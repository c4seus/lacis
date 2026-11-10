from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QAccessible
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from accessibility_checks import interactive_widgets_without_accessible_name
from fake_time import FakeTime
from lacis.collectors.environment import CollectionEnvironment
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.design.theme_controller import ThemeController
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui import announcements
from lacis.ui.main_window import MainWindow
from lacis.ui.notifications import NotificationKind
from lacis.ui.register_search_list import (
    NAVIGATION_HINT,
    SEARCHING_TEXT,
    added_message,
    position_message,
)

INVESTIGATION_NAME = "faux-plombiers-31"
WAIT_MILLISECONDS = 10_000

Announcement = tuple[str, QAccessible.AnnouncementPoliteness]


def fake_timing() -> CollectorTiming:
    fake_time = FakeTime()
    return CollectorTiming(
        rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
        sleep=fake_time.sleep,
        monotonic=fake_time.clock,
    )


def environment_answering(handler: httpx.MockTransport) -> CollectionEnvironment:
    return CollectionEnvironment(handler, demo=True, timing=fake_timing())


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "Qui se cache derrière les plombiers ?")
    return library


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> list[Announcement]:
    messages: list[Announcement] = []

    def record(
        widget: QWidget,
        message: str,
        politeness: QAccessible.AnnouncementPoliteness = announcements.ASSERTIVE,
    ) -> None:
        messages.append((message, politeness))

    monkeypatch.setattr(announcements, "announce", record)
    return messages


def open_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    environment: CollectionEnvironment,
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller, environment, library)
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.activateWindow()
    qtbot.waitUntil(main_window.isActiveWindow)
    return main_window


@pytest.fixture
def main_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> Iterator[MainWindow]:
    environment = environment_answering(httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)))
    main_window = open_window(qtbot, settings, theme_controller, library, environment)
    main_window.open_investigation(INVESTIGATION_NAME)
    main_window.header_bar.search_field.setFocus()
    yield main_window
    main_window.register_search.stop()


def search_for(qtbot: QtBot, main_window: MainWindow, text: str) -> None:
    field = main_window.header_bar.search_field
    field.selectAll()
    QTest.keyClicks(field, text)
    QTest.keyClick(field, Qt.Key.Key_Return)
    wait_for_results(qtbot, main_window)


def wait_for_results(qtbot: QtBot, main_window: MainWindow) -> None:
    qtbot.waitUntil(
        lambda: main_window.register_search.search_job is None, timeout=WAIT_MILLISECONDS
    )


def titles(main_window: MainWindow) -> list[str]:
    return [row.title_label.text() for row in main_window.search_popup.rows]


def entity_identifiers(library: InvestigationLibrary) -> set[str]:
    with library.open(INVESTIGATION_NAME) as opened:
        return {entity.identifier for entity in GraphStore(opened.connection).entities()}


def press(main_window: MainWindow, key: Qt.Key) -> None:
    QTest.keyClick(main_window.header_bar.search_field, key)


def test_the_search_is_only_active_in_an_open_investigation(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    environment = environment_answering(httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)))
    main_window = open_window(qtbot, settings, theme_controller, library, environment)
    header_bar = main_window.header_bar
    assert not header_bar.search_field.isEnabled()
    main_window.open_investigation(INVESTIGATION_NAME)
    assert header_bar.search_field.isEnabled()
    assert header_bar.search_button.isEnabled()
    search_for(qtbot, main_window, "lilas")
    main_window.show_home()
    assert not header_bar.search_field.isEnabled()
    assert header_bar.search_field.text() == ""
    assert not main_window.search_popup.isVisible()


def test_results_appear_as_the_user_types(qtbot: QtBot, main_window: MainWindow) -> None:
    field = main_window.header_bar.search_field
    QTest.keyClicks(field, "lilas")
    assert main_window.register_search.delay.isActive()
    qtbot.waitUntil(lambda: len(main_window.search_popup.rows) == 3, timeout=WAIT_MILLISECONDS)
    assert main_window.search_popup.isVisible()
    assert field.hasFocus()


def test_fewer_than_three_characters_do_not_search(qtbot: QtBot, main_window: MainWindow) -> None:
    field = main_window.header_bar.search_field
    QTest.keyClicks(field, "li")
    assert not main_window.register_search.delay.isActive()
    assert not main_window.search_popup.isVisible()
    QTest.keyClick(field, Qt.Key.Key_Down)
    assert not main_window.search_popup.isVisible()


def test_enter_with_a_short_query_explains_the_minimum(
    main_window: MainWindow, heard: list[Announcement]
) -> None:
    main_window.header_bar.search_field.setText("ab")
    press(main_window, Qt.Key.Key_Return)
    popup = main_window.search_popup
    assert popup.isVisible()
    expected = "Saisissez au moins 3 caractères pour rechercher."
    assert popup.message_label.text() == expected
    assert popup.message_label.property("tone") == "problem"
    assert heard == [(expected, announcements.ASSERTIVE)]


