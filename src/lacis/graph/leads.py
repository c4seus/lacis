from dataclasses import dataclass

from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE, PIVOT_KINDS
from lacis.storage.entities import Entity, EntityKind, LinkKind
from lacis.storage.graph_store import GraphStore

KNOWN_AS_DIRECTOR_ONLY = "Connue comme dirigeante seulement"
COMPANY_DETAILS_NOT_FETCHED = "Établissements, dirigeants et annonces pas encore recherchés"
OTHER_MANDATES_POSSIBLE = "D'autres mandats peuvent exister"
OTHER_COMPANIES_POSSIBLE = "D'autres entreprises peuvent y être domiciliées"
KIND_ORDER = (EntityKind.COMPANY, EntityKind.PERSON, EntityKind.ADDRESS)


@dataclass(frozen=True)
class Lead:
    identifier: str
    kind: EntityKind
    label: str
    reason: str


def is_known_as_director_only(graph_store: GraphStore, company: Entity) -> bool:
    links = graph_store.links_of(company.identifier)
    return bool(links) and all(
        link.kind is LinkKind.MANDATE and link.source == company.identifier for link in links
    )


def reason_for(graph_store: GraphStore, entity: Entity) -> str:
    if entity.kind is EntityKind.PERSON:
        return OTHER_MANDATES_POSSIBLE
    if entity.kind is EntityKind.ADDRESS:
        return OTHER_COMPANIES_POSSIBLE
    if is_known_as_director_only(graph_store, entity):
        return KNOWN_AS_DIRECTOR_ONLY
    return COMPANY_DETAILS_NOT_FETCHED


def unexpanded_leads(graph_store: GraphStore) -> list[Lead]:
    leads = [
        Lead(entity.identifier, entity.kind, entity.label, reason_for(graph_store, entity))
        for entity in graph_store.entities()
        if entity.kind in PIVOT_KINDS and EXPANDED_AT_ATTRIBUTE not in entity.attributes
    ]
    return sorted(leads, key=lambda lead: (KIND_ORDER.index(lead.kind), lead.label.casefold()))
