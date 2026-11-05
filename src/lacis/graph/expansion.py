import sqlite3
from dataclasses import dataclass

from lacis.collectors.company_register import Company
from lacis.graph.mapping import GraphFragment, company_entity
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseSummary


@dataclass(frozen=True)
class GraphChanges:
    new_entities: tuple[str, ...] = ()
    new_links: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.new_entities or self.new_links)


class GraphExpander:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.graph_store = GraphStore(connection)

    def add_company(self, company: Company, response: ResponseSummary) -> GraphChanges:
        return self.save_fragment(GraphFragment((company_entity(company),)), response)

    def save_fragment(self, fragment: GraphFragment, response: ResponseSummary) -> GraphChanges:
        new_entities = [
            entity.identifier
            for entity in fragment.entities
            if self.graph_store.entity(entity.identifier) is None
        ]
        new_links = [
            link.identifier
            for link in fragment.links
            if self.graph_store.link(link.identifier) is None
        ]
        for entity in fragment.entities:
            self.graph_store.save_entity(entity, response)
        for link in fragment.links:
            self.graph_store.save_link(link, response)
        return GraphChanges(tuple(new_entities), tuple(new_links))
