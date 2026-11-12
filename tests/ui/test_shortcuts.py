from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui.header_bar import SEARCH_HINT_RIGHT_MARGIN
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
CONTROL = Qt.KeyboardModifier.ControlModifier
ALT = Qt.KeyboardModifier.AltModifier


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, QUESTION)
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        jean = builder.person("Jean", "DUPONT")
        builder.mandate(jean, builder.company("SOCIETE ANNONCEE", date(2024, 5, 2)))
    return library


@pytest.fixture
def window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    return window


def press(key: Qt.Key, modifier: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier) -> None:
    focused = QApplication.focusWidget()
    assert isinstance(focused, QWidget)
    QTest.keyClick(focused, key, modifier)


def focus_graph(window: MainWindow) -> None:
    window.investigation_page.graph_view.setFocus()
    assert window.investigation_page.graph_view.hasFocus()


def select_company(window: MainWindow) -> str:
    page = window.investigation_page
    company = next(
        node.identifier for node in page.graph_view.drawing.nodes if node.label.startswith("SOC")
    )
    page.show_entity(company, "")
    return company


def test_slash_and_ctrl_f_go_to_the_search_with_its_text_selected(window: MainWindow) -> None:
    field = window.header_bar.search_field
    field.setText("plomberie")
    focus_graph(window)
    press(Qt.Key.Key_Slash)
    assert field.hasFocus()
    assert field.selectedText() == "plomberie"
    focus_graph(window)
    press(Qt.Key.Key_F, CONTROL)
    assert field.hasFocus()
    assert field.selectedText() == "plomberie"


def test_a_slash_typed_in_a_text_field_stays_in_the_text(window: MainWindow) -> None:
    field = window.header_bar.search_field
    field.setFocus()
    QTest.keyClicks(field, "12/2024")
    assert field.text() == "12/2024"
    entities = window.investigation_page.details_panel.entities_tab
    window.main_menu_bar.tab_actions[2].trigger()
    entities.filter_field.setFocus()
    QTest.keyClicks(entities.filter_field, "a/b")
    assert entities.filter_field.text() == "a/b"
    assert entities.filter_field.hasFocus()
    assert field.text() == "12/2024"


def test_the_shortcuts_wait_for_an_open_investigation(window: MainWindow) -> None:
    window.show_home()
    window.start_new_investigation()
    name = window.home_screen.new_investigation_panel.fields.name_field.input
    name.setFocus()
    QTest.keyClicks(name, "plombiers/31")
    QTest.keyClick(name, Qt.Key.Key_F, CONTROL)
    QTest.keyClick(name, Qt.Key.Key_E, CONTROL)
    assert name.text() == "plombiers/31"
    assert name.hasFocus()
    assert window.review_actions.expansions == {}
    window.focus_search()
    assert not window.header_bar.search_field.hasFocus()


def test_ctrl_zero_fits_the_graph(window: MainWindow) -> None:
    view = window.investigation_page.graph_view
    view.zoom_in()
    zoomed = view.transform().m11()
    window.header_bar.search_field.setFocus()
    press(Qt.Key.Key_0, CONTROL)
    assert view.transform().m11() != zoomed
    assert window.header_bar.search_field.text() == ""


def test_ctrl_e_expands_the_selected_entity(qtbot: QtBot, window: MainWindow) -> None:
    expand_action = window.main_menu_bar.expand_action
    assert not expand_action.isEnabled()
    company = select_company(window)
    assert expand_action.isEnabled()
    focus_graph(window)
    press(Qt.Key.Key_E, CONTROL)
    assert company in window.review_actions.expansions
    assert not expand_action.isEnabled()
    qtbot.waitUntil(lambda: not window.review_actions.expansions, timeout=10_000)
    assert expand_action.isEnabled()
    window.show_home()
    assert not expand_action.isEnabled()


def test_the_details_tabs_are_switched_from_the_keyboard(window: MainWindow) -> None:
    tabs = window.investigation_page.details_panel.tabs
    focus_graph(window)
    press(Qt.Key.Key_3, ALT)
    assert tabs.currentIndex() == 2
    assert tabs.tabBar().hasFocus()
    press(Qt.Key.Key_PageDown, CONTROL)
    assert tabs.currentIndex() == 3
    press(Qt.Key.Key_PageDown, CONTROL)
    assert tabs.currentIndex() == 0
    press(Qt.Key.Key_PageUp, CONTROL)
    assert tabs.currentIndex() == 3
    press(Qt.Key.Key_1, ALT)
    assert tabs.currentIndex() == 0


def test_the_search_shows_its_shortcut_until_it_has_the_focus(window: MainWindow) -> None:
    hint = window.header_bar.shortcut_hint
    field = window.header_bar.search_field
    assert hint.text() == "/"
    assert field.accessibleDescription() == "Raccourcis : / ou Ctrl+F"
    focus_graph(window)
    assert hint.isVisible()
    field.setFocus()
    assert not hint.isVisible()
    focus_graph(window)
    assert hint.isVisible()
    window.show_home()
    assert not hint.isVisible()
    window.resize(1300, 800)
    window.resize(1440, 900)
    QApplication.processEvents()
    assert field.width() - hint.geometry().right() - 1 == SEARCH_HINT_RIGHT_MARGIN
