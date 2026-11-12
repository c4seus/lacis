import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fake_time import FakeTime
from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.collectors.http_client import CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.design.theme_controller import ThemeController
from lacis.graph.background import CollectionSettings
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


def test_nothing_is_decided_once_stopped(
    menu_bar: MainMenuBar, people: tuple[str, str], library: InvestigationLibrary
) -> None:
    actions = ReviewActions(menu_bar, lambda message, kind: None)
    actions.decide(people, ("Jean", "Jean Pierre"), HomonymDecision.SAME_PERSON)
    assert decision_of(library, people) is None
    actions.stop()


def test_messages_name_the_decision_and_the_failure() -> None:
    assert decision_message("Marie", "Marie Claire", HomonymDecision.DIFFERENT_PERSON) == (
        "Marie et Marie Claire : personnes différentes. Ctrl+Z pour annuler."
    )
    assert failure_message(ValueError("Problème")) == "Problème"
    assert failure_message(sqlite3.DatabaseError()) == (
        "La base de données de cette enquête est illisible."
    )
