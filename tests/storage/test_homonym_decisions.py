import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fake_time import FakeWallClock
from lacis.storage.entities import CollectedEntity, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import (
    HomonymDecision,
    HomonymDecisionStore,
    InvalidHomonymDecisionError,
    RecordedDecision,
    current_time,
)
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
)

DECIDED_AT = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
JEAN = person_identifier("DUPONT", "Jean", "1980-05")
JEAN_PIERRE = person_identifier("DUPONT", "Jean Pierre", "1980-05")
JEAN_MARC = person_identifier("DUPONT", "Jean Marc", "1980-05")


@pytest.fixture
def wall_clock() -> FakeWallClock:
    return FakeWallClock(DECIDED_AT)


@pytest.fixture
def decision_store(
    investigation_connection: sqlite3.Connection,
    response_store: ResponseStore,
    wall_clock: FakeWallClock,
) -> HomonymDecisionStore:
    response = response_store.save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            DECIDED_AT,
        )
    )
    graph_store = GraphStore(investigation_connection)
    for person, label in ((JEAN, "Jean DUPONT"), (JEAN_PIERRE, "Jean Pierre DUPONT")):
        graph_store.save_entity(CollectedEntity(person, label), response)
    graph_store.save_entity(CollectedEntity(JEAN_MARC, "Jean Marc DUPONT"), response)
    return HomonymDecisionStore(investigation_connection, now=wall_clock.now)


def test_a_same_person_decision_is_recorded_with_its_date(
    decision_store: HomonymDecisionStore,
) -> None:
    recorded = decision_store.record(JEAN_PIERRE, JEAN, HomonymDecision.SAME_PERSON)
    first, second = sorted((JEAN, JEAN_PIERRE))
    assert recorded == RecordedDecision(first, second, HomonymDecision.SAME_PERSON, DECIDED_AT)
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) == recorded
    assert decision_store.decision_between(JEAN_PIERRE, JEAN) == recorded


def test_a_different_person_decision_is_recorded_with_its_date(
    decision_store: HomonymDecisionStore,
) -> None:
    decision_store.record(JEAN, JEAN_MARC, HomonymDecision.DIFFERENT_PERSON)
    recorded = decision_store.decision_between(JEAN_MARC, JEAN)
    assert recorded is not None
    assert recorded.decision is HomonymDecision.DIFFERENT_PERSON
    assert recorded.decided_at == DECIDED_AT


def test_the_decisions_read_in_french() -> None:
    assert HomonymDecision.SAME_PERSON.value == "même personne"
    assert HomonymDecision.DIFFERENT_PERSON.value == "personne différente"


def test_a_new_decision_replaces_the_previous_one(
    decision_store: HomonymDecisionStore, wall_clock: FakeWallClock
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.DIFFERENT_PERSON)
    wall_clock.advance(timedelta(hours=1))
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    [recorded] = decision_store.decisions()
    assert recorded.decision is HomonymDecision.SAME_PERSON
    assert recorded.decided_at == DECIDED_AT + timedelta(hours=1)


def test_every_decision_is_listed_in_the_order_it_was_taken(
    decision_store: HomonymDecisionStore, wall_clock: FakeWallClock
) -> None:
    decision_store.record(JEAN, JEAN_MARC, HomonymDecision.DIFFERENT_PERSON)
    wall_clock.advance(timedelta(minutes=5))
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    assert [recorded.decision for recorded in decision_store.decisions()] == [
        HomonymDecision.DIFFERENT_PERSON,
        HomonymDecision.SAME_PERSON,
    ]
    assert decision_store.decided_pairs() == {
        tuple(sorted((JEAN, JEAN_MARC))),
        tuple(sorted((JEAN, JEAN_PIERRE))),
    }


def test_a_pair_without_decision_has_none(decision_store: HomonymDecisionStore) -> None:
    assert decision_store.decision_between(JEAN, JEAN_MARC) is None
    assert decision_store.decisions() == []


@pytest.mark.parametrize(
    ("first", "second"),
    [(JEAN, JEAN), (JEAN, "company:111111111"), ("address:0", JEAN_PIERRE)],
)
def test_only_two_different_people_can_be_decided_on(
    decision_store: HomonymDecisionStore, first: str, second: str
) -> None:
    with pytest.raises(InvalidHomonymDecisionError):
        decision_store.record(first, second, HomonymDecision.SAME_PERSON)


def test_a_decision_needs_people_of_the_investigation(
    decision_store: HomonymDecisionStore,
) -> None:
    stranger = person_identifier("MARTIN", "Paul", "1990-01")
    with pytest.raises(sqlite3.IntegrityError):
        decision_store.record(JEAN, stranger, HomonymDecision.DIFFERENT_PERSON)


def test_decisions_are_dated_in_utc() -> None:
    assert current_time().tzinfo is UTC
