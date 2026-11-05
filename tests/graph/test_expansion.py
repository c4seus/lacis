import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.company_register import CompanyRegister, InvalidQueryError
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import ExpansionError, GraphExpander, current_time
from lacis.graph.mapping import company_fragment
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import (
    EntityKind,
    LinkKind,
    address_identifier,
    establishment_identifier,
    person_identifier,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseStore

DUPONT_SERVICES = "company:222222222"
DUPONT_SERVICES_HEAD_OFFICE = establishment_identifier("22222222200015")
SHARED_ADDRESS = address_identifier("12 RUE DES LILAS 31000 TOULOUSE")
JEAN_DUPONT = person_identifier("DUPONT", "Jean", "1980-05")
EXPANDED_AT = datetime(2026, 11, 5, 10, 30, tzinfo=UTC)


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(FAKE_PLUMBERS_SCENARIO)


@pytest.fixture
def http_client(
    fake_api: FakeApi, response_store: ResponseStore, collection_log: CollectionLog
) -> Iterator[CollectorHttpClient]:
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(fake_api),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            monotonic=fake_time.clock,
        ),
    )
    yield client
    client.close()


@pytest.fixture
def company_register(http_client: CollectorHttpClient) -> CompanyRegister:
    return CompanyRegister(http_client)


@pytest.fixture
def expander(
    investigation_connection: sqlite3.Connection, company_register: CompanyRegister
) -> GraphExpander:
    return GraphExpander(investigation_connection, company_register, now=lambda: EXPANDED_AT)


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


def test_a_company_is_added_from_a_search_result(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("dupont services")
    [dupont_services] = search_page.companies
    changes = expander.add_company(dupont_services, search_page.response)
    assert changes.new_entities == (DUPONT_SERVICES,)
    assert changes.new_links == ()
    assert not changes.is_empty
    entity = graph_store.require_entity(DUPONT_SERVICES)
    assert entity.label == "DUPONT SERVICES"
    assert entity.attributes["siren"] == "222222222"
    assert entity.attributes["is_active"] is False
    assert graph_store.sources_of_entity(DUPONT_SERVICES) == [search_page.response]


def test_adding_a_company_does_not_expand_it(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("acme plomberie")
    expander.add_company(search_page.companies[0], search_page.response)
    assert [entity.kind for entity in graph_store.entities()] == [EntityKind.COMPANY]
    assert graph_store.links() == []


def test_adding_a_company_twice_adds_nothing_new(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("dupont services")
    expander.add_company(search_page.companies[0], search_page.response)
    changes = expander.add_company(search_page.companies[0], search_page.response)
    assert changes.is_empty
    assert len(graph_store.entities()) == 1


def test_a_fragment_saved_twice_adds_its_entities_and_links_once(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("acme plomberie")
    fragment = company_fragment(search_page.companies[0])
    changes = expander.save_fragment(fragment, search_page.response)
    assert set(changes.new_entities) == {entity.identifier for entity in fragment.entities}
    assert set(changes.new_links) == {link.identifier for link in fragment.links}
    assert len(graph_store.links()) == len(fragment.links)
    assert expander.save_fragment(fragment, search_page.response).is_empty


def test_expanding_dupont_services_gives_its_establishment_address_and_directors(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    changes = expander.expand_company("222 222 222")
    assert set(changes.new_entities) == {
        DUPONT_SERVICES,
        DUPONT_SERVICES_HEAD_OFFICE,
        SHARED_ADDRESS,
        JEAN_DUPONT,
    }
    assert {(link.source, link.kind, link.target) for link in graph_store.links()} == {
        (DUPONT_SERVICES_HEAD_OFFICE, LinkKind.ESTABLISHMENT_OF, DUPONT_SERVICES),
        (DUPONT_SERVICES_HEAD_OFFICE, LinkKind.LOCATED_AT, SHARED_ADDRESS),
        (DUPONT_SERVICES, LinkKind.REGISTERED_OFFICE, SHARED_ADDRESS),
        (JEAN_DUPONT, LinkKind.MANDATE, DUPONT_SERVICES),
    }
    assert len(changes.new_links) == 4


def test_an_expanded_company_records_when_it_was_expanded_and_from_which_response(
    expander: GraphExpander, graph_store: GraphStore, response_store: ResponseStore
) -> None:
    expander.expand_company("222222222")
    company = graph_store.require_entity(DUPONT_SERVICES)
    assert company.attributes["expanded_at"] == EXPANDED_AT.isoformat()
    assert company.attributes["closing_date"] == "2023-01-15"
    [detail_response] = response_store.summaries()
    assert graph_store.sources_of_entity(JEAN_DUPONT) == [detail_response]
    assert detail_response.parameters["q"] == "222222222"


def test_expanding_the_same_company_twice_adds_nothing_new(
    expander: GraphExpander, graph_store: GraphStore, fake_api: FakeApi
) -> None:
    expander.expand_company("222222222")
    entities_after_first_expansion = graph_store.entities()
    assert expander.expand_company("222222222").is_empty
    assert expander.expand_company("222222222", refresh=True).is_empty
    assert len(graph_store.entities()) == len(entities_after_first_expansion)
    assert len(fake_api.requests) == 2


def test_expanding_a_company_added_from_a_search_keeps_it_and_adds_the_rest(
    company_register: CompanyRegister, expander: GraphExpander
) -> None:
    search_page = company_register.search("dupont services")
    expander.add_company(search_page.companies[0], search_page.response)
    changes = expander.expand_company("222222222")
    assert DUPONT_SERVICES not in changes.new_entities
    assert JEAN_DUPONT in changes.new_entities


def test_a_second_company_at_the_same_address_shares_it(expander: GraphExpander) -> None:
    expander.expand_company("111111111")
    changes = expander.expand_company("222222222")
    assert SHARED_ADDRESS not in changes.new_entities
    assert DUPONT_SERVICES in changes.new_entities


def test_expanding_an_unknown_siren_reaches_the_caller_with_a_french_message(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    with pytest.raises(ExpansionError) as failure:
        expander.expand_company("123456780")
    assert str(failure.value) == (
        "Aucune entreprise ne porte le SIREN 123 456 780 dans le registre national."
    )
    assert graph_store.entities() == []


def test_expanding_requires_a_siren(expander: GraphExpander, fake_api: FakeApi) -> None:
    with pytest.raises(InvalidQueryError):
        expander.expand_company("ACME")
    assert fake_api.requests == []


def test_expansions_are_dated_in_utc() -> None:
    assert current_time().tzinfo is UTC
