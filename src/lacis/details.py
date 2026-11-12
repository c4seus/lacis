import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from urllib.parse import quote

from lacis.collectors.bodacc import NOTICE_URL
from lacis.collectors.http_client import SOURCE_NAMES
from lacis.graph.drawing import KIND_LABELS, is_closed
from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE, PIVOT_KINDS
from lacis.graph.leads import is_known_as_director_only
from lacis.graph.mapping import spaced_siren
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import Attributes, Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.notices import NoticeFamily, NoticeRole, NoticeStore
from lacis.storage.responses import ResponseStore, ResponseSummary

DIRECTORY_ROOT = "https://annuaire-entreprises.data.gouv.fr"
SHORT_FINGERPRINT_LENGTH = 8
ACTIVE_TEXT = "Active"
CLOSED_COMPANY_TEXT = "Fermée"
OPEN_ESTABLISHMENT_TEXT = "Ouvert"
CLOSED_ESTABLISHMENT_TEXT = "Fermé"
HEAD_OFFICE_TEXT = "Siège"
DIRECTOR_ONLY_TEXT = "Connue comme dirigeante seulement"


class BadgeTone(StrEnum):
    ACTIVE = "active"
    CLOSED = "closed"
    OUTLINE = "outline"


@dataclass(frozen=True)
class Badge:
    text: str
    tone: BadgeTone


@dataclass(frozen=True)
class Reference:
    identifier: str
    kind: EntityKind
    label: str


@dataclass(frozen=True)
class SignalCard:
    title: str
    severity: Severity
    score: float
    explanation: str
    references: tuple[Reference, ...]

    @property
    def written_score(self) -> str:
        return f"score {self.score:.2f}".replace(".", ",")


@dataclass(frozen=True)
class LinkLine:
    role: str
    reference: Reference
    closed: bool


@dataclass(frozen=True)
class SourceLine:
    response_identifier: int
    source_name: str
    collected_at: datetime
    fingerprint: str
    url: str

    @property
    def written_date(self) -> str:
        return written_moment(self.collected_at)

    @property
    def short_fingerprint(self) -> str:
        start = self.fingerprint[:SHORT_FINGERPRINT_LENGTH]
        end = self.fingerprint[-SHORT_FINGERPRINT_LENGTH:]
        return f"{start}…{end}"


FAMILY_LABELS = {
    NoticeFamily.CREATION: "Création",
    NoticeFamily.REGISTRATION: "Immatriculation",
    NoticeFamily.AMENDMENT: "Modification",
    NoticeFamily.INSOLVENCY: "Procédure collective",
    NoticeFamily.CONCILIATION: "Conciliation",
    NoticeFamily.PROFESSIONAL_RECOVERY: "Rétablissement professionnel",
    NoticeFamily.SALE: "Vente et cession",
    NoticeFamily.ACCOUNTS: "Dépôt des comptes",
    NoticeFamily.REMOVAL: "Radiation",
    NoticeFamily.MISCELLANEOUS: "Divers",
}
ALERT_FAMILIES = frozenset(
    {NoticeFamily.INSOLVENCY, NoticeFamily.PROFESSIONAL_RECOVERY, NoticeFamily.REMOVAL}
)
ROLE_NOTES = {
    NoticeRole.SUBJECT: "",
    NoticeRole.PREVIOUS_OPERATOR: "En tant qu'ancien exploitant",
    NoticeRole.PREVIOUS_OWNER: "En tant qu'ancien propriétaire",
    NoticeRole.MENTIONED: "Mentionnée dans l'annonce",
}


@dataclass(frozen=True)
class NoticeLine:
    identifier: str
    family: NoticeFamily
    published_on: date
    summary: str
    court: str
    judgment: str
    response_identifier: int
    role: NoticeRole
    withdrawn_at: datetime | None = None

    @property
    def written_date(self) -> str:
        return self.published_on.strftime("%d/%m/%Y")

    @property
    def family_label(self) -> str:
        return FAMILY_LABELS[self.family]

    @property
    def is_alert(self) -> bool:
        return self.family in ALERT_FAMILIES

    @property
    def is_withdrawn(self) -> bool:
        return self.withdrawn_at is not None

    @property
    def withdrawn_text(self) -> str:
        if self.withdrawn_at is None:
            return ""
        moment = self.withdrawn_at.astimezone()
        return f"Absente du BODACC au rafraîchissement du {moment:%d/%m/%Y}"

    @property
    def role_note(self) -> str:
        return ROLE_NOTES[self.role]

    @property
    def shown_judgment(self) -> str:
        repeated = self.judgment.casefold() in self.summary.casefold()
        return "" if repeated or not self.judgment else self.judgment

    @property
    def url(self) -> str:
        return NOTICE_URL.format(identifier=self.identifier)


