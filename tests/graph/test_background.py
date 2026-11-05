import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fake_time import FakeTime
from lacis.collectors.company_register import CompanySearchPage
from lacis.collectors.environment import demo_collection_environment
from lacis.collectors.http_client import CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.background import (
    BackgroundJob,
    CollectionSession,
    CollectionSettings,
    add_company_job,
    expansion_job,
    interruptible_sleep,
    search_job,
)
from lacis.graph.expansion import ExpansionReport
from lacis.graph.progress import ExpansionProgress
from lacis.storage.collection_log import CollectionLog
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary

INVESTIGATION_NAME = "faux-plombiers-31"
SIGNAL_TIMEOUT_MILLISECONDS = 10_000


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "Qui se cache derrière les plombiers ?")
    return library


@pytest.fixture
def settings(library: InvestigationLibrary) -> CollectionSettings:
    fake_time = FakeTime()
    return CollectionSettings(
        library,
        INVESTIGATION_NAME,
        demo_collection_environment(),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            sleep=fake_time.sleep,
            monotonic=fake_time.clock,
        ),
    )


@pytest.fixture
def started_jobs() -> Iterator[list[BackgroundJob]]:
    jobs: list[BackgroundJob] = []
    yield jobs
    for job in jobs:
        job.wait()


def run(qtbot: QtBot, job: BackgroundJob, started_jobs: list[BackgroundJob]) -> object:
    started_jobs.append(job)
    with qtbot.waitSignal(job.succeeded, timeout=SIGNAL_TIMEOUT_MILLISECONDS) as blocker:
        job.start()
    job.wait()
    [result] = blocker.args
    return result


def failure_of(qtbot: QtBot, job: BackgroundJob, started_jobs: list[BackgroundJob]) -> str:
    started_jobs.append(job)
    with qtbot.waitSignal(job.failed, timeout=SIGNAL_TIMEOUT_MILLISECONDS) as blocker:
        job.start()
    job.wait()
    [message] = blocker.args
    return str(message)


def entity_identifiers(library: InvestigationLibrary) -> set[str]:
    with library.open(INVESTIGATION_NAME) as investigation:
        return {entity.identifier for entity in GraphStore(investigation.connection).entities()}


