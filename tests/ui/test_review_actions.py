import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fake_time import FakeTime
from investigation_builder import InvestigationBuilder
from lacis.collectors.company_register import CompanySearchPage
from lacis.collectors.environment import demo_collection_environment
from lacis.collectors.http_client import CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.design.theme_controller import ThemeController
from lacis.graph.background import CollectionSettings, add_company_job, search_job
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui.help_menu import HelpMenu
from lacis.ui.menu_bar import MainMenuBar
from lacis.ui.notifications import NotificationKind
from lacis.ui.review_actions import ReviewActions, decision_message, failure_message
from lacis.ui.theme_menu import ThemeMenu

INVESTIGATION_NAME = "faux-plombiers-31"
WAIT_MILLISECONDS = 10_000

type Notified = list[tuple[str, NotificationKind]]


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    return library


@pytest.fixture
def collection_settings(library: InvestigationLibrary) -> CollectionSettings:
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
def menu_bar(qtbot: QtBot, theme_controller: ThemeController) -> MainMenuBar:
    menu_bar = MainMenuBar(ThemeMenu(theme_controller), HelpMenu())
    qtbot.addWidget(menu_bar)
    return menu_bar


@pytest.fixture
def notified() -> Notified:
    return []


@pytest.fixture
def actions(
    menu_bar: MainMenuBar, collection_settings: CollectionSettings, notified: Notified
) -> Iterator[ReviewActions]:
    actions = ReviewActions(menu_bar, lambda message, kind: notified.append((message, kind)))
    actions.start(collection_settings)
    yield actions
    actions.stop()


@pytest.fixture
def people(library: InvestigationLibrary) -> tuple[str, str]:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        return builder.person("Jean", "DUPONT"), builder.person("Jean Pierre", "DUPONT")


def decision_of(library: InvestigationLibrary, people: tuple[str, str]) -> HomonymDecision | None:
    with library.open(INVESTIGATION_NAME) as opened:
        recorded = HomonymDecisionStore(opened.connection).decision_between(*people)
    return None if recorded is None else recorded.decision


def test_a_decision_is_recorded_and_can_be_undone(
    qtbot: QtBot,
    actions: ReviewActions,
    library: InvestigationLibrary,
    people: tuple[str, str],
    notified: Notified,
) -> None:
    labels = ("Jean DUPONT", "Jean Pierre DUPONT")
    with qtbot.waitSignal(actions.changed):
        actions.decide(people, labels, HomonymDecision.SAME_PERSON)
    assert decision_of(library, people) is HomonymDecision.SAME_PERSON
    menu_bar = actions.menu_bar
    assert notified == [
        (
            "Jean DUPONT et Jean Pierre DUPONT : même personne. Ctrl+Z pour annuler.",
            NotificationKind.SUCCESS,
        )
    ]
    assert menu_bar.undo_action.isEnabled()
    assert menu_bar.undo_action.text() == "&Annuler la décision d'homonyme"
    with qtbot.waitSignal(actions.changed):
        menu_bar.undo_action.trigger()
    assert decision_of(library, people) is None
    menu_bar.redo_action.trigger()
    assert decision_of(library, people) is HomonymDecision.SAME_PERSON


def test_a_failed_decision_is_reported_and_not_recorded(
    actions: ReviewActions,
    menu_bar: MainMenuBar,
    library: InvestigationLibrary,
    people: tuple[str, str],
    notified: Notified,
) -> None:
    library.rename(INVESTIGATION_NAME, "ailleurs")
    actions.decide(people, ("Jean", "Jean Pierre"), HomonymDecision.DIFFERENT_PERSON)
    assert notified == [
        (f"L'enquête « {INVESTIGATION_NAME} » est introuvable.", NotificationKind.ERROR)
    ]
    assert not menu_bar.undo_action.isEnabled()


