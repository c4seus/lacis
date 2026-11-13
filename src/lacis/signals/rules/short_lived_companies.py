from dataclasses import dataclass

from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE
from lacis.signals.context import InvestigationContext
from lacis.signals.facts import counted
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.rules.company_life import (
    insolvency_notices,
    lifetime_months,
    mentions_liquidation,
    shown_months,
)
from lacis.signals.rules.directors import (
    EXCLUDED_ROLES,
    INCLUDE_PROBABLE,
    DirectedCompanies,
    directed_companies,
)
from lacis.signals.signal import Finding, Severity
from lacis.storage.entities import Entity, EntityKind

MINIMUM_COMPANIES = Threshold("minimum_companies", ThresholdKind.WHOLE_NUMBER, minimum=1)
MINIMUM_SHORT_LIVED = Threshold("minimum_short_lived", ThresholdKind.WHOLE_NUMBER, minimum=1)
MAXIMUM_LIFETIME_MONTHS = Threshold(
    "maximum_lifetime_months", ThresholdKind.WHOLE_NUMBER, minimum=1
)
LIQUIDATION_BONUS = 0.2
NOT_EXPANDED_TEXT = " ; cette personne n'a pas encore été étendue"


@dataclass(frozen=True)
class ShortLived:
    company: Entity
    months: float
    liquidated: bool


def short_lived_of(
    context: InvestigationContext, companies: list[Entity], maximum_months: int
) -> list[ShortLived]:
    found = []
    for company in companies:
        months = lifetime_months(company)
        if months is not None and months < maximum_months:
            liquidated = mentions_liquidation(insolvency_notices(context, company))
            found.append(ShortLived(company, months, liquidated))
    return sorted(found, key=lambda short_lived: (short_lived.months, short_lived.company.label))


def explanation_of(
    directed: DirectedCompanies, short_lived: list[ShortLived], maximum_months: int
) -> str:
    listed = ", ".join(
        f"{found.company.label} ({shown_months(found.months)})" for found in short_lived
    )
    liquidated = sum(found.liquidated for found in short_lived)
    liquidation = (
        f" ; {counted(liquidated, 'a fermé', 'ont fermé')} après une liquidation judiciaire"
        if liquidated
        else ""
    )
    merged = (
        f" ; le décompte réunit {len(directed.members)} fiches de la même personne"
        if len(directed.members) > 1
        else ""
    )
    director = directed.director
    not_expanded = (
        NOT_EXPANDED_TEXT
        if director.kind is EntityKind.PERSON and EXPANDED_AT_ATTRIBUTE not in director.attributes
        else ""
    )
    companies = counted(len(directed.companies), "entreprise", "entreprises")
    closed = counted(len(short_lived), "fermée", "fermées")
    return (
        f"{director.label} dirige ou a dirigé {companies} de l'enquête, dont {closed} moins de "
        f"{maximum_months} mois après leur création : {listed}{liquidation}{merged}{not_expanded}."
    )


@dataclass(frozen=True)
class ShortLivedCompaniesRule:
    name: str = "short_lived_companies"
    title: str = "Sociétés éphémères en série"
    thresholds: tuple[Threshold, ...] = (
        MINIMUM_COMPANIES,
        MINIMUM_SHORT_LIVED,
        MAXIMUM_LIFETIME_MONTHS,
        INCLUDE_PROBABLE,
        EXCLUDED_ROLES,
    )

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        minimum_companies = settings.whole_number(MINIMUM_COMPANIES.name)
        minimum_short_lived = settings.whole_number(MINIMUM_SHORT_LIVED.name)
        maximum_months = settings.whole_number(MAXIMUM_LIFETIME_MONTHS.name)
        findings = []
        for identity, directed in sorted(directed_companies(context, settings).items()):
            companies = list(directed.companies.values())
            if len(companies) < minimum_companies:
                continue
            short_lived = short_lived_of(context, companies, maximum_months)
            if len(short_lived) < minimum_short_lived:
                continue
            liquidated = any(found.liquidated for found in short_lived)
            share = len(short_lived) / len(companies)
            strength = min(1.0, len(short_lived) / (2 * minimum_short_lived)) * (0.6 + 0.4 * share)
            doubled = len(short_lived) >= 2 * minimum_short_lived
            findings.append(
                Finding(
                    subject=identity,
                    strength=min(1.0, strength + (LIQUIDATION_BONUS if liquidated else 0.0)),
                    explanation=explanation_of(directed, short_lived, maximum_months),
                    justifying_entities=(
                        *(found.company.identifier for found in short_lived),
                        *(member for member in sorted(directed.members) if member != identity),
                    ),
                    severity=Severity.HIGH if doubled or liquidated else None,
                )
            )
        return findings