def test_a_task_runs_outside_the_interface_thread(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    def thread_of_the_task(session: CollectionSession) -> int:
        return threading.get_ident()

    task_thread = run(qtbot, BackgroundJob(settings, thread_of_the_task), started_jobs)
    assert task_thread != threading.get_ident()


def test_a_search_runs_in_the_background(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    search_page = run(qtbot, search_job(settings, "dupont services"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    assert [company.siren for company in search_page.companies] == ["222222222"]


def test_a_company_found_by_a_search_is_added_in_the_background(
    qtbot: QtBot,
    settings: CollectionSettings,
    library: InvestigationLibrary,
    started_jobs: list[BackgroundJob],
) -> None:
    search_page = run(qtbot, search_job(settings, "acme plomberie"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    company = search_page.companies[0]
    run(qtbot, add_company_job(settings, company, search_page.response), started_jobs)
    assert entity_identifiers(library) == {"company:111111111"}


def test_an_expansion_runs_in_the_background(
    qtbot: QtBot,
    settings: CollectionSettings,
    library: InvestigationLibrary,
    started_jobs: list[BackgroundJob],
) -> None:
    search_page = run(qtbot, search_job(settings, "222222222"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    run(
        qtbot,
        add_company_job(settings, search_page.companies[0], search_page.response),
        started_jobs,
    )
    report = run(qtbot, expansion_job(settings, "company:222222222", 2), started_jobs)
    assert isinstance(report, ExpansionReport)
    assert "company:111111111" in report.changes.new_entities
    assert "company:111111111" in entity_identifiers(library)


def test_an_expected_failure_reaches_the_interface_as_a_french_message(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    message = failure_of(qtbot, expansion_job(settings, "company:222222222", 5), started_jobs)
    assert message == "La profondeur d'extension doit être comprise entre 1 et 3."
    assert failure_of(qtbot, search_job(settings, " "), started_jobs) == (
        "Saisissez un nom, un SIREN, un SIRET, un dirigeant ou une adresse."
    )


def test_a_missing_investigation_is_reported(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    missing = CollectionSettings(settings.library, "enquete-absente", settings.environment)
    assert failure_of(qtbot, search_job(missing, "acme"), started_jobs) == (
        "L'enquête « enquete-absente » est introuvable."
    )


def test_an_unexpected_failure_is_logged_and_reported_without_details(
    qtbot: QtBot,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
    caplog: pytest.LogCaptureFixture,
) -> None:
    def broken_task(session: CollectionSession) -> object:
        raise RuntimeError("bug")

    message = failure_of(qtbot, BackgroundJob(settings, broken_task), started_jobs)
    assert message == (
        "La collecte s'est arrêtée sur une erreur inattendue. "
        "Le journal de Lacis en donne le détail."
    )
    assert "Background collection failed" in caplog.text


def test_waiting_for_a_job_returns_once_its_task_is_done(settings: CollectionSettings) -> None:
    release = threading.Event()
    done: list[bool] = []

    def slow_task(session: CollectionSession) -> None:
        release.wait(timeout=5)
        done.append(True)

    job = BackgroundJob(settings, slow_task)
    job.start()
    assert job.worker_thread.is_alive()
    release.set()
    job.wait()
    assert done == [True]
    assert not job.worker_thread.is_alive()


def test_an_expansion_reports_its_progress(
    qtbot: QtBot,
    settings: CollectionSettings,
    library: InvestigationLibrary,
    started_jobs: list[BackgroundJob],
) -> None:
    search_page = run(qtbot, search_job(settings, "222222222"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    run(
        qtbot,
        add_company_job(settings, search_page.companies[0], search_page.response),
        started_jobs,
    )
    job = expansion_job(settings, "company:222222222", 2)
    reports: list[ExpansionProgress] = []
    job.progressed.connect(reports.append)
    report = run(qtbot, job, started_jobs)
    assert isinstance(report, ExpansionReport)
    assert reports[-1].new_entities == len(report.changes.new_entities)
    assert reports[-1].requests_made == network_requests(library) - 1
    assert [progress.requests_made for progress in reports] == sorted(
        progress.requests_made for progress in reports
    )


def network_requests(library: InvestigationLibrary) -> int:
    with library.open(INVESTIGATION_NAME) as investigation:
        entries = CollectionLog(investigation.connection).entries()
        return sum(not entry.request.served_from_cache for entry in entries)


def cancellation_of(qtbot: QtBot, job: BackgroundJob, started_jobs: list[BackgroundJob]) -> object:
    started_jobs.append(job)
    job.cancel()
    with qtbot.waitSignal(job.cancelled, timeout=SIGNAL_TIMEOUT_MILLISECONDS) as blocker:
        job.start()
    job.wait()
    [result] = blocker.args
    return result


def test_a_cancelled_search_reports_its_cancellation(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    assert cancellation_of(qtbot, search_job(settings, "acme"), started_jobs) is None


def test_a_cancelled_expansion_reports_what_it_kept(
    qtbot: QtBot,
    settings: CollectionSettings,
    library: InvestigationLibrary,
    started_jobs: list[BackgroundJob],
) -> None:
    search_page = run(qtbot, search_job(settings, "222222222"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    run(
        qtbot,
        add_company_job(settings, search_page.companies[0], search_page.response),
        started_jobs,
    )
    report = cancellation_of(
        qtbot, expansion_job(settings, "company:222222222", 3, refresh=True), started_jobs
    )
    assert isinstance(report, ExpansionReport)
    assert report.cancelled
    assert entity_identifiers(library) == {"company:222222222"}


def test_a_waiting_job_wakes_up_when_cancelled() -> None:
    cancellation = threading.Event()
    sleep = interruptible_sleep(cancellation)
    cancellation.set()
    started = time.monotonic()
    sleep(30)
    assert time.monotonic() - started < 5
