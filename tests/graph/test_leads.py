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
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import GraphExpander
from lacis.graph.leads import Lead, unexpanded_leads
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import EntityKind, address_identifier, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseStore

SHARED_ADDRESS = address_identifier("12 RUE DES LILAS 31000 TOULOUSE")
JEAN_DUPONT = person_identifier("DUPONT", "Jean", "1980-05")
JEAN_PIERRE_DUPONT = person_identifier("DUPONT", "Jean Pierre", "1980-05")


@pytest.fixture
def http_client(
    response_store: ResponseStore, collection_log: CollectionLog
) -> Iterator[CollectorHttpClient]:
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)),
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
        now=lambda: datetime(2026, 11, 5, tzinfo=UTC),
    )


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


@pytest.fixture
def plumbers_expanded(expander: GraphExpander) -> GraphExpander:
    expander.expand_company("222222222")
    expander.expand_company("111111111")
    return expander


def test_the_leads_of_the_fake_plumbers_match_the_design_target(
    plumbers_expanded: GraphExpander, graph_store: GraphStore
) -> None:
    assert unexpanded_leads(graph_store) == [
        Lead(
            "company:333333333",
            EntityKind.COMPANY,
            "HOLDING DUPONT",
            "Connue comme dirigeante seulement",
        ),
        Lead(JEAN_DUPONT, EntityKind.PERSON, "Jean DUPONT", "D'autres mandats peuvent exister"),
        Lead(
            JEAN_PIERRE_DUPONT,
            EntityKind.PERSON,
            "Jean Pierre DUPONT",
            "D'autres mandats peuvent exister",
        ),
        Lead(
            SHARED_ADDRESS,
            EntityKind.ADDRESS,
            "12 RUE DES LILAS 31000 TOULOUSE",
            "D'autres entreprises peuvent y être domiciliées",
        ),
    ]


def test_an_expanded_entity_is_no_longer_a_lead(
    plumbers_expanded: GraphExpander, graph_store: GraphStore
) -> None:
    plumbers_expanded.expand_address(SHARED_ADDRESS)
    plumbers_expanded.expand_company("333333333")
    identifiers = [lead.identifier for lead in unexpanded_leads(graph_store)]
    assert SHARED_ADDRESS not in identifiers
    assert "company:333333333" not in identifiers


def test_establishments_and_foreign_companies_are_never_leads(
    plumbers_expanded: GraphExpander, graph_store: GraphStore
) -> None:
    kinds = {lead.kind for lead in unexpanded_leads(graph_store)}
    assert kinds <= {EntityKind.COMPANY, EntityKind.PERSON, EntityKind.ADDRESS}
    assert any(entity.kind is EntityKind.FOREIGN_COMPANY for entity in graph_store.entities())


def test_a_company_found_but_not_expanded_waits_for_its_details(
    plumbers_expanded: GraphExpander, graph_store: GraphStore
) -> None:
    plumbers_expanded.expand_person(JEAN_DUPONT)
    reasons = {lead.label: lead.reason for lead in unexpanded_leads(graph_store)}
    assert reasons["DUPONT RENOVATION"] == (
        "Établissements, dirigeants et annonces pas encore recherchés"
    )
    assert reasons["HOLDING DUPONT"] == (
        "Établissements, dirigeants et annonces pas encore recherchés"
    )


def test_a_company_added_from_a_search_is_a_lead_until_expanded(
    expander: GraphExpander, http_client: CollectorHttpClient, graph_store: GraphStore
) -> None:
    search_page = CompanyRegister(http_client).search("acme")
    expander.add_company(search_page.companies[0], search_page.response)
    [lead] = unexpanded_leads(graph_store)
    assert lead.label == "ACME PLOMBERIE"
    assert lead.reason == "Établissements, dirigeants et annonces pas encore recherchés"


def test_an_investigation_without_entities_has_no_lead(graph_store: GraphStore) -> None:
    assert unexpanded_leads(graph_store) == []
