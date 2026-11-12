import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from lacis.graph.drawing import KIND_LABELS, is_closed
from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE, PIVOT_KINDS
from lacis.graph.leads import is_known_as_director_only
from lacis.graph.mapping import spaced_siren
from lacis.storage.entities import Attributes, Entity, EntityKind
from lacis.storage.graph_store import GraphStore

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
class EntityDetails:
    identifier: str
    kind: EntityKind
    name: str
    badges: tuple[Badge, ...]
    facts: tuple[str, ...]
    expanded_on: str

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind].capitalize()

    @property
    def expandable(self) -> bool:
        return self.kind in PIVOT_KINDS

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


def entity_details(connection: sqlite3.Connection, identifier: str) -> EntityDetails | None:
    graph_store = GraphStore(connection)
    entity = graph_store.entity(identifier)
    if entity is None:
        return None
    expanded_at = entity.attributes.get(EXPANDED_AT_ATTRIBUTE)
    expanded_on = (
        f"Étendue le {written_moment(datetime.fromisoformat(expanded_at))}"
        if isinstance(expanded_at, str) and expanded_at
        else ""
    )
    return EntityDetails(
        identifier=identifier,
        kind=entity.kind,
        name=entity.label,
        badges=tuple(status_badges(graph_store, entity)),
        facts=tuple(FACTS[entity.kind](entity.attributes)),
        expanded_on=expanded_on,
    )
