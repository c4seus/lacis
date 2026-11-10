import sqlite3
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from lacis.graph.background import BackgroundJob
from lacis.history import InvestigationHistory
from lacis.signals.configuration import SignalConfigurationError
from lacis.signals.engine import SignalEngine
from lacis.signals.recomputation import InvestigationSignals
from lacis.storage.errors import InvestigationError
from lacis.storage.investigations import UNREADABLE_DATABASE_MESSAGE, InvestigationLibrary


class SignalRefresher(QObject):
    refreshed = Signal(object)
    failed = Signal(str)

    def __init__(
        self,
        library: InvestigationLibrary,
        investigation_name: str,
        engine_factory: Callable[[], SignalEngine] = SignalEngine.configured,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.investigation_name = investigation_name
        self.engine_factory = engine_factory

    def follow(self, history: InvestigationHistory) -> None:
        history.changed.connect(self.refresh)

    def follow_job(self, job: BackgroundJob) -> None:
        job.succeeded.connect(self.refresh)

    def refresh(self) -> None:
        try:
            engine = self.engine_factory()
            with self.library.open(self.investigation_name) as opened:
                report = InvestigationSignals(opened.connection, engine).current()
        except (SignalConfigurationError, InvestigationError) as problem:
            self.failed.emit(str(problem))
            return
        except sqlite3.DatabaseError:
            self.failed.emit(UNREADABLE_DATABASE_MESSAGE)
            return
        self.refreshed.emit(report)
