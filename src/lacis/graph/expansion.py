import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from lacis.collectors.company_register import Company, CompanyRegister, siren_of
from lacis.graph.mapping import GraphFragment, company_entity, company_fragment, spaced_siren
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseSummary


@dataclass(frozen=True)
class GraphChanges:
    new_entities: tuple[str, ...] = ()
    new_links: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (self.new_entities or self.new_links)


EXPANDED_AT_ATTRIBUTE = "expanded_at"


class ExpansionError(Exception):
    pass


def current_time() -> datetime:
    return datetime.now(UTC)


def unknown_company_message(siren: str) -> str:
    return f"Aucune entreprise ne porte le SIREN {spaced_siren(siren)} dans le registre national."


class GraphExpander:
    def __init__(
        self,
        connection: sqlite3.Connection,
        company_register: CompanyRegister,
        now: Callable[[], datetime] = current_time,
    ) -> None:
        self.graph_store = GraphStore(connection)
        self.company_register = company_register
        self.now = now

    def expand_company(self, siren: str, *, refresh: bool = False) -> GraphChanges:
        digits = siren_of(siren)
        sourced_company = self.company_register.sourced_company(digits, refresh=refresh)
        if sourced_company is None:
            raise ExpansionError(unknown_company_message(digits))
        fragment = self.marked_as_expanded(company_fragment(sourced_company.company))
        return self.save_fragment(fragment, sourced_company.response)

    def marked_as_expanded(self, fragment: GraphFragment) -> GraphFragment:
        company = fragment.entities[0]
        expanded_attributes = {
            **company.attributes,
            EXPANDED_AT_ATTRIBUTE: self.now().isoformat(),
        }
        marked_company = replace(company, attributes=expanded_attributes)
        return replace(fragment, entities=(marked_company, *fragment.entities[1:]))

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
