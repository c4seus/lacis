import logging
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

from PySide6.QtCore import QObject, Signal

from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import Company, CompanyRegister, InvalidQueryError
from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT, CollectionEnvironment
from lacis.collectors.http_client import (
    COLLECTORS_LOGGER_NAME,
    DEFAULT_TIMING,
    CollectionCancelledError,
    CollectionControl,
    CollectionError,
    CollectorHttpClient,
    CollectorTiming,
)
from lacis.graph.drawing import lay_out_investigation
from lacis.graph.expansion import ExpansionError, ExpansionReport, GraphExpander
from lacis.graph.progress import ProgressTracker
from lacis.graph.register_search import search_register
from lacis.signals.configuration import SignalConfigurationError
from lacis.signals.engine import SignalEngine
from lacis.signals.recomputation import InvestigationSignals
from lacis.storage.collection_log import CollectionLog
from lacis.storage.errors import InvestigationError
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.positions import PositionStore
from lacis.storage.responses import ResponseStore, ResponseSummary

UNEXPECTED_FAILURE_MESSAGE = (
    "La collecte s'est arrêtée sur une erreur inattendue. Le journal de Lacis en donne le détail."
)
LOCK_POLL_SECONDS = 0.05
investigation_locks: dict[str, threading.Lock] = {}
investigation_locks_guard = threading.Lock()
EXPECTED_FAILURES = (CollectionError, ExpansionError, InvalidQueryError, InvestigationError)


@dataclass(frozen=True)
class CollectionSettings:
    library: InvestigationLibrary
    investigation_name: str
    environment: CollectionEnvironment = REAL_COLLECTION_ENVIRONMENT
    timing: CollectorTiming = DEFAULT_TIMING


@dataclass(frozen=True)
class CollectionSession:
    company_register: CompanyRegister
    expander: GraphExpander
    connection: sqlite3.Connection


def interruptible_sleep(cancellation: threading.Event) -> Callable[[float], None]:
    def sleep(seconds: float) -> None:
        cancellation.wait(seconds)

    return sleep


@contextmanager
def collection_session(
    settings: CollectionSettings, tracker: ProgressTracker, cancellation: threading.Event
) -> Iterator[CollectionSession]:
    with settings.library.open(settings.investigation_name) as investigation:
        connection = investigation.connection
        http_client = CollectorHttpClient(
            ResponseStore(connection),
            CollectionLog(connection),
            settings.environment.transport,
            replace(settings.timing, sleep=interruptible_sleep(cancellation)),
            CollectionControl(request_made=tracker.request_made, cancellation=cancellation),
        )
        try:
            company_register = CompanyRegister(http_client)
            expander = GraphExpander(connection, company_register, Bodacc(http_client))
            expander.entities_found = tracker.entities_found
            yield CollectionSession(company_register, expander, connection)
        finally:
            http_client.close()


type CollectionTask = Callable[[CollectionSession], object]


def investigation_lock(settings: CollectionSettings) -> threading.Lock:
    key = str(settings.library.directory_of(settings.investigation_name).resolve())
    with investigation_locks_guard:
        return investigation_locks.setdefault(key, threading.Lock())


@contextmanager
def exclusive_access(
    settings: CollectionSettings, cancellation: threading.Event
) -> Iterator[None]:
    lock = investigation_lock(settings)
    while not lock.acquire(timeout=LOCK_POLL_SECONDS):
        if cancellation.is_set():
            raise CollectionCancelledError
    try:
        yield
    finally:
        lock.release()


class BackgroundJob(QObject):
    progressed = Signal(object)
    succeeded = Signal(object)
    cancelled = Signal(object)
    failed = Signal(str)

    def __init__(
        self, settings: CollectionSettings, task: CollectionTask, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.task = task
        self.cancellation = threading.Event()
        self.worker_thread = threading.Thread(
            target=self.run, name="lacis-collection", daemon=True
        )

    def start(self) -> None:
        self.worker_thread.start()

    def cancel(self) -> None:
        self.cancellation.set()

    def is_running(self) -> bool:
        return self.worker_thread.is_alive()

    def wait(self) -> None:
        if self.worker_thread.is_alive():
            self.worker_thread.join()

    def run(self) -> None:
        try:
            tracker = ProgressTracker(self.progressed.emit)
            with (
                exclusive_access(self.settings, self.cancellation),
                collection_session(self.settings, tracker, self.cancellation) as session,
            ):
                result = self.task(session)
        except CollectionCancelledError:
            self.cancelled.emit(None)
        except EXPECTED_FAILURES as failure:
            self.failed.emit(str(failure))
        except Exception:
            logging.getLogger(COLLECTORS_LOGGER_NAME).exception("Background collection failed")
            self.failed.emit(UNEXPECTED_FAILURE_MESSAGE)
        else:
            if isinstance(result, ExpansionReport) and result.cancelled:
                self.cancelled.emit(result)
            else:
                self.succeeded.emit(result)


def search_job(settings: CollectionSettings, text: str, page: int = 1) -> BackgroundJob:
    return BackgroundJob(settings, lambda session: session.company_register.search(text, page))


def register_search_job(settings: CollectionSettings, text: str) -> BackgroundJob:
    return BackgroundJob(
        settings,
        lambda session: search_register(
            session.company_register, session.expander.graph_store, text
        ),
    )


def recompute_signals(connection: sqlite3.Connection) -> None:
    try:
        engine = SignalEngine.configured()
    except SignalConfigurationError as problem:
        logging.getLogger(COLLECTORS_LOGGER_NAME).warning(
            "Signals left to recompute later: %s", problem
        )
        return
    InvestigationSignals(connection, engine).recompute()


def with_signals_recomputed(task: CollectionTask) -> CollectionTask:
    def run(session: CollectionSession) -> object:
        result = task(session)
        recompute_signals(session.connection)
        return result

    return run


def add_company_job(
    settings: CollectionSettings, company: Company, response: ResponseSummary
) -> BackgroundJob:
    return BackgroundJob(
        settings,
        with_signals_recomputed(lambda session: session.expander.add_company(company, response)),
    )


def expansion_job(
    settings: CollectionSettings, identifier: str, depth: int = 1, *, refresh: bool = False
) -> BackgroundJob:
    return BackgroundJob(
        settings,
        with_signals_recomputed(
            lambda session: session.expander.expand(identifier, depth, refresh=refresh)
        ),
    )


def pause_unless_cancelled(cancellation: threading.Event) -> Callable[[], None]:
    def pause() -> None:
        if cancellation.is_set():
            raise CollectionCancelledError
        time.sleep(0)

    return pause


def layout_job(settings: CollectionSettings) -> BackgroundJob:
    job = BackgroundJob(settings, lambda session: None)
    pause = pause_unless_cancelled(job.cancellation)
    job.task = lambda session: lay_out_investigation(session.connection, pause)
    return job


def move_job(settings: CollectionSettings, moved: dict[str, tuple[float, float]]) -> BackgroundJob:
    return BackgroundJob(settings, lambda session: PositionStore(session.connection).move(moved))
