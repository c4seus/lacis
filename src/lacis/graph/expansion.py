import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Self

from lacis.collectors.bodacc import Bodacc, CompanyNotices
from lacis.collectors.company_register import (
    SIREN_LENGTH,
    Company,
    CompanyRegister,
    CompanySearchPage,
    NaturalPersonDirector,
    siren_of,
)
from lacis.graph.mapping import (
    GraphFragment,
    combined,
    company_entity,
    company_fragment,
    director_fragment,
    establishment_fragment,
    shown,
    spaced_siren,
)
from lacis.storage.comparison_keys import person_name_key
from lacis.storage.entities import (
    CollectedEntity,
    EntityKind,
    company_identifier,
    establishment_of_link,
    registered_office_link,
)
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
MAXIMUM_SEARCH_PAGES = 4
ESTABLISHMENT_PREFIX = f"{EntityKind.ESTABLISHMENT}:"
UNKNOWN_ENTITY_MESSAGE = "Cette entité n'est pas dans l'enquête ou ne peut pas être étendue."


def combined_changes(changes: Iterable[GraphChanges]) -> GraphChanges:
    every_change = list(changes)
    return GraphChanges(
        *(
            tuple(
                dict.fromkeys(
                    identifier for change in every_change for identifier in getattr(change, name)
                )
            )
            for name in ("new_entities", "new_links", "new_notices", "withdrawn_notices")
        )
    )


@dataclass(frozen=True)
class SearchedName:
    last_name: str
    first_names: str
    birth_month: str | None

    @classmethod
    def of(cls, person: CollectedEntity) -> Self:
        birth_month = person.attributes.get("birth_month")
        return cls(
            str(person.attributes.get("last_name") or ""),
            str(person.attributes.get("first_names") or ""),
            birth_month if isinstance(birth_month, str) else None,
        )

    def bears(self, director: NaturalPersonDirector) -> bool:
        last_name = shown(director.last_name)
        if last_name is None or person_name_key(last_name) != person_name_key(self.last_name):
            return False
        first_name_words = set(person_name_key(shown(director.first_names) or "").split())
        if not set(person_name_key(self.first_names).split()) <= first_name_words:
            return False
        birth_month = shown(director.birth_month)
        return None in (birth_month, self.birth_month) or birth_month == self.birth_month

    def mandates_in(self, company: Company) -> GraphFragment:
        company_entity_identifier = company_identifier(company.siren)
        return combined(
            [
                GraphFragment((company_entity(company),)),
                *(
                    director_fragment(company_entity_identifier, director)
                    for director in company.directors
                    if isinstance(director, NaturalPersonDirector) and self.bears(director)
                ),
            ]
        )


class ExpansionError(Exception):
    pass


def current_time() -> datetime:
    return datetime.now(UTC)


def unknown_company_message(siren: str) -> str:
    return f"Aucune entreprise ne porte le SIREN {spaced_siren(siren)} dans le registre national."


def registered_at(company: Company, address: str) -> GraphFragment:
    company_entity_identifier = company_identifier(company.siren)
    establishments = {
        establishment.siret: establishment
        for establishment in (*company.matching_establishments, company.head_office)
        if establishment is not None
    }
    fragments = [GraphFragment((company_entity(company),))]
    for establishment in establishments.values():
        fragment = establishment_fragment(company_entity_identifier, establishment)
        if any(entity.identifier == address for entity in fragment.entities):
            fragments.append(fragment)
            if establishment.is_head_office:
                office_link = registered_office_link(company_entity_identifier, address)
                fragments.append(GraphFragment(links=(office_link,)))
    return combined(fragments)


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
        company, *other_entities = fragment.entities
        return replace(fragment, entities=(self.expanded(company), *other_entities))

    def expanded(self, entity: CollectedEntity) -> CollectedEntity:
        attributes = {**entity.attributes, EXPANDED_AT_ATTRIBUTE: self.now().isoformat()}
        return replace(entity, attributes=attributes)

    def entity_to_expand(self, identifier: str, kind: EntityKind) -> CollectedEntity:
        entity = self.graph_store.entity(identifier)
        if entity is None or entity.kind is not kind:
            raise ExpansionError(UNKNOWN_ENTITY_MESSAGE)
        return CollectedEntity(entity.identifier, entity.label, entity.attributes)

    def expand_person(self, identifier: str, *, refresh: bool = False) -> GraphChanges:
        person = self.entity_to_expand(identifier, EntityKind.PERSON)
        searched_name = SearchedName.of(person)
        changes = []
        search_pages = self.director_pages(searched_name, refresh)
        for search_page in search_pages:
            for company in search_page.companies:
                fragment = searched_name.mandates_in(company)
                if fragment.links:
                    changes.append(self.save_fragment(fragment, search_page.response))
        expanded_person = GraphFragment((self.expanded(person),))
        changes.append(self.save_fragment(expanded_person, search_pages[-1].response))
        return combined_changes(changes)

    def director_pages(
        self, searched_name: SearchedName, refresh: bool
    ) -> list[CompanySearchPage]:
        return self.every_page(
            lambda page: self.company_register.search_director(
                searched_name.last_name, searched_name.first_names, page, refresh=refresh
            )
        )

    def every_page(
        self, search_page: Callable[[int], CompanySearchPage]
    ) -> list[CompanySearchPage]:
        search_pages = [search_page(1)]
        while search_pages[-1].has_next_page and len(search_pages) < MAXIMUM_SEARCH_PAGES:
            search_pages.append(search_page(search_pages[-1].page + 1))
        return search_pages

    def expand_address(self, identifier: str, *, refresh: bool = False) -> GraphChanges:
        address = self.entity_to_expand(identifier, EntityKind.ADDRESS)
        text = str(address.attributes.get("text") or address.label)
        search_pages = self.every_page(
            lambda page: self.company_register.search(text, page, refresh=refresh)
        )
        changes = []
        for search_page in search_pages:
            for company in search_page.companies:
                fragment = registered_at(company, identifier)
                if fragment.links:
                    changes.append(self.save_fragment(fragment, search_page.response))
        expanded_address = GraphFragment((self.expanded(address),))
        changes.append(self.save_fragment(expanded_address, search_pages[-1].response))
        return combined_changes(changes)

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

    def expand_establishment(self, identifier: str, *, refresh: bool = False) -> GraphChanges:
        establishment = self.entity_to_expand(identifier, EntityKind.ESTABLISHMENT)
        siren = identifier.removeprefix(ESTABLISHMENT_PREFIX)[:SIREN_LENGTH]
        company_changes = self.expand_company(siren, refresh=refresh)
        company_entity_identifier = company_identifier(siren)
        source = self.graph_store.sources_of_entity(company_entity_identifier)[-1]
        fragment = GraphFragment(
            (self.expanded(establishment),),
            (establishment_of_link(identifier, company_entity_identifier),),
        )
        return combined_changes([company_changes, self.save_fragment(fragment, source)])
