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
from lacis.collectors.http_client import (
    CollectionControl,
    CollectionError,
    CollectorHttpClient,
    CollectorTiming,
)
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import ExpansionError, GraphChanges, GraphExpander, ignore_count
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
def control() -> CollectionControl:
    return CollectionControl()


@pytest.fixture
def http_client(
    fake_api: FakeApi,
    response_store: ResponseStore,
    collection_log: CollectionLog,
    control: CollectionControl,
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
        control,
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


def capped_expander(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    maximum_new_entities: int,
) -> GraphExpander:
    return GraphExpander(
        investigation_connection,
        CompanyRegister(http_client),
        Bodacc(http_client),
        now=lambda: EXPANDED_AT,
        maximum_new_entities=maximum_new_entities,
    )


@pytest.fixture
def expander_capped_at_two(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    dupont_services_added: None,
) -> GraphExpander:
    return capped_expander(investigation_connection, http_client, 2)


def test_an_expansion_stops_at_the_cap_of_new_entities_and_says_so(
    expander_capped_at_two: GraphExpander, graph_store: GraphStore
) -> None:
    report = expander_capped_at_two.expand(DUPONT_SERVICES)
    assert len(report.changes.new_entities) == 2
    assert len(graph_store.entities()) == 3
    assert report.cap_reached
    assert report.cap == 2
    assert report.cap_message == (
        "Extension arrêtée à 2 nouvelles entités, la limite fixée. "
        "Étendez les pistes restantes pour continuer."
    )


def test_a_company_cut_by_the_cap_stays_a_lead_with_consistent_links(
    expander_capped_at_two: GraphExpander, graph_store: GraphStore
) -> None:
    expander_capped_at_two.expand(DUPONT_SERVICES)
    assert not is_expanded(graph_store, DUPONT_SERVICES)
    known = {entity.identifier for entity in graph_store.entities()}
    assert all(link.source in known and link.target in known for link in graph_store.links())
    assert graph_store.entity(JEAN_DUPONT) is None


def test_expanding_again_after_the_cap_continues_where_it_stopped(
    expander_capped_at_two: GraphExpander, graph_store: GraphStore
) -> None:
    expander_capped_at_two.expand(DUPONT_SERVICES)
    report = expander_capped_at_two.expand(DUPONT_SERVICES)
    assert report.changes.new_entities == (JEAN_DUPONT,)
    assert not report.cap_reached
    assert is_expanded(graph_store, DUPONT_SERVICES)


@pytest.mark.parametrize("cap", [1, 4, 7])
def test_the_cap_is_never_exceeded_at_any_depth(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    graph_store: GraphStore,
    dupont_services_added: None,
    cap: int,
) -> None:
    expander = capped_expander(investigation_connection, http_client, cap)
    report = expander.expand(DUPONT_SERVICES, 3)
    assert len(report.changes.new_entities) <= cap
    assert len(graph_store.entities()) <= cap + 1
    assert report.cap_reached


def test_reaching_the_cap_stops_the_requests(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    fake_api: FakeApi,
    dupont_services_added: None,
) -> None:
    capped_expander(investigation_connection, http_client, 4).expand(DUPONT_SERVICES, 3)
    capped_requests = len(fake_api.requests)
    fake_api.requests.clear()
    expander = capped_expander(investigation_connection, http_client, 500)
    expander.expand(DUPONT_SERVICES, 3, refresh=True)
    assert capped_requests < len(fake_api.requests)


def test_an_expansion_below_the_cap_reports_no_cap(
    expander: GraphExpander, dupont_services_added: None
) -> None:
    report = expander.expand(DUPONT_SERVICES, 2)
    assert not report.cap_reached
    assert report.cap is None
    assert report.cap_message == ""


def test_a_single_pivot_outside_an_expansion_has_no_cap(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    graph_store: GraphStore,
) -> None:
    expander = capped_expander(investigation_connection, http_client, 1)
    changes = expander.expand_company("222222222")
    assert len(changes.new_entities) == 4
    assert is_expanded(graph_store, DUPONT_SERVICES)


def test_the_expander_reports_every_new_entity_it_saves(
    expander: GraphExpander, dupont_services_added: None
) -> None:
    found: list[int] = []
    expander.entities_found = found.append
    report = expander.expand(DUPONT_SERVICES, 2)
    assert sum(found) == len(report.changes.new_entities)
    assert all(count > 0 for count in found)


def test_new_entities_are_reported_to_nobody_by_default() -> None:
    ignore_count(3)


def test_a_cancelled_expansion_keeps_what_was_collected_and_stays_consistent(
    expander: GraphExpander,
    control: CollectionControl,
    graph_store: GraphStore,
    dupont_services_added: None,
) -> None:
    expander.entities_found = lambda count: control.cancellation.set()
    report = expander.expand(DUPONT_SERVICES, 3)
    assert report.cancelled
    assert JEAN_DUPONT in report.changes.new_entities
    assert graph_store.entity(JEAN_DUPONT) is not None
    known = {entity.identifier for entity in graph_store.entities()}
    assert all(link.source in known and link.target in known for link in graph_store.links())
    assert not is_expanded(graph_store, DUPONT_SERVICES)


def test_an_expansion_resumed_after_a_cancellation_completes(
    expander: GraphExpander,
    control: CollectionControl,
    graph_store: GraphStore,
    dupont_services_added: None,
) -> None:
    control.cancellation.set()
    cancelled_report = expander.expand(DUPONT_SERVICES, 2)
    assert cancelled_report.cancelled
    assert cancelled_report.changes == GraphChanges()
    control.cancellation.clear()
    report = expander.expand(DUPONT_SERVICES, 2)
    assert not report.cancelled
    assert is_expanded(graph_store, JEAN_DUPONT)
