from dataclasses import dataclass
from datetime import date

from lacis.signals.context import InvestigationContext
from lacis.signals.facts import activity, creation_date, french_date
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.rules.company_life import (
    closing_date,
    insolvency_notices,
    mentions_liquidation,
    months_between,
)
from lacis.signals.rules.directors import EXCLUDED_ROLES, INCLUDE_PROBABLE, mandates
from lacis.signals.signal import Finding, Severity
from lacis.storage.comparison_keys import normalise_text
from lacis.storage.entities import Entity, EntityKind, LinkKind

WINDOW_MONTHS = Threshold("window_months", ThresholdKind.WHOLE_NUMBER, minimum=1)
NAME_OVERLAP = Threshold("name_overlap", ThresholdKind.NUMBER, minimum=0, maximum=1)
MINIMUM_NAME_WORD_LENGTH = 3
NAME_STOPWORDS = frozenset(
    {
        "SARL",
        "SAS",
        "SASU",
        "EURL",
        "SCI",
        "SNC",
        "SOCIETE",
        "STE",
        "ETS",
        "ETABLISSEMENTS",
        "GROUPE",
        "HOLDING",
        "FRANCE",
        "LES",
        "DES",
    }
)
BASE_STRENGTH = 0.5
LIQUIDATION_STRENGTH = 0.2
CLUE_STRENGTH = 0.15

type DirectorsByIdentity = dict[str, list[Entity]]


@dataclass(frozen=True)
class ClosedCompany:
    company: Entity
    closed_on: date
    liquidated: bool


@dataclass(frozen=True)
class PhoenixPair:
    closed: ClosedCompany
    successor: Entity
    created_on: date
    directors: tuple[str, ...]
    named_directors: tuple[Entity, ...]
    same_address: bool
    close_name: bool

    @property
    def severity(self) -> Severity | None:
        clue = self.same_address or self.close_name
        if self.closed.liquidated and clue:
            return Severity.HIGH
        if self.closed.liquidated or clue:
            return Severity.MEDIUM
        return None

    @property
    def strength(self) -> float:
        return min(
            1.0,
            BASE_STRENGTH
            + LIQUIDATION_STRENGTH * self.closed.liquidated
            + CLUE_STRENGTH * self.same_address
            + CLUE_STRENGTH * self.close_name,
        )


def name_words(label: str) -> set[str]:
    return {
        word
        for word in normalise_text(label).split()
        if len(word) >= MINIMUM_NAME_WORD_LENGTH and word not in NAME_STOPWORDS
    }


def names_are_close(first: str, second: str, overlap: float) -> bool:
    first_words, second_words = name_words(first), name_words(second)
    if not first_words or not second_words:
        return False
    shared = len(first_words & second_words)
    return shared / min(len(first_words), len(second_words)) >= overlap


def closed_after_insolvency(
    context: InvestigationContext, company: Entity
) -> ClosedCompany | None:
    closed_on = closing_date(company)
    notices = insolvency_notices(context, company)
    if closed_on is None or not notices:
        return None
    return ClosedCompany(company, closed_on, mentions_liquidation(notices))


def registered_offices(context: InvestigationContext, company: Entity) -> set[str]:
    return {
        address.identifier
        for address in context.neighbours(
            company.identifier, LinkKind.REGISTERED_OFFICE, EntityKind.ADDRESS
        )
    }


def delay_text(created_on: date, closed_on: date) -> str:
    months = round(months_between(created_on, closed_on))
    if months == 0:
        return "le même mois"
    return f"{months} mois {'plus tôt' if created_on < closed_on else 'plus tard'}"


def explanation_of(pair: PhoenixPair) -> str:
    closed = pair.closed
    proceeding = "une liquidation judiciaire" if closed.liquidated else "une procédure collective"
    names = ", ".join(director.label for director in pair.named_directors)
    same_director = "même dirigeant" if len(pair.named_directors) == 1 else "mêmes dirigeants"
    delay = delay_text(pair.created_on, closed.closed_on)
    text = (
        f"{closed.company.label} a fermé le {french_date(closed.closed_on)} après {proceeding} ; "
        f"{pair.successor.label}, {same_director} ({names}) et même activité "
        f"({activity(closed.company)}), a été créée {delay}."
    )
    clues = [
        clue
        for present, clue in ((pair.same_address, "même adresse"), (pair.close_name, "nom proche"))
        if present
    ]
    return f"{text} Indices : {', '.join(clues)}." if clues else text


def created_after(created_on: date, closed_company: Entity) -> bool:
    closed_company_created_on = creation_date(closed_company)
    return closed_company_created_on is None or created_on > closed_company_created_on


def directors_by_company(
    context: InvestigationContext, settings: RuleSettings
) -> dict[str, DirectorsByIdentity]:
    directors: dict[str, DirectorsByIdentity] = {}
    for mandate in mandates(context, settings):
        by_identity = directors.setdefault(mandate.company.identifier, {})
        by_identity.setdefault(mandate.identity, []).append(mandate.director)
    return directors


def phoenix_pairs(context: InvestigationContext, settings: RuleSettings) -> list[PhoenixPair]:
    window_months = settings.whole_number(WINDOW_MONTHS.name)
    overlap = settings.number(NAME_OVERLAP.name)
    directors = directors_by_company(context, settings)
    companies = sorted(
        context.entities_of(EntityKind.COMPANY), key=lambda company: company.identifier
    )
    pairs = []
    for company in companies:
        closed = closed_after_insolvency(context, company)
        if closed is None or activity(company) is None:
            continue
        closed_directors = directors.get(company.identifier, {})
        for successor in companies:
            created_on = creation_date(successor)
            if (
                successor is company
                or activity(successor) != activity(company)
                or created_on is None
                or months_between(created_on, closed.closed_on) > window_months
                or not created_after(created_on, company)
            ):
                continue
            successor_directors = directors.get(successor.identifier, {})
            shared = sorted(set(closed_directors) & set(successor_directors))
            if not shared:
                continue
            pairs.append(
                PhoenixPair(
                    closed=closed,
                    successor=successor,
                    created_on=created_on,
                    directors=tuple(
                        dict.fromkeys(
                            director.identifier
                            for identity in shared
                            for director in (
                                *closed_directors[identity],
                                *successor_directors[identity],
                            )
                        )
                    ),
                    named_directors=tuple(
                        sorted(
                            (closed_directors[identity][0] for identity in shared),
                            key=lambda director: director.label,
                        )
                    ),
                    same_address=bool(
                        registered_offices(context, company)
                        & registered_offices(context, successor)
                    ),
                    close_name=names_are_close(company.label, successor.label, overlap),
                )
            )
    return pairs


@dataclass(frozen=True)
class PhoenixSchemeRule:
    name: str = "phoenix_scheme"
    title: str = "Schéma phénix"
    thresholds: tuple[Threshold, ...] = (
        WINDOW_MONTHS,
        NAME_OVERLAP,
        INCLUDE_PROBABLE,
        EXCLUDED_ROLES,
    )

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        return [
            Finding(
                subject=pair.successor.identifier,
                strength=pair.strength,
                explanation=explanation_of(pair),
                justifying_entities=(
                    pair.closed.company.identifier,
                    *pair.directors,
                ),
                severity=pair.severity,
            )
            for pair in phoenix_pairs(context, settings)
        ]
