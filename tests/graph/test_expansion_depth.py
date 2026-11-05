import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectionError, CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import ExpansionError, GraphChanges, GraphExpander
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import (
    address_identifier,
    establishment_identifier,
    foreign_company_identifier,
    person_identifier,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseSource, ResponseStore

EXPANDED_AT = datetime(2026, 11, 5, 10, 30, tzinfo=UTC)
ACME = "company:111111111"
DUPONT_SERVICES = "company:222222222"
HOLDING = "company:333333333"
SHARED_ADDRESS = address_identifier("12 RUE DES LILAS 31000 TOULOUSE")
JEAN_DUPONT = person_identifier("DUPONT", "Jean", "1980-05")


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
def expander(
    investigation_connection: sqlite3.Connection, http_client: CollectorHttpClient
) -> GraphExpander:
    return GraphExpander(
        investigation_connection,
        CompanyRegister(http_client),
        Bodacc(http_client),
        now=lambda: EXPANDED_AT,
    )


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


@pytest.fixture
def dupont_services_added(expander: GraphExpander, http_client: CollectorHttpClient) -> None:
    search_page = CompanyRegister(http_client).search("222222222")
    expander.add_company(search_page.companies[0], search_page.response)


def is_expanded(graph_store: GraphStore, identifier: str) -> bool:
    return "expanded_at" in graph_store.require_entity(identifier).attributes


@pytest.mark.parametrize("depth", [0, 4])
def test_the_depth_goes_from_one_to_three(
    expander: GraphExpander, dupont_services_added: None, depth: int
) -> None:
    with pytest.raises(ExpansionError) as failure:
        expander.expand(DUPONT_SERVICES, depth)
    assert str(failure.value) == ("La profondeur d'extension doit être comprise entre 1 et 3.")


def test_a_depth_one_expansion_expands_only_the_chosen_entity(
    expander: GraphExpander, graph_store: GraphStore, dupont_services_added: None
) -> None:
    report = expander.expand(DUPONT_SERVICES)
    assert JEAN_DUPONT in report.changes.new_entities
    assert report.failures == ()
    assert is_expanded(graph_store, DUPONT_SERVICES)
    assert not is_expanded(graph_store, JEAN_DUPONT)
    assert not is_expanded(graph_store, SHARED_ADDRESS)


def test_a_depth_two_expansion_expands_the_entities_found_at_depth_one(
    expander: GraphExpander, graph_store: GraphStore, dupont_services_added: None
) -> None:
    report = expander.expand(DUPONT_SERVICES, 2)
    assert is_expanded(graph_store, JEAN_DUPONT)
    assert is_expanded(graph_store, SHARED_ADDRESS)
    assert {ACME, HOLDING} <= set(report.changes.new_entities)
    assert not is_expanded(graph_store, ACME)
    assert not is_expanded(graph_store, HOLDING)


def test_a_depth_three_expansion_goes_one_step_further(
    expander: GraphExpander, graph_store: GraphStore, dupont_services_added: None
) -> None:
    report = expander.expand(DUPONT_SERVICES, 3)
    assert is_expanded(graph_store, ACME)
    assert is_expanded(graph_store, HOLDING)
    assert foreign_company_identifier("DUPONT INVEST LTD", "") in report.changes.new_entities


def test_expanding_an_expanded_graph_again_adds_nothing(
    expander: GraphExpander, dupont_services_added: None
) -> None:
    expander.expand(DUPONT_SERVICES, 2)
    assert expander.expand(DUPONT_SERVICES, 2).changes == GraphChanges()


def test_a_failure_beyond_the_chosen_entity_is_reported_without_stopping(
    expander: GraphExpander,
    graph_store: GraphStore,
    dupont_services_added: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_addresses(identifier: str, *, refresh: bool = False) -> GraphChanges:
        raise CollectionError(
            "Le service Recherche d'entreprises ne répond pas.",
            ResponseSource.COMPANY_REGISTER,
            None,
        )

    monkeypatch.setattr(expander, "expand_address", fail_on_addresses)
    report = expander.expand(DUPONT_SERVICES, 2)
    assert report.failures == (
        "12 RUE DES LILAS 31000 TOULOUSE : Le service Recherche d'entreprises ne répond pas.",
    )
    assert is_expanded(graph_store, JEAN_DUPONT)
    assert not is_expanded(graph_store, SHARED_ADDRESS)


def test_a_failure_on_the_chosen_entity_reaches_the_caller(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    with pytest.raises(ExpansionError):
        expander.expand(DUPONT_SERVICES)
    assert graph_store.entities() == []


def test_a_foreign_company_cannot_be_expanded(
    expander: GraphExpander, dupont_services_added: None
) -> None:
    expander.expand(DUPONT_SERVICES)
    with pytest.raises(ExpansionError):
        expander.expand(foreign_company_identifier("DUPONT INVEST LTD", ""))


def test_any_entity_of_the_investigation_can_be_the_starting_point(
    expander: GraphExpander, graph_store: GraphStore, dupont_services_added: None
) -> None:
    expander.expand(DUPONT_SERVICES)
    head_office = establishment_identifier("22222222200015")
    expander.expand(head_office)
    assert is_expanded(graph_store, head_office)
    expander.expand(SHARED_ADDRESS)
    assert is_expanded(graph_store, SHARED_ADDRESS)
