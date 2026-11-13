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
from lacis.identity.identities import PersonIdentities
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import Attributes, CollectedEntity, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.responses import ResponseStore

ACME = "company:111111111"
DUPONT_SERVICES = "company:222222222"
HOLDING = "company:333333333"
DUPONT_RENOVATION = "company:666666666"
JEAN = person_identifier("DUPONT", "Jean", "1980-05")
JEAN_PIERRE = person_identifier("DUPONT", "Jean Pierre", "1980-05")
JEAN_MARC = person_identifier("DUPONT", "Jean Marc", "1980-05")


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


@pytest.fixture
def decision_store(investigation_connection: sqlite3.Connection) -> HomonymDecisionStore:
    return HomonymDecisionStore(
        investigation_connection, now=lambda: datetime(2026, 11, 6, tzinfo=UTC)
    )


@pytest.fixture
def plumbers_expanded(
    investigation_connection: sqlite3.Connection,
    response_store: ResponseStore,
    collection_log: CollectionLog,
) -> Iterator[GraphExpander]:
    fake_time = FakeTime()
    http_client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            monotonic=fake_time.clock,
        ),
    )
    expander = GraphExpander(
        investigation_connection, CompanyRegister(http_client), Bodacc(http_client)
    )
    expander.expand_company("222222222")
    expander.expand_company("111111111")
    yield expander
    http_client.close()


def test_without_decision_each_spelling_is_its_own_person(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    identities = PersonIdentities(graph_store, decision_store)
    assert not identities.same_person(JEAN, JEAN_PIERRE)
    assert identities.group_of(JEAN) == {JEAN}
    assert identities.common_directors(DUPONT_SERVICES, ACME) == set()


def test_confirming_the_homonyms_of_the_scenario_gives_both_companies_one_director(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    identities = PersonIdentities(graph_store, decision_store)
    assert identities.same_person(JEAN_PIERRE, JEAN)
    assert identities.group_of(JEAN_PIERRE) == {JEAN, JEAN_PIERRE}
    [director] = identities.common_directors(DUPONT_SERVICES, ACME)
    assert director == identities.representative(JEAN)
    assert identities.directed_companies(JEAN) == {DUPONT_SERVICES, ACME}


def test_probable_matches_count_only_when_a_rule_asks_for_them(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    assert (
        PersonIdentities(graph_store, decision_store).common_directors(DUPONT_SERVICES, ACME)
        == set()
    )
    with_probable = PersonIdentities(graph_store, decision_store, include_probable=True)
    assert with_probable.same_person(JEAN, JEAN_PIERRE)
    assert with_probable.common_directors(DUPONT_SERVICES, ACME)


def test_a_rejected_match_is_never_one_person_even_when_probable_ones_are_asked_for(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.DIFFERENT_PERSON)
    identities = PersonIdentities(graph_store, decision_store, include_probable=True)
    assert not identities.same_person(JEAN, JEAN_PIERRE)
    assert identities.common_directors(DUPONT_SERVICES, ACME) == set()


def test_weak_matches_are_never_taken_as_one_person(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
    response_store: ResponseStore,
) -> None:
    plumbers_expanded.expand_person(JEAN)
    unknown_birth = person_identifier("DUPONT", "Jean", None)
    attributes: Attributes = {"last_name": "DUPONT", "first_names": "Jean"}
    graph_store.save_entity(
        CollectedEntity(unknown_birth, "Jean DUPONT", attributes),
        response_store.summaries()[0],
    )
    identities = PersonIdentities(graph_store, decision_store, include_probable=True)
    assert identities.same_person(JEAN, JEAN_MARC)
    assert not identities.same_person(JEAN, unknown_birth)


def test_confirmed_people_form_one_group_across_several_decisions(
    plumbers_expanded: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    plumbers_expanded.expand_person(JEAN)
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    decision_store.record(JEAN_MARC, JEAN, HomonymDecision.SAME_PERSON)
    decision_store.record(JEAN_MARC, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    identities = PersonIdentities(graph_store, decision_store)
    assert identities.group_of(JEAN_MARC) == {JEAN, JEAN_PIERRE, JEAN_MARC}
    assert identities.same_person(JEAN_PIERRE, JEAN_MARC)
    assert identities.directed_companies(JEAN_PIERRE) == {
        DUPONT_SERVICES,
        ACME,
        HOLDING,
        DUPONT_RENOVATION,
    }