@dataclass(frozen=True)
class EntityDetails:
    identifier: str
    kind: EntityKind
    name: str
    badges: tuple[Badge, ...]
    facts: tuple[str, ...]
    expanded_on: str
    copy_label: str
    copy_value: str
    directory_url: str
    signals: tuple[SignalCard, ...]
    links: tuple[LinkLine, ...]
    sources: tuple[SourceLine, ...]
    notices: tuple[NoticeLine, ...] = ()

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind].capitalize()

    @property
    def expandable(self) -> bool:
        return self.kind in PIVOT_KINDS

    @property
    def has_notices(self) -> bool:
        return self.kind is EntityKind.COMPANY

    @property
    def expanded(self) -> bool:
        return bool(self.expanded_on)


def written_day(text: object) -> str:
    if not isinstance(text, str) or not text:
        return ""
    try:
        return date.fromisoformat(text).strftime("%d/%m/%Y")
    except ValueError:
        return ""


def written_moment(moment: datetime) -> str:
    return moment.astimezone().strftime("%d/%m/%Y à %H:%M")


def written_month(text: object) -> str:
    if not isinstance(text, str) or "-" not in text:
        return ""
    year, month = text.split("-", 1)
    return f"{month}/{year}"


def text_of(attributes: Attributes, name: str) -> str:
    value = attributes.get(name)
    return value if isinstance(value, str) else ""


def spaced_siret(siret: str) -> str:
    return f"{spaced_siren(siret[:9])} {siret[9:]}"


def company_facts(attributes: Attributes) -> list[str]:
    siren = text_of(attributes, "siren")
    facts = [f"SIREN {spaced_siren(siren)}"] if siren else []
    created = written_day(attributes.get("creation_date"))
    closed = written_day(attributes.get("closing_date"))
    activity = text_of(attributes, "activity")
    facts += [f"Créée le {created}"] if created else []
    facts += [f"Fermée le {closed}"] if closed else []
    facts += [f"NAF {activity}"] if activity else []
    return facts


def establishment_facts(attributes: Attributes) -> list[str]:
    siret = text_of(attributes, "siret")
    facts = [f"SIRET {spaced_siret(siret)}"] if siret else []
    created = written_day(attributes.get("creation_date"))
    closed = written_day(attributes.get("closing_date"))
    activity = text_of(attributes, "activity")
    facts += [f"Créé le {created}"] if created else []
    facts += [f"Fermé le {closed}"] if closed else []
    facts += [f"NAF {activity}"] if activity else []
    return facts


def person_facts(attributes: Attributes) -> list[str]:
    born = written_month(attributes.get("birth_month"))
    nationality = text_of(attributes, "nationality")
    facts = [f"Né en {born}"] if born else []
    facts += [f"Nationalité {nationality}"] if nationality else []
    return facts


def address_facts(attributes: Attributes) -> list[str]:
    postcode = text_of(attributes, "postcode")
    city = text_of(attributes, "city")
    facts = [f"Code postal {postcode}"] if postcode else []
    facts += [f"Commune {city}"] if city else []
    return facts


def foreign_company_facts(attributes: Attributes) -> list[str]:
    country = text_of(attributes, "country")
    return [f"Pays {country}"] if country else []


FACTS = {
    EntityKind.COMPANY: company_facts,
    EntityKind.ESTABLISHMENT: establishment_facts,
    EntityKind.PERSON: person_facts,
    EntityKind.ADDRESS: address_facts,
    EntityKind.FOREIGN_COMPANY: foreign_company_facts,
}


def status_badges(graph_store: GraphStore, entity: Entity) -> list[Badge]:
    attributes = entity.attributes
    badges = []
    if entity.kind is EntityKind.COMPANY:
        if attributes.get("is_active") is True:
            badges.append(Badge(ACTIVE_TEXT, BadgeTone.ACTIVE))
        elif attributes.get("is_active") is False:
            badges.append(Badge(CLOSED_COMPANY_TEXT, BadgeTone.CLOSED))
        if is_known_as_director_only(graph_store, entity):
            badges.append(Badge(DIRECTOR_ONLY_TEXT, BadgeTone.OUTLINE))
    if entity.kind is EntityKind.ESTABLISHMENT:
        if attributes.get("is_head_office") is True:
            badges.append(Badge(HEAD_OFFICE_TEXT, BadgeTone.OUTLINE))
        if is_closed(entity):
            badges.append(Badge(CLOSED_ESTABLISHMENT_TEXT, BadgeTone.CLOSED))
        elif attributes.get("is_open") is True:
            badges.append(Badge(OPEN_ESTABLISHMENT_TEXT, BadgeTone.ACTIVE))
    return badges


def copied(entity: Entity) -> tuple[str, str]:
    if entity.kind is EntityKind.COMPANY and text_of(entity.attributes, "siren"):
        return "Copier le SIREN", text_of(entity.attributes, "siren")
    if entity.kind is EntityKind.ESTABLISHMENT and text_of(entity.attributes, "siret"):
        return "Copier le SIRET", text_of(entity.attributes, "siret")
    if entity.kind is EntityKind.ADDRESS:
        return "Copier l'adresse", entity.label
    return "Copier le nom", entity.label


