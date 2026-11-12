import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from pytestqt.qtbot import QtBot

from fake_time import FakeTime
from graph_scenario import plumbers_scenario
from investigation_builder import InvestigationBuilder
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
    layout_job,
    move_job,
    register_search_job,
    search_job,
)
from lacis.graph.expansion import ExpansionReport
from lacis.graph.progress import ExpansionProgress
from lacis.graph.register_search import RegisterSearchResults
from lacis.signals.refresher import SignalRefresher
from lacis.signals.store import SignalReport, SignalStore
from lacis.storage.collection_log import CollectionLog
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.positions import Position, PositionStore
from large_investigation import large_investigation

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


def test_a_job_runs_until_its_task_ends(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    release = threading.Event()
    job = BackgroundJob(settings, lambda session: release.wait(SIGNAL_TIMEOUT_MILLISECONDS))
    assert not job.is_running()
    started_jobs.append(job)
    with qtbot.waitSignal(job.succeeded, timeout=SIGNAL_TIMEOUT_MILLISECONDS):
        job.start()
        assert job.is_running()
        release.set()
    job.wait()
    assert not job.is_running()


def test_a_search_runs_in_the_background(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    search_page = run(qtbot, search_job(settings, "dupont services"), started_jobs)
    assert isinstance(search_page, CompanySearchPage)
    assert [company.siren for company in search_page.companies] == ["222222222"]


def test_a_register_search_marks_the_companies_already_in_the_investigation(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    before = run(qtbot, register_search_job(settings, "lilas"), started_jobs)
    assert isinstance(before, RegisterSearchResults)
    acme = before.results[0]
    run(qtbot, add_company_job(settings, acme.company, before.page.response), started_jobs)
    after = run(qtbot, register_search_job(settings, "lilas"), started_jobs)
    assert isinstance(after, RegisterSearchResults)
    assert [result.in_investigation for result in after.results] == [True, False, False]


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


def add_acme(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    page = run(qtbot, search_job(settings, "111111111"), started_jobs)
    assert isinstance(page, CompanySearchPage)
    run(qtbot, add_company_job(settings, page.companies[0], page.response), started_jobs)


def stored_report(library: InvestigationLibrary) -> tuple[int, SignalReport | None]:
    with library.open(INVESTIGATION_NAME) as investigation:
        store = SignalStore(investigation.connection)
        return store.revision(), store.report()


def test_an_expansion_leaves_signals_computed_for_its_result(
    qtbot: QtBot,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
    library: InvestigationLibrary,
) -> None:
    add_acme(qtbot, settings, started_jobs)
    run(qtbot, expansion_job(settings, "company:111111111"), started_jobs)
    revision, report = stored_report(library)
    assert report is not None
    assert report.revision == revision


def test_adding_a_company_leaves_signals_computed_too(
    qtbot: QtBot,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
    library: InvestigationLibrary,
) -> None:
    page = run(qtbot, search_job(settings, "lilas"), started_jobs)
    assert isinstance(page, CompanySearchPage)
    run(qtbot, add_company_job(settings, page.companies[0], page.response), started_jobs)
    revision, report = stored_report(library)
    assert report is not None
    assert report.revision == revision


def test_an_invalid_signal_configuration_does_not_fail_the_expansion(
    qtbot: QtBot,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
    isolated_configuration_directory: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    add_acme(qtbot, settings, started_jobs)
    with settings.library.open(INVESTIGATION_NAME) as investigation, investigation.connection:
        investigation.connection.execute("DELETE FROM signal_computation")
    isolated_configuration_directory.mkdir(parents=True)
    (isolated_configuration_directory / "signals.toml").write_text("[rules.inconnue]\n")
    run(qtbot, expansion_job(settings, "company:111111111"), started_jobs)
    assert stored_report(settings.library)[1] is None
    assert "Signals left to recompute later" in caplog.text


def test_the_refresher_follows_jobs(
    qtbot: QtBot,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
    library: InvestigationLibrary,
) -> None:
    add_acme(qtbot, settings, started_jobs)
    refresher = SignalRefresher(library, INVESTIGATION_NAME)
    job = expansion_job(settings, "company:111111111")
    refresher.follow_job(job)
    with qtbot.waitSignal(refresher.refreshed, timeout=SIGNAL_TIMEOUT_MILLISECONDS):
        run(qtbot, job, started_jobs)


def test_a_layout_places_new_entities_in_the_background(
    qtbot: QtBot,
    library: InvestigationLibrary,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
) -> None:
    with library.open(INVESTIGATION_NAME) as investigation:
        plumbers_scenario(InvestigationBuilder(investigation.connection))
    assert run(qtbot, layout_job(settings), started_jobs) == 9
    with library.open(INVESTIGATION_NAME) as investigation:
        assert len(PositionStore(investigation.connection).positions()) == 9
    assert run(qtbot, layout_job(settings), started_jobs) == 0


def test_a_cancelled_layout_saves_nothing(
    qtbot: QtBot,
    library: InvestigationLibrary,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
) -> None:
    with library.open(INVESTIGATION_NAME) as investigation:
        plumbers_scenario(InvestigationBuilder(investigation.connection))
    assert cancellation_of(qtbot, layout_job(settings), started_jobs) is None
    with library.open(INVESTIGATION_NAME) as investigation:
        assert PositionStore(investigation.connection).positions() == {}


def test_the_interface_stays_responsive_while_500_entities_are_laid_out(
    qtbot: QtBot,
    library: InvestigationLibrary,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
) -> None:
    with library.open(INVESTIGATION_NAME) as investigation:
        assert large_investigation(investigation.connection, 100).size == 500
    ticks: list[float] = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start()
    job = layout_job(settings)
    started_jobs.append(job)
    with qtbot.waitSignal(job.succeeded, timeout=60_000) as blocker:
        job.start()
    timer.stop()
    job.wait()
    assert blocker.args == [500]
    assert len(ticks) >= 5
    assert max(later - earlier for earlier, later in pairwise(ticks)) < 1.0


def test_jobs_on_the_same_investigation_take_turns(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    release = threading.Event()
    order: list[str] = []

    def first_task(session: CollectionSession) -> None:
        order.append("first starts")
        release.wait(SIGNAL_TIMEOUT_MILLISECONDS / 1000)
        order.append("first ends")

    first = BackgroundJob(settings, first_task)
    second = BackgroundJob(settings, lambda session: order.append("second runs"))
    started_jobs.extend([first, second])
    first.start()
    qtbot.waitUntil(lambda: order == ["first starts"])
    with qtbot.waitSignal(second.succeeded, timeout=SIGNAL_TIMEOUT_MILLISECONDS):
        second.start()
        time.sleep(0.2)
        assert order == ["first starts"]
        release.set()
    assert order == ["first starts", "first ends", "second runs"]


def test_a_job_waiting_for_its_turn_can_be_cancelled(
    qtbot: QtBot, settings: CollectionSettings, started_jobs: list[BackgroundJob]
) -> None:
    started = threading.Event()
    release = threading.Event()

    def first_task(session: CollectionSession) -> None:
        started.set()
        release.wait(SIGNAL_TIMEOUT_MILLISECONDS / 1000)

    first = BackgroundJob(settings, first_task)
    waiting = BackgroundJob(settings, lambda session: None)
    started_jobs.extend([first, waiting])
    first.start()
    assert started.wait(SIGNAL_TIMEOUT_MILLISECONDS / 1000)
    waiting.start()
    with qtbot.waitSignal(waiting.cancelled, timeout=SIGNAL_TIMEOUT_MILLISECONDS):
        waiting.cancel()
    release.set()


def test_jobs_on_other_investigations_do_not_wait(
    qtbot: QtBot,
    library: InvestigationLibrary,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
) -> None:
    library.create("autre-enquete", "")
    release = threading.Event()
    started = threading.Event()

    def first_task(session: CollectionSession) -> None:
        started.set()
        release.wait(SIGNAL_TIMEOUT_MILLISECONDS / 1000)

    first = BackgroundJob(settings, first_task)
    other = BackgroundJob(replace(settings, investigation_name="autre-enquete"), lambda s: 1)
    started_jobs.extend([first, other])
    first.start()
    assert started.wait(SIGNAL_TIMEOUT_MILLISECONDS / 1000)
    assert run(qtbot, other, started_jobs) == 1
    release.set()


def test_moved_positions_are_saved_in_the_background(
    qtbot: QtBot,
    library: InvestigationLibrary,
    settings: CollectionSettings,
    started_jobs: list[BackgroundJob],
) -> None:
    with library.open(INVESTIGATION_NAME) as investigation:
        scenario = plumbers_scenario(InvestigationBuilder(investigation.connection))
    run(qtbot, move_job(settings, {scenario.acme: (5.0, 6.0)}), started_jobs)
    with library.open(INVESTIGATION_NAME) as investigation:
        assert PositionStore(investigation.connection).positions() == {
            scenario.acme: Position(5.0, 6.0, moved_by_investigator=True)
        }
