from collections.abc import Iterator

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design.style_sheet import build_style_sheet
from lacis.design.theme_controller import ThemeController, theme_for_colour_scheme
from lacis.design.tokens import DARK_THEME, LIGHT_THEME


@pytest.fixture
def theme_controller(qapp: QApplication) -> Iterator[ThemeController]:
    controller = ThemeController(qapp)
    yield controller
    qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
    qapp.setStyleSheet("")


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
    colour_scheme: Qt.ColorScheme, expected_theme: object
) -> None:
    assert theme_for_colour_scheme(colour_scheme) is expected_theme


def test_the_theme_of_the_system_is_applied_at_start(
    qapp: QApplication, theme_controller: ThemeController
) -> None:
    expected_theme = theme_for_colour_scheme(qapp.styleHints().colorScheme())
    assert theme_controller.current_theme is expected_theme
    assert qapp.styleSheet() == build_style_sheet(expected_theme)


def test_the_theme_follows_the_system_when_it_turns_dark_then_light(
    qapp: QApplication, qtbot: QtBot, theme_controller: ThemeController
) -> None:
    with qtbot.waitSignal(theme_controller.theme_changed) as dark_signal:
        qapp.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert dark_signal.args == [DARK_THEME]
    assert qapp.styleSheet() == build_style_sheet(DARK_THEME)

    with qtbot.waitSignal(theme_controller.theme_changed) as light_signal:
        qapp.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Light)
    assert light_signal.args == [LIGHT_THEME]
    assert qapp.styleSheet() == build_style_sheet(LIGHT_THEME)
