from collections.abc import Iterator

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME
from lacis.ui.theme_menu import ThemeMenu


@pytest.fixture
def theme_controller(qapp: QApplication, settings: QSettings) -> Iterator[ThemeController]:
    controller = ThemeController(qapp, settings)
    yield controller
    qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")


def create_menu(qtbot: QtBot, theme_controller: ThemeController) -> ThemeMenu:
    menu = ThemeMenu(theme_controller)
    qtbot.addWidget(menu)
    return menu


def test_the_menu_offers_the_three_choices_in_french(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu = create_menu(qtbot, theme_controller)
    assert menu.title() == "&Thème"
    assert [action.text() for action in menu.actions()] == ["&Système", "&Clair", "S&ombre"]


def test_the_current_choice_is_checked(qtbot: QtBot, theme_controller: ThemeController) -> None:
    menu = create_menu(qtbot, theme_controller)
    assert [action.isChecked() for action in menu.actions()] == [True, False, False]


def test_choosing_an_entry_applies_and_checks_it(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu = create_menu(qtbot, theme_controller)
    menu.preference_actions[ThemePreference.DARK].trigger()
    assert theme_controller.preference == ThemePreference.DARK
    assert theme_controller.current_theme is DARK_THEME
    assert [action.isChecked() for action in menu.actions()] == [False, False, True]


def test_the_menu_follows_a_choice_made_elsewhere(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu = create_menu(qtbot, theme_controller)
    theme_controller.set_preference(ThemePreference.LIGHT)
    assert menu.preference_actions[ThemePreference.LIGHT].isChecked()