def test_enter_searches_at_once_and_shows_each_result(
    qtbot: QtBot, main_window: MainWindow, heard: list[Announcement]
) -> None:
    field = main_window.header_bar.search_field
    field.setText("lilas")
    QTest.keyClick(field, Qt.Key.Key_Return)
    popup = main_window.search_popup
    assert popup.message_label.text() == SEARCHING_TEXT
    wait_for_results(qtbot, main_window)
    assert popup.count_label.text() == "3 résultats dans le registre national"
    assert popup.hint_label.text() == NAVIGATION_HINT
    assert titles(main_window) == ["ACME PLOMBERIE", "DUPONT SERVICES", "LILAS BOULANGERIE"]
    dupont = popup.rows[1]
    assert dupont.status_label.text() == "Fermée"
    assert dupont.status_label.property("tone") == "badge-closed"
    assert dupont.details_label.text() == (
        "222 222 222 · NAF 43.22A · 31000 TOULOUSE · créée le 02/04/2019"
    )
    assert not dupont.in_investigation_label.isVisible()
    assert dupont.action_button.text() == "Ajouter"
    assert dupont.action_button.accessibleName() == "Ajouter DUPONT SERVICES"
    assert popup.rows[0].property("current") is True
    assert heard == [("3 résultats dans le registre national.", announcements.POLITE)]
    assert interactive_widgets_without_accessible_name(main_window) == []


def test_a_search_without_result_says_so(qtbot: QtBot, main_window: MainWindow) -> None:
    search_for(qtbot, main_window, "introuvable")
    popup = main_window.search_popup
    assert popup.count_label.text() == "Aucun résultat dans le registre national"
    assert not popup.list_area.isVisible()
    assert not popup.hint_label.isVisible()


def test_the_list_opens_below_the_search_field(qtbot: QtBot, main_window: MainWindow) -> None:
    search_for(qtbot, main_window, "lilas")
    field = main_window.header_bar.search_field
    field_bottom = field.mapTo(main_window, QPoint(0, field.height())).y()
    assert main_window.search_popup.y() > field_bottom
    assert main_window.search_popup.width() >= field.width()
    main_window.resize(main_window.width() - 100, main_window.height())
    assert main_window.search_popup.x() + main_window.search_popup.width() <= (main_window.width())


def test_arrows_move_through_the_results_and_are_announced(
    qtbot: QtBot, main_window: MainWindow, heard: list[Announcement]
) -> None:
    search_for(qtbot, main_window, "lilas")
    popup = main_window.search_popup
    heard.clear()
    press(main_window, Qt.Key.Key_Down)
    press(main_window, Qt.Key.Key_Down)
    press(main_window, Qt.Key.Key_Down)
    assert popup.current_index == 2
    assert [row.property("current") for row in popup.rows] == [False, False, True]
    press(main_window, Qt.Key.Key_Up)
    assert popup.current_index == 1
    assert heard[-1] == ("DUPONT SERVICES, Fermée, 2 sur 3", announcements.POLITE)
    assert position_message(popup.rows[0].result, 1, 3) == "ACME PLOMBERIE, Active, 1 sur 3"


def test_escape_closes_the_list_and_down_opens_it_again(
    qtbot: QtBot, main_window: MainWindow
) -> None:
    search_for(qtbot, main_window, "lilas")
    press(main_window, Qt.Key.Key_Escape)
    assert not main_window.search_popup.isVisible()
    press(main_window, Qt.Key.Key_Escape)
    press(main_window, Qt.Key.Key_Down)
    wait_for_results(qtbot, main_window)
    assert main_window.search_popup.isVisible()
    assert len(main_window.search_popup.rows) == 3


def test_leaving_the_search_field_closes_the_list(qtbot: QtBot, main_window: MainWindow) -> None:
    search_for(qtbot, main_window, "lilas")
    main_window.investigation_page.back_button.setFocus()
    assert not main_window.search_popup.isVisible()


def test_enter_adds_the_current_result_to_the_investigation(
    qtbot: QtBot,
    main_window: MainWindow,
    library: InvestigationLibrary,
    heard: list[Announcement],
) -> None:
    search_for(qtbot, main_window, "lilas")
    press(main_window, Qt.Key.Key_Down)
    heard.clear()
    with qtbot.waitSignal(main_window.register_search.company_added, timeout=WAIT_MILLISECONDS):
        press(main_window, Qt.Key.Key_Return)
        assert main_window.search_popup.rows[1].action_button.text() == "Ajout…"
    row = main_window.search_popup.rows[1]
    assert entity_identifiers(library) == {"company:222222222"}
    assert row.in_investigation_label.isVisible()
    assert row.action_button.text() == "Voir"
    assert row.action_button.isEnabled()
    assert heard == [(added_message("DUPONT SERVICES"), announcements.POLITE)]
    assert added_message("X") == "X a été ajoutée à l'enquête."
    [notification] = main_window.notification_area.notifications
    assert notification.message == added_message("DUPONT SERVICES")
    assert notification.kind is NotificationKind.SUCCESS
    assert main_window.header_bar.search_field.hasFocus()
    assert main_window.investigation_page.counts_label.text() == "1 entité, 0 lien"