def test_an_undo_that_fails_is_reported(
    actions: ReviewActions,
    menu_bar: MainMenuBar,
    library: InvestigationLibrary,
    people: tuple[str, str],
    notified: Notified,
) -> None:
    actions.decide(people, ("Jean", "Jean Pierre"), HomonymDecision.SAME_PERSON)
    library.rename(INVESTIGATION_NAME, "ailleurs")
    menu_bar.undo_action.trigger()
    assert notified[-1] == (
        f"L'enquête « {INVESTIGATION_NAME} » est introuvable.",
        NotificationKind.ERROR,
    )


def test_nothing_is_decided_or_expanded_once_stopped(
    menu_bar: MainMenuBar, people: tuple[str, str], library: InvestigationLibrary
) -> None:
    actions = ReviewActions(menu_bar, lambda message, kind: None)
    actions.decide(people, ("Jean", "Jean Pierre"), HomonymDecision.SAME_PERSON)
    actions.expand("company:111111111", "ACME PLOMBERIE")
    assert decision_of(library, people) is None
    assert actions.expansions == {}
    actions.stop()


def add_acme(qtbot: QtBot, collection_settings: CollectionSettings) -> None:
    search = search_job(collection_settings, "111111111")
    with qtbot.waitSignal(search.succeeded, timeout=WAIT_MILLISECONDS) as found:
        search.start()
    search.wait()
    [page] = found.args
    assert isinstance(page, CompanySearchPage)
    adding = add_company_job(collection_settings, page.companies[0], page.response)
    with qtbot.waitSignal(adding.succeeded, timeout=WAIT_MILLISECONDS):
        adding.start()
    adding.wait()


def test_an_expansion_runs_in_the_background_and_reports_what_it_found(
    qtbot: QtBot,
    actions: ReviewActions,
    collection_settings: CollectionSettings,
    library: InvestigationLibrary,
    notified: Notified,
) -> None:
    add_acme(qtbot, collection_settings)
    expanding: list[set[str]] = []
    actions.expanding_changed.connect(expanding.append)
    with qtbot.waitSignal(actions.changed, timeout=WAIT_MILLISECONDS):
        actions.expand("company:111111111", "ACME PLOMBERIE")
        actions.expand("company:111111111", "ACME PLOMBERIE")
    assert expanding == [{"company:111111111"}, set()]
    assert notified[0] == ("Extension de ACME PLOMBERIE en cours…", NotificationKind.INFORMATION)
    message, kind = notified[1]
    assert kind is NotificationKind.SUCCESS
    assert message.startswith("Extension de ACME PLOMBERIE terminée : ")
    with library.open(INVESTIGATION_NAME) as opened:
        assert len(GraphStore(opened.connection).entities()) > 1


def test_a_failed_expansion_is_reported(
    qtbot: QtBot, actions: ReviewActions, notified: Notified
) -> None:
    with qtbot.waitSignal(actions.changed, timeout=WAIT_MILLISECONDS):
        actions.expand("company:999999999", "INCONNUE")
    assert notified[-1] == (
        "Cette entité n'est pas dans l'enquête ou ne peut pas être étendue.",
        NotificationKind.ERROR,
    )


def test_leaving_cancels_the_running_expansions(
    qtbot: QtBot, actions: ReviewActions, collection_settings: CollectionSettings
) -> None:
    add_acme(qtbot, collection_settings)
    actions.expand("company:111111111", "ACME PLOMBERIE")
    job = actions.expansions["company:111111111"]
    actions.stop()
    assert actions.expansions == {}
    assert not job.is_running()
    actions.finish_expansion("company:111111111", "ACME PLOMBERIE", None)
    actions.fail_expansion("company:111111111", "Problème")


def test_messages_name_the_decision_and_the_failure() -> None:
    assert decision_message("Marie", "Marie Claire", HomonymDecision.DIFFERENT_PERSON) == (
        "Marie et Marie Claire : personnes différentes. Ctrl+Z pour annuler."
    )
    assert failure_message(ValueError("Problème")) == "Problème"
    assert failure_message(sqlite3.DatabaseError()) == (
        "La base de données de cette enquête est illisible."
    )
