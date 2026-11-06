import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fake_time import FakeWallClock
from lacis.storage.entities import CollectedEntity, Link, LinkKind, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import (
    HomonymDecision,
    HomonymDecisionNotFoundError,
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


@pytest.mark.parametrize(
    "decision", [HomonymDecision.SAME_PERSON, HomonymDecision.DIFFERENT_PERSON]
)
def test_a_decision_can_be_undone(
    decision_store: HomonymDecisionStore, decision: HomonymDecision
) -> None:
    recorded = decision_store.record(JEAN, JEAN_PIERRE, decision)
    assert decision_store.undo(JEAN_PIERRE, JEAN) == recorded
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) is None
    assert decision_store.decisions() == []


def test_undoing_a_decision_leaves_the_others(decision_store: HomonymDecisionStore) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    decision_store.record(JEAN, JEAN_MARC, HomonymDecision.DIFFERENT_PERSON)
    decision_store.undo(JEAN, JEAN_MARC)
    [remaining] = decision_store.decisions()
    assert remaining.decision is HomonymDecision.SAME_PERSON


def test_undoing_a_missing_decision_is_reported_in_french(
    decision_store: HomonymDecisionStore,
) -> None:
    with pytest.raises(HomonymDecisionNotFoundError) as failure:
        decision_store.undo(JEAN, JEAN_MARC)
    assert str(failure.value) == "Aucune décision n'a été prise sur ces deux personnes."


def same_person_links(investigation_connection: sqlite3.Connection) -> list[Link]:
    return [
        link
        for link in GraphStore(investigation_connection).links()
        if link.kind is LinkKind.SAME_PERSON
    ]


def test_a_confirmed_match_adds_a_same_person_link(
    decision_store: HomonymDecisionStore, investigation_connection: sqlite3.Connection
) -> None:
    decision_store.record(JEAN_PIERRE, JEAN, HomonymDecision.SAME_PERSON)
    [link] = same_person_links(investigation_connection)
    assert {link.source, link.target} == {JEAN, JEAN_PIERRE}
    assert link.first_collected_at == DECIDED_AT
    assert GraphStore(investigation_connection).sources_of_link(link.identifier) == []


def test_confirming_twice_keeps_one_link_dated_by_the_last_decision(
    decision_store: HomonymDecisionStore,
    investigation_connection: sqlite3.Connection,
    wall_clock: FakeWallClock,
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    wall_clock.advance(timedelta(days=1))
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    [link] = same_person_links(investigation_connection)
    assert link.first_collected_at == DECIDED_AT
    assert link.last_collected_at == DECIDED_AT + timedelta(days=1)


def test_a_rejected_match_has_no_same_person_link(
    decision_store: HomonymDecisionStore, investigation_connection: sqlite3.Connection
) -> None:
    decision_store.record(JEAN, JEAN_MARC, HomonymDecision.DIFFERENT_PERSON)
    assert same_person_links(investigation_connection) == []


def test_rejecting_a_confirmed_match_removes_its_link(
    decision_store: HomonymDecisionStore, investigation_connection: sqlite3.Connection
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.DIFFERENT_PERSON)
    assert same_person_links(investigation_connection) == []


def test_undoing_a_confirmed_match_removes_its_link(
    decision_store: HomonymDecisionStore, investigation_connection: sqlite3.Connection
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    decision_store.undo(JEAN, JEAN_PIERRE)
    assert same_person_links(investigation_connection) == []
