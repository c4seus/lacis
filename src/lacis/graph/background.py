import logging
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import Company, CompanyRegister, InvalidQueryError
from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT, CollectionEnvironment
from lacis.collectors.http_client import (
    COLLECTORS_LOGGER_NAME,
    DEFAULT_TIMING,
    CollectionError,
    CollectorHttpClient,
    CollectorTiming,
)
from lacis.graph.expansion import ExpansionError, GraphExpander
from lacis.storage.collection_log import CollectionLog
from lacis.storage.errors import InvestigationError
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.responses import ResponseStore, ResponseSummary

UNEXPECTED_FAILURE_MESSAGE = (
    "La collecte s'est arrêtée sur une erreur inattendue. Le journal de Lacis en donne le détail."
)
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


@contextmanager
def collection_session(settings: CollectionSettings) -> Iterator[CollectionSession]:
    with settings.library.open(settings.investigation_name) as investigation:
        connection = investigation.connection
        http_client = CollectorHttpClient(
            ResponseStore(connection),
            CollectionLog(connection),
            settings.environment.transport,
            settings.timing,
        )
        try:
            company_register = CompanyRegister(http_client)
            expander = GraphExpander(connection, company_register, Bodacc(http_client))
            yield CollectionSession(company_register, expander)
        finally:
            http_client.close()


type CollectionTask = Callable[[CollectionSession], object]


class BackgroundJob(QObject):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(
        self, settings: CollectionSettings, task: CollectionTask, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.task = task
        self.worker_thread = threading.Thread(
            target=self.run, name="lacis-collection", daemon=True
        )

    def start(self) -> None:
        self.worker_thread.start()

    def wait(self) -> None:
        if self.worker_thread.is_alive():
            self.worker_thread.join()

    def run(self) -> None:
        try:
            with collection_session(self.settings) as session:
                result = self.task(session)
        except EXPECTED_FAILURES as failure:
            self.failed.emit(str(failure))
        except Exception:
            logging.getLogger(COLLECTORS_LOGGER_NAME).exception("Background collection failed")
            self.failed.emit(UNEXPECTED_FAILURE_MESSAGE)
        else:
            self.succeeded.emit(result)


def search_job(settings: CollectionSettings, text: str, page: int = 1) -> BackgroundJob:
    return BackgroundJob(settings, lambda session: session.company_register.search(text, page))


def add_company_job(
    settings: CollectionSettings, company: Company, response: ResponseSummary
) -> BackgroundJob:
    return BackgroundJob(settings, lambda session: session.expander.add_company(company, response))


def expansion_job(
    settings: CollectionSettings, identifier: str, depth: int = 1, *, refresh: bool = False
) -> BackgroundJob:
    return BackgroundJob(
        settings, lambda session: session.expander.expand(identifier, depth, refresh=refresh)
    )