def directory_url(entity: Entity) -> str:
    siren = text_of(entity.attributes, "siren")
    siret = text_of(entity.attributes, "siret")
    if entity.kind is EntityKind.COMPANY and siren:
        return f"{DIRECTORY_ROOT}/entreprise/{siren}"
    if entity.kind is EntityKind.ESTABLISHMENT and siret:
        return f"{DIRECTORY_ROOT}/etablissement/{siret}"
    if entity.kind in {EntityKind.PERSON, EntityKind.ADDRESS}:
        return f"{DIRECTORY_ROOT}/rechercher?terme={quote(entity.label)}"
    return ""


class References:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store

    def of(self, identifier: str) -> Reference:
        entity = self.graph_store.require_entity(identifier)
        return Reference(identifier, entity.kind, entity.label)


def signal_cards(
    report: SignalReport | None, identifier: str, references: References
) -> list[SignalCard]:
    if report is None:
        return []
    concerned: list[Signal] = [
        signal
        for signal in report.signals
        if identifier == signal.subject or identifier in signal.justifying_entities
    ]
    ordered = sorted(concerned, key=lambda signal: (-signal.severity.rank, -signal.score))
    cards = []
    for signal in ordered:
        others = [
            other
            for other in dict.fromkeys((signal.subject, *signal.justifying_entities))
            if other != identifier
        ]
        cards.append(
            SignalCard(
                signal.title,
                signal.severity,
                signal.score,
                signal.explanation,
                tuple(references.of(other) for other in others),
            )
        )
    return cards


def link_role(link: Link, identifier: str) -> str:
    seen_from_source = link.source == identifier
    roles = {
        LinkKind.ESTABLISHMENT_OF: ("Entreprise", "Établissement"),
        LinkKind.LOCATED_AT: ("Adresse", "Établissement"),
        LinkKind.REGISTERED_OFFICE: ("Siège social", "Siège de"),
        LinkKind.SAME_PERSON: ("Même personne", "Même personne"),
    }
    if link.kind is LinkKind.MANDATE:
        return f"{link.role} de" if seen_from_source else link.role
    from_source, from_target = roles[link.kind]
    return from_source if seen_from_source else from_target


def link_lines(graph_store: GraphStore, identifier: str) -> list[LinkLine]:
    lines = []
    for link in graph_store.links_of(identifier):
        other = graph_store.require_entity(
            link.target if link.source == identifier else link.source
        )
        lines.append(
            LinkLine(
                link_role(link, identifier),
                Reference(other.identifier, other.kind, other.label),
                is_closed(other),
            )
        )
    return sorted(lines, key=lambda line: (line.role, line.reference.label))


def source_line(summary: ResponseSummary) -> SourceLine:
    return SourceLine(
        summary.identifier,
        SOURCE_NAMES[summary.source],
        summary.collected_at,
        summary.fingerprint,
        summary.url,
    )


def notice_lines(connection: sqlite3.Connection, identifier: str) -> list[NoticeLine]:
    by_family = NoticeStore(connection).notices_of_company(identifier)
    lines = [
        NoticeLine(
            company_notice.notice.identifier,
            company_notice.notice.family,
            company_notice.notice.published_on,
            company_notice.notice.summary,
            company_notice.notice.court,
            company_notice.notice.judgment,
            company_notice.notice.response_identifier,
            company_notice.role,
            company_notice.notice.withdrawn_at,
        )
        for notices in by_family.values()
        for company_notice in notices
    ]
    return sorted(lines, key=lambda line: (line.published_on, line.identifier), reverse=True)


def entity_details(
    connection: sqlite3.Connection, identifier: str, report: SignalReport | None
) -> EntityDetails | None:
    graph_store = GraphStore(connection)
    entity = graph_store.entity(identifier)
    if entity is None:
        return None
    copy_label, copy_value = copied(entity)
    expanded_at = entity.attributes.get(EXPANDED_AT_ATTRIBUTE)
    expanded_on = (
        f"Étendue le {written_moment(datetime.fromisoformat(expanded_at))}"
        if isinstance(expanded_at, str) and expanded_at
        else ""
    )
    sources = [source_line(summary) for summary in graph_store.sources_of_entity(identifier)]
    return EntityDetails(
        identifier=identifier,
        kind=entity.kind,
        name=entity.label,
        badges=tuple(status_badges(graph_store, entity)),
        facts=tuple(FACTS[entity.kind](entity.attributes)),
        expanded_on=expanded_on,
        copy_label=copy_label,
        copy_value=copy_value,
        directory_url=directory_url(entity),
        signals=tuple(signal_cards(report, identifier, References(graph_store))),
        links=tuple(link_lines(graph_store, identifier)),
        sources=tuple(reversed(sources)),
        notices=tuple(notice_lines(connection, identifier)),
    )


def raw_response(connection: sqlite3.Connection, response_identifier: int) -> str:
    body = ResponseStore(connection).read(response_identifier).body
    try:
        return json.dumps(json.loads(body), ensure_ascii=False, indent=2)
    except ValueError:
        return body.decode("utf-8", errors="replace")
