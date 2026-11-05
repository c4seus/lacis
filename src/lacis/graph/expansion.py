import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from lacis.collectors.bodacc import Bodacc, CompanyNotices
from lacis.collectors.company_register import Company, CompanyRegister, siren_of
from lacis.graph.mapping import GraphFragment, company_entity, company_fragment, spaced_siren
from lacis.storage.entities import company_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.notices import NoticeStore
from lacis.storage.responses import ResponseSummary


@dataclass(frozen=True)
class GraphChanges:
    new_entities: tuple[str, ...] = ()
    new_links: tuple[str, ...] = ()
    new_notices: tuple[str, ...] = ()
    withdrawn_notices: tuple[str, ...] = ()

    @property
    def is_empty(self) -> bool:
        return not (
            self.new_entities or self.new_links or self.new_notices or self.withdrawn_notices
        )


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
        bodacc: Bodacc,
        now: Callable[[], datetime] = current_time,
    ) -> None:
        self.graph_store = GraphStore(connection)
        self.notice_store = NoticeStore(connection)
        self.company_register = company_register
        self.bodacc = bodacc
        self.now = now

    def expand_company(self, siren: str, *, refresh: bool = False) -> GraphChanges:
        digits = siren_of(siren)
        sourced_company = self.company_register.sourced_company(digits, refresh=refresh)
        if sourced_company is None:
            raise ExpansionError(unknown_company_message(digits))
        fragment = self.marked_as_expanded(company_fragment(sourced_company.company))
        graph_changes = self.save_fragment(fragment, sourced_company.response)
        notice_changes = self.save_notices(self.bodacc.notices_of(digits, refresh=refresh))
        return replace(
            graph_changes,
            new_notices=notice_changes.new_notices,
            withdrawn_notices=notice_changes.withdrawn_notices,
        )

    def save_notices(self, company_notices: CompanyNotices) -> GraphChanges:
        new_notices = []
        for notice in company_notices.notices:
            if self.notice_store.notice(notice.identifier) is None:
                new_notices.append(notice.identifier)
            collected_notice = notice.collected_notice()
            known_companies = {
                company: role
                for company, role in collected_notice.companies.items()
                if self.graph_store.entity(company) is not None
            }
            self.notice_store.save_notice(
                replace(collected_notice, companies=known_companies), notice.response
            )
        withdrawn_notices: list[str] = []
        if company_notices.is_complete:
            withdrawn_notices = [
                withdrawn.identifier
                for withdrawn in self.notice_store.record_refresh(
                    company_identifier(company_notices.siren),
                    company_notices.pages[-1].response,
                    [notice.identifier for notice in company_notices.notices],
                )
            ]
        return GraphChanges(
            new_notices=tuple(new_notices), withdrawn_notices=tuple(withdrawn_notices)
        )

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
