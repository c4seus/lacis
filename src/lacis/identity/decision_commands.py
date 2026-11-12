from collections.abc import Callable
from typing import Protocol

from PySide6.QtGui import QUndoCommand

from lacis.storage.homonym_decisions import (
    HomonymDecision,
    HomonymDecisionNotFoundError,
    RecordedDecision,
)

DECISION_ACTION_NAME = "la décision d'homonyme"
WITHDRAWAL_ACTION_NAME = "le retrait de la décision d'homonyme"


class DecisionStore(Protocol):
    def record(
        self, first_person: str, second_person: str, decision: HomonymDecision
    ) -> RecordedDecision: ...

    def restore(self, recorded: RecordedDecision) -> RecordedDecision: ...

    def withdraw(self, first_person: str, second_person: str) -> RecordedDecision: ...

    def decision_between(
        self, first_person: str, second_person: str
    ) -> RecordedDecision | None: ...


class RecordDecisionCommand(QUndoCommand):
    def __init__(
        self,
        decision_store: DecisionStore,
        first_person: str,
        second_person: str,
        decision: HomonymDecision,
    ) -> None:
        super().__init__(DECISION_ACTION_NAME)
        self.decision_store = decision_store
        self.people = (first_person, second_person)
        self.decision = decision
        self.previous = decision_store.decision_between(first_person, second_person)
        self.recorded: RecordedDecision | None = None

    def redo(self) -> None:
        if self.recorded is None:
            self.recorded = self.decision_store.record(*self.people, self.decision)
        else:
            self.decision_store.restore(self.recorded)

    def undo(self) -> None:
        if self.previous is None:
            self.decision_store.withdraw(*self.people)
        else:
            self.decision_store.restore(self.previous)


class WithdrawDecisionCommand(QUndoCommand):
    def __init__(
        self, decision_store: DecisionStore, first_person: str, second_person: str
    ) -> None:
        super().__init__(WITHDRAWAL_ACTION_NAME)
        withdrawn = decision_store.decision_between(first_person, second_person)
        if withdrawn is None:
            raise HomonymDecisionNotFoundError
        self.decision_store = decision_store
        self.withdrawn = withdrawn

    def redo(self) -> None:
        self.decision_store.withdraw(self.withdrawn.first_person, self.withdrawn.second_person)

    def undo(self) -> None:
        self.decision_store.restore(self.withdrawn)


class ReportedCommand(QUndoCommand):
    def __init__(
        self,
        command: QUndoCommand,
        expected_failures: tuple[type[Exception], ...],
        report_failure: Callable[[Exception], None],
    ) -> None:
        super().__init__(command.text())
        self.command = command
        self.expected_failures = expected_failures
        self.report_failure = report_failure

    def redo(self) -> None:
        self.run(self.command.redo)

    def undo(self) -> None:
        self.run(self.command.undo)

    def run(self, action: Callable[[], None]) -> None:
        try:
            action()
        except self.expected_failures as failure:
            self.report_failure(failure)
