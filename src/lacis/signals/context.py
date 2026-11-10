import sqlite3
from datetime import date

from lacis.identity.identities import PersonIdentities
from lacis.storage.entities import Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecisionStore
from lacis.storage.notices import CompanyNotice, NoticeFamily, NoticeStore


class InvestigationContext:
    def __init__(self, connection: sqlite3.Connection, today: date) -> None:
        self.today = today
        self.connection = connection
        self.graph_store = GraphStore(connection)
        self.notice_store = NoticeStore(connection)
        self.computed_identities: dict[bool, PersonIdentities] = {}
        self.entities = {entity.identifier: entity for entity in self.graph_store.entities()}
        self.links = self.graph_store.links()
        self.links_by_entity: dict[str, list[Link]] = {}
        for link in self.links:
            self.links_by_entity.setdefault(link.source, []).append(link)
            self.links_by_entity.setdefault(link.target, []).append(link)

    def entity(self, identifier: str) -> Entity | None:
        return self.entities.get(identifier)

    def entities_of(self, kind: EntityKind) -> list[Entity]:
        return [entity for entity in self.entities.values() if entity.kind is kind]

    def links_of(self, identifier: str, kind: LinkKind | None = None) -> list[Link]:
        return [
            link
            for link in self.links_by_entity.get(identifier, [])
            if kind is None or link.kind is kind
        ]

    def neighbours(
        self,
        identifier: str,
        link_kind: LinkKind | None = None,
        entity_kind: EntityKind | None = None,
    ) -> list[Entity]:
        found: dict[str, Entity] = {}
        for link in self.links_of(identifier, link_kind):
            other = self.entities.get(link.target if link.source == identifier else link.source)
            if other is not None and (entity_kind is None or other.kind is entity_kind):
                found[other.identifier] = other
        return list(found.values())

    def identities(self, *, include_probable: bool) -> PersonIdentities:
        if include_probable not in self.computed_identities:
            self.computed_identities[include_probable] = PersonIdentities(
                self.graph_store,
                HomonymDecisionStore(self.connection),
                include_probable=include_probable,
            )
        return self.computed_identities[include_probable]

    def notices_of(self, company: str) -> dict[NoticeFamily, list[CompanyNotice]]:
        return self.notice_store.notices_of_company(company)
