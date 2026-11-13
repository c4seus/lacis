from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design.style_sheet import build_style_sheet
from lacis.design.theme_controller import (
    THEME_PREFERENCE_SETTING_KEY,
    ThemeController,
    ThemePreference,
    read_theme_preference,
    theme_for_colour_scheme,
)
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme

ControllerFactory = Callable[[], ThemeController]


@pytest.fixture
def create_theme_controller(
    qapp: QApplication, settings: QSettings
) -> Iterator[ControllerFactory]:
    created_controllers: list[ThemeController] = []

    def create() -> ThemeController:
        controller = ThemeController(qapp, settings)
        created_controllers.append(controller)
        return controller

    yield create
    for controller in created_controllers:
        qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")


def system_turns(qapp: QApplication, colour_scheme: Qt.ColorScheme) -> None:
    qapp.styleHints().colorSchemeChanged.emit(colour_scheme)


@pytest.mark.parametrize(
    ("colour_scheme", "expected_theme"),
    [
        (Qt.ColorScheme.Light, LIGHT_THEME),
        (Qt.ColorScheme.Dark, DARK_THEME),
        (Qt.ColorScheme.Unknown, LIGHT_THEME),
    ],
    ids=["light", "dark", "unknown"],
)
def test_each_system_colour_scheme_has_its_theme(
    colour_scheme: Qt.ColorScheme, expected_theme: Theme
) -> None:
    assert theme_for_colour_scheme(colour_scheme) is expected_theme


def test_without_a_choice_the_theme_of_the_system_is_used(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    expected_theme = theme_for_colour_scheme(qapp.styleHints().colorScheme())
    assert theme_controller.preference == ThemePreference.SYSTEM
    assert theme_controller.current_theme is expected_theme
    assert qapp.styleSheet() == build_style_sheet(expected_theme)


def test_without_a_choice_the_theme_follows_the_system_while_running(
    qapp: QApplication, qtbot: QtBot, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    with qtbot.waitSignal(theme_controller.theme_changed) as dark_signal:
        system_turns(qapp, Qt.ColorScheme.Dark)
    assert dark_signal.args == [DARK_THEME]
    assert qapp.styleSheet() == build_style_sheet(DARK_THEME)

    with qtbot.waitSignal(theme_controller.theme_changed) as light_signal:
        system_turns(qapp, Qt.ColorScheme.Light)
    assert light_signal.args == [LIGHT_THEME]
    assert qapp.styleSheet() == build_style_sheet(LIGHT_THEME)


@pytest.mark.parametrize(
    ("preference", "forced_theme", "other_system_scheme"),
    [
        (ThemePreference.LIGHT, LIGHT_THEME, Qt.ColorScheme.Dark),
        (ThemePreference.DARK, DARK_THEME, Qt.ColorScheme.Light),
    ],
    ids=["light", "dark"],
)
def test_a_forced_theme_ignores_the_system(
    qapp: QApplication,
    create_theme_controller: ControllerFactory,
    preference: ThemePreference,
    forced_theme: Theme,
    other_system_scheme: Qt.ColorScheme,
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_preference(preference)
    system_turns(qapp, other_system_scheme)
    assert theme_controller.current_theme is forced_theme
    assert qapp.styleSheet() == build_style_sheet(forced_theme)


@pytest.mark.parametrize("preference", list(ThemePreference), ids=str)
def test_the_choice_stays_in_place_after_a_restart(
    qapp: QApplication,
    create_theme_controller: ControllerFactory,
    preference: ThemePreference,
) -> None:
    create_theme_controller().set_preference(preference)
    restarted_controller = create_theme_controller()
    assert restarted_controller.preference == preference


def test_a_forced_dark_theme_is_applied_again_after_a_restart(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    create_theme_controller().set_preference(ThemePreference.DARK)
    qapp.setStyleSheet("")
    restarted_controller = create_theme_controller()
    assert restarted_controller.current_theme is DARK_THEME
    assert qapp.styleSheet() == build_style_sheet(DARK_THEME)


def test_going_back_to_the_system_choice_follows_the_system_again(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_preference(ThemePreference.LIGHT)
    theme_controller.set_preference(ThemePreference.SYSTEM)
    system_turns(qapp, Qt.ColorScheme.Dark)
    assert theme_controller.current_theme is DARK_THEME


def test_changing_the_choice_announces_it(
    qtbot: QtBot, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    with qtbot.waitSignal(theme_controller.preference_changed) as preference_signal:
        theme_controller.set_preference(ThemePreference.DARK)
    assert preference_signal.args == [ThemePreference.DARK]


@pytest.mark.parametrize("stored_value", [None, "", "blue", 3], ids=repr)
def test_an_unknown_stored_choice_falls_back_to_the_system(
    settings: QSettings, stored_value: object
) -> None:
    if stored_value is not None:
        settings.setValue(THEME_PREFERENCE_SETTING_KEY, stored_value)
    assert read_theme_preference(settings) == ThemePreference.SYSTEM


@pytest.mark.parametrize(
    ("preference", "theme"),
    [(ThemePreference.LIGHT, LIGHT_THEME), (ThemePreference.DARK, DARK_THEME)],
    ids=["light", "dark"],
)
def test_links_take_the_accent_colour_of_the_theme(
    qapp: QApplication,
    create_theme_controller: ControllerFactory,
    preference: ThemePreference,
    theme: Theme,
) -> None:
    create_theme_controller().set_preference(preference)
    for role in (QPalette.ColorRole.Link, QPalette.ColorRole.LinkVisited):
        assert qapp.palette().color(role) == QColor(theme.colours.accent)
