import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtGui import QUndoCommand
from pytestqt.qtbot import QtBot

from fake_time import FakeWallClock
from lacis.history import InvestigationHistory
from lacis.identity.decision_commands import (
    RecordDecisionCommand,
    ReportedCommand,
    WithdrawDecisionCommand,
)
from lacis.storage.entities import CollectedEntity, LinkKind, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import (
    HomonymDecision,
    HomonymDecisionNotFoundError,
    HomonymDecisionStore,
    RecordedDecision,
)
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore

DECIDED_AT = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)
JEAN = person_identifier("DUPONT", "Jean", "1980-05")
JEAN_PIERRE = person_identifier("DUPONT", "Jean Pierre", "1980-05")


@pytest.fixture
def wall_clock() -> FakeWallClock:
    return FakeWallClock(DECIDED_AT)


@pytest.fixture
def graph_store(
    investigation_connection: sqlite3.Connection, response_store: ResponseStore
) -> GraphStore:
    graph_store = GraphStore(investigation_connection)
    response = response_store.save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            DECIDED_AT,
        )
    )
    graph_store.save_entity(CollectedEntity(JEAN, "Jean DUPONT"), response)
    graph_store.save_entity(CollectedEntity(JEAN_PIERRE, "Jean Pierre DUPONT"), response)
    return graph_store


@pytest.fixture
def decision_store(
    investigation_connection: sqlite3.Connection,
    graph_store: GraphStore,
    wall_clock: FakeWallClock,
) -> HomonymDecisionStore:
    return HomonymDecisionStore(investigation_connection, now=wall_clock.now)


@pytest.fixture
def history(qtbot: QtBot) -> InvestigationHistory:
    return InvestigationHistory()


def same_person_links(graph_store: GraphStore) -> int:
    return sum(link.kind is LinkKind.SAME_PERSON for link in graph_store.links())


def test_undoing_a_same_person_decision_removes_it_and_its_link(
    history: InvestigationHistory,
    decision_store: HomonymDecisionStore,
    graph_store: GraphStore,
) -> None:
    history.record(
        RecordDecisionCommand(decision_store, JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    )
    assert same_person_links(graph_store) == 1
    assert history.undoText() == "la décision d'homonyme"
    history.undo()
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) is None
    assert same_person_links(graph_store) == 0


def test_redoing_a_decision_brings_it_back_with_its_first_date(
    history: InvestigationHistory,
    decision_store: HomonymDecisionStore,
    graph_store: GraphStore,
    wall_clock: FakeWallClock,
) -> None:
    history.record(
        RecordDecisionCommand(decision_store, JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    )
    history.undo()
    wall_clock.advance(timedelta(hours=2))
    history.redo()
    recorded = decision_store.decision_between(JEAN, JEAN_PIERRE)
    assert recorded is not None
    assert recorded.decision is HomonymDecision.SAME_PERSON
    assert recorded.decided_at == DECIDED_AT
    assert same_person_links(graph_store) == 1


def test_undoing_a_changed_decision_restores_the_previous_one(
    history: InvestigationHistory,
    decision_store: HomonymDecisionStore,
    graph_store: GraphStore,
    wall_clock: FakeWallClock,
) -> None:
    history.record(
        RecordDecisionCommand(decision_store, JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    )
    wall_clock.advance(timedelta(days=1))
    history.record(
        RecordDecisionCommand(decision_store, JEAN_PIERRE, JEAN, HomonymDecision.DIFFERENT_PERSON)
    )
    assert same_person_links(graph_store) == 0
    history.undo()
    first, second = sorted((JEAN, JEAN_PIERRE))
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) == RecordedDecision(
        first, second, HomonymDecision.SAME_PERSON, DECIDED_AT
    )
    assert same_person_links(graph_store) == 1


def test_withdrawing_a_decision_can_be_undone_and_redone(
    history: InvestigationHistory,
    decision_store: HomonymDecisionStore,
    graph_store: GraphStore,
) -> None:
    decision_store.record(JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    history.record(WithdrawDecisionCommand(decision_store, JEAN, JEAN_PIERRE))
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) is None
    assert history.undoText() == "le retrait de la décision d'homonyme"
    history.undo()
    restored = decision_store.decision_between(JEAN, JEAN_PIERRE)
    assert restored is not None
    assert restored.decided_at == DECIDED_AT
    assert same_person_links(graph_store) == 1
    history.redo()
    assert decision_store.decisions() == []


def test_a_missing_decision_cannot_be_withdrawn(decision_store: HomonymDecisionStore) -> None:
    with pytest.raises(HomonymDecisionNotFoundError):
        WithdrawDecisionCommand(decision_store, JEAN, JEAN_PIERRE)


def test_collected_facts_are_never_undone(
    history: InvestigationHistory,
    decision_store: HomonymDecisionStore,
    graph_store: GraphStore,
) -> None:
    history.record(
        RecordDecisionCommand(decision_store, JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    )
    entities_before = graph_store.entities()
    history.undo()
    history.undo()
    assert graph_store.entities() == entities_before
    assert not history.canUndo()


class FailingCommand(QUndoCommand):
    def redo(self) -> None:
        raise HomonymDecisionNotFoundError

    def undo(self) -> None:
        raise HomonymDecisionNotFoundError


def test_a_reported_command_runs_the_wrapped_command(
    decision_store: HomonymDecisionStore,
) -> None:
    failures: list[Exception] = []
    recorded = RecordDecisionCommand(
        decision_store, JEAN, JEAN_PIERRE, HomonymDecision.SAME_PERSON
    )
    reported = ReportedCommand(recorded, (HomonymDecisionNotFoundError,), failures.append)
    assert reported.text() == "la décision d'homonyme"
    reported.redo()
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) is not None
    reported.undo()
    assert decision_store.decision_between(JEAN, JEAN_PIERRE) is None
    assert failures == []


def test_a_reported_command_reports_its_expected_failures() -> None:
    failures: list[Exception] = []
    reported = ReportedCommand(
        FailingCommand("échec"), (HomonymDecisionNotFoundError,), failures.append
    )
    reported.redo()
    reported.undo()
    assert [type(failure) for failure in failures] == [HomonymDecisionNotFoundError] * 2
