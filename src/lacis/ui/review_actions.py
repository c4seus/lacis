import sqlite3
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from lacis.graph.background import (
    BackgroundJob,
    CollectionSettings,
    expansion_job,
    notices_refresh_job,
)
from lacis.graph.expansion import ExpansionReport
from lacis.history import InvestigationHistory
from lacis.identity.decision_commands import RecordDecisionCommand, ReportedCommand
from lacis.identity.library_decisions import LibraryDecisionStore
from lacis.review import expansion_message, notices_message
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
EXPANSION_STARTED_PREFIX = "Extension de "
EXPANSION_STARTED_SUFFIX = " en cours…"
NOTICES_REFRESH_STARTED_PREFIX = "Rafraîchissement des annonces de "


def failure_message(failure: Exception) -> str:
    if isinstance(failure, sqlite3.DatabaseError):
        return UNREADABLE_DATABASE_MESSAGE
    return str(failure)


def decision_message(first_label: str, second_label: str, decision: HomonymDecision) -> str:
    return f"{first_label} et {second_label} : {DECISION_TEXTS[decision]}. {UNDO_HINT}"


class ReviewActions(QObject):
    changed = Signal()
    expanding_changed = Signal(object)

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
        self.expansions: dict[str, BackgroundJob] = {}

    def start(self, settings: CollectionSettings) -> None:
        self.stop()
        self.settings = settings
        self.menu_bar.show_history(self.history)

    def follow_history(self) -> None:
        if self.settings is not None:
            self.changed.emit()

    def stop(self) -> None:
        for job in self.expansions.values():
            job.cancel()
        for job in self.expansions.values():
            job.wait()
        self.expansions = {}
        self.expanding_changed.emit(set())
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

    def expand(self, identifier: str, label: str, depth: int = 1, refresh: bool = False) -> None:
        if self.settings is None:
            return
        self.run_collection(
            identifier,
            expansion_job(self.settings, identifier, depth, refresh=refresh),
            f"{EXPANSION_STARTED_PREFIX}{label}{EXPANSION_STARTED_SUFFIX}",
            lambda report: expansion_message(label, report),
        )

    def refresh_notices(self, identifier: str, label: str) -> None:
        if self.settings is None:
            return
        self.run_collection(
            identifier,
            notices_refresh_job(self.settings, identifier),
            f"{NOTICES_REFRESH_STARTED_PREFIX}{label}{EXPANSION_STARTED_SUFFIX}",
            lambda report: notices_message(label, report),
        )

    def run_collection(
        self,
        identifier: str,
        job: BackgroundJob,
        started_message: str,
        describe: Callable[[ExpansionReport], str],
    ) -> None:
        if identifier in self.expansions:
            return
        job.succeeded.connect(lambda report: self.finish_collection(identifier, report, describe))
        job.cancelled.connect(lambda report: self.finish_collection(identifier, None, describe))
        job.failed.connect(lambda message: self.fail_expansion(identifier, message))
        self.expansions[identifier] = job
        self.expanding_changed.emit(set(self.expansions))
        self.notify(started_message, NotificationKind.INFORMATION)
        job.start()

    def forget_expansion(self, identifier: str) -> bool:
        job = self.expansions.pop(identifier, None)
        if job is None:
            return False
        job.wait()
        self.expanding_changed.emit(set(self.expansions))
        return True

    def finish_collection(
        self, identifier: str, report: object, describe: Callable[[ExpansionReport], str]
    ) -> None:
        if not self.forget_expansion(identifier):
            return
        if isinstance(report, ExpansionReport):
            self.notify(describe(report), NotificationKind.SUCCESS)
        self.changed.emit()

    def fail_expansion(self, identifier: str, message: str) -> None:
        if not self.forget_expansion(identifier):
            return
        self.notify(message, NotificationKind.ERROR)
        self.changed.emit()
