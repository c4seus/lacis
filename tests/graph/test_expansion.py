import sqlite3
from collections.abc import Iterator

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import GraphExpander
from lacis.graph.mapping import company_fragment
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import EntityKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseStore

DUPONT_SERVICES = "company:222222222"


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
def expander(investigation_connection: sqlite3.Connection) -> GraphExpander:
    return GraphExpander(investigation_connection)


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