def test_a_click_on_add_adds_the_result(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    search_for(qtbot, main_window, "lilas")
    row = main_window.search_popup.rows[2]
    with qtbot.waitSignal(main_window.register_search.company_added, timeout=WAIT_MILLISECONDS):
        QTest.mouseClick(row.action_button, Qt.MouseButton.LeftButton)
    assert entity_identifiers(library) == {"company:555555555"}
    assert main_window.header_bar.search_field.hasFocus()


def test_a_click_on_a_row_chooses_it_but_not_twice(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    search_for(qtbot, main_window, "lilas")
    row = main_window.search_popup.rows[0]
    with qtbot.waitSignal(main_window.register_search.company_added, timeout=WAIT_MILLISECONDS):
        QTest.mouseClick(row, Qt.MouseButton.LeftButton)
        main_window.register_search.choose(row)
    QTest.mouseClick(row, Qt.MouseButton.RightButton)
    assert entity_identifiers(library) == {"company:111111111"}


def test_a_result_already_in_the_investigation_is_shown_instead_of_added(
    qtbot: QtBot, main_window: MainWindow
) -> None:
    search_for(qtbot, main_window, "lilas")
    with qtbot.waitSignal(main_window.register_search.company_added, timeout=WAIT_MILLISECONDS):
        press(main_window, Qt.Key.Key_Return)
    search_for(qtbot, main_window, "plomberie")
    row = main_window.search_popup.rows[0]
    assert row.in_investigation_label.isVisible()
    assert row.action_button.accessibleName() == "Voir ACME PLOMBERIE"
    with qtbot.waitSignal(main_window.register_search.company_shown) as shown:
        press(main_window, Qt.Key.Key_Return)
    assert shown.args == ["company:111111111", "ACME PLOMBERIE"]
    assert not main_window.search_popup.isVisible()
    page = main_window.investigation_page
    assert page.selected_entity == "company:111111111"
    assert page.selection_label.text() == "Sélection : ACME PLOMBERIE"


def test_enter_while_typing_searches_the_new_text_instead_of_choosing(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    search_for(qtbot, main_window, "lilas")
    field = main_window.header_bar.search_field
    QTest.keyClick(field, Qt.Key.Key_Backspace)
    QTest.keyClick(field, Qt.Key.Key_Return)
    wait_for_results(qtbot, main_window)
    assert entity_identifiers(library) == set()
    assert titles(main_window) == ["ACME PLOMBERIE", "DUPONT SERVICES", "LILAS BOULANGERIE"]


def test_errors_of_the_api_are_shown_in_the_list_in_french(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    heard: list[Announcement],
) -> None:
    refusing = httpx.MockTransport(lambda request: httpx.Response(400, json={"erreur": "x"}))
    main_window = open_window(
        qtbot, settings, theme_controller, library, environment_answering(refusing)
    )
    main_window.open_investigation(INVESTIGATION_NAME)
    search_for(qtbot, main_window, "lilas")
    popup = main_window.search_popup
    assert popup.isVisible()
    assert popup.message_label.text().startswith("Le service ")
    assert "a refusé la requête (erreur 400)" in popup.message_label.text()
    assert popup.message_label.property("tone") == "problem"
    assert popup.rows == []
    assert heard == [(popup.message_label.text(), announcements.ASSERTIVE)]
    main_window.register_search.stop()


def test_a_failed_addition_is_notified_as_an_error(
    qtbot: QtBot,
    main_window: MainWindow,
    library: InvestigationLibrary,
    heard: list[Announcement],
) -> None:
    search_for(qtbot, main_window, "lilas")
    library.rename(INVESTIGATION_NAME, "ailleurs")
    heard.clear()
    row = main_window.search_popup.rows[0]
    main_window.register_search.choose(row)
    qtbot.waitUntil(row.action_button.isEnabled, timeout=WAIT_MILLISECONDS)
    expected = f"L'enquête « {INVESTIGATION_NAME} » est introuvable."
    [notification] = main_window.notification_area.notifications
    assert notification.message == expected
    assert notification.kind is NotificationKind.ERROR
    assert notification.stays
    assert row.action_button.text() == "Ajouter"
    assert heard == [(expected, announcements.ASSERTIVE)]


def test_results_of_an_abandoned_search_are_ignored(qtbot: QtBot, main_window: MainWindow) -> None:
    search_for(qtbot, main_window, "lilas")
    results_before = titles(main_window)
    main_window.register_search.show_search_failure("ignorée")
    assert titles(main_window) == results_before


def test_closing_the_window_stops_the_collection(qtbot: QtBot, main_window: MainWindow) -> None:
    main_window.header_bar.search_field.setText("lilas")
    press(main_window, Qt.Key.Key_Return)
    jobs = list(main_window.register_search.started_jobs)
    main_window.close()
    assert jobs
    assert not any(job.is_running() for job in jobs)
    assert main_window.register_search.settings is None
