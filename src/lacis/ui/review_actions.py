import sqlite3
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from lacis.graph.background import CollectionSettings
from lacis.history import InvestigationHistory
from lacis.identity.decision_commands import RecordDecisionCommand, ReportedCommand
from lacis.identity.library_decisions import LibraryDecisionStore
from lacis.storage.errors import InvestigationError
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionNotFoundError
from lacis.storage.investigations import UNREADABLE_DATABASE_MESSAGE
from lacis.ui.menu_bar import MainMenuBar
from lacis.ui.notifications import NotificationKind

DECISION_FAILURES = (InvestigationError, sqlite3.DatabaseError, HomonymDecisionNotFoundError)
DECISION_TEXTS = {
    HomonymDecision.SAME_PERSON: "même personne",
    HomonymDecision.DIFFERENT_PERSON: "personnes différentes",
}
UNDO_HINT = "Ctrl+Z pour annuler."


def failure_message(failure: Exception) -> str:
    if isinstance(failure, sqlite3.DatabaseError):
        return UNREADABLE_DATABASE_MESSAGE
    return str(failure)


def decision_message(first_label: str, second_label: str, decision: HomonymDecision) -> str:
    return f"{first_label} et {second_label} : {DECISION_TEXTS[decision]}. {UNDO_HINT}"


class ReviewActions(QObject):
    changed = Signal()

    def __init__(
        self,
        menu_bar: MainMenuBar,
        notify: Callable[[str, NotificationKind], object],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.menu_bar = menu_bar
        self.notify = notify
        self.settings: CollectionSettings | None = None
        self.history = InvestigationHistory(self)
        self.history.changed.connect(self.follow_history)

    def start(self, settings: CollectionSettings) -> None:
        self.stop()
        self.settings = settings
        self.menu_bar.show_history(self.history)

    def follow_history(self) -> None:
        if self.settings is not None:
            self.changed.emit()

    def stop(self) -> None:
        self.settings = None
        self.history.clear()
        self.menu_bar.show_history(None)

    def report_failure(self, failure: Exception) -> None:
        self.notify(failure_message(failure), NotificationKind.ERROR)

    def decide(
        self,
        people: tuple[str, str],
        labels: tuple[str, str],
        decision: HomonymDecision,
    ) -> None:
        if self.settings is None:
            return
        store = LibraryDecisionStore(self.settings.library, self.settings.investigation_name)
        try:
            command = RecordDecisionCommand(store, *people, decision)
            command.redo()
        except DECISION_FAILURES as failure:
            self.report_failure(failure)
            return
        self.history.record(ReportedCommand(command, DECISION_FAILURES, self.report_failure))
        self.notify(decision_message(*labels, decision), NotificationKind.SUCCESS)
