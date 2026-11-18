from collections.abc import Callable, Iterator

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design import theme_controller as theme_controller_module
from lacis.design.style_sheet import build_style_sheet
from lacis.design.theme_controller import (
    DEFAULT_TEXT_SIZE,
    TEXT_SIZE_SETTING_KEY,
    TEXT_SIZES,
    THEME_PREFERENCE_SETTING_KEY,
    ThemeController,
    ThemePreference,
    read_text_size,
    read_theme_preference,
    theme_for_colour_scheme,
)
from lacis.design.tokens import (
    DARK_THEME,
    HIGH_CONTRAST_DARK_THEME,
    HIGH_CONTRAST_LIGHT_THEME,
    LIGHT_THEME,
    Theme,
)

ControllerFactory = Callable[[], ThemeController]


@pytest.fixture
def create_theme_controller(
    qapp: QApplication, settings: QSettings
) -> Iterator[ControllerFactory]:
    created_controllers: list[ThemeController] = []
    font = qapp.font()

    def create() -> ThemeController:
        controller = ThemeController(qapp, settings)
        created_controllers.append(controller)
        return controller

    yield create
    for controller in created_controllers:
        qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
        qapp.styleHints().accessibility().contrastPreferenceChanged.disconnect(
            controller.follow_system_contrast
        )
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")
    qapp.setFont(font)


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


def test_the_text_size_is_designed_size_by_default(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    assert theme_controller.text_size == DEFAULT_TEXT_SIZE == 100
    assert theme_controller.text_scale == 1.0
    assert qapp.font().pixelSize() == LIGHT_THEME.font_sizes.body


def test_a_larger_text_size_enlarges_every_text_of_the_theme(
    qtbot: QtBot, qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_preference(ThemePreference.DARK)
    with qtbot.waitSignal(theme_controller.text_size_changed) as changed:
        theme_controller.set_text_size(200)
    assert changed.args == [200]
    larger = DARK_THEME.with_text_scale(2)
    assert theme_controller.current_theme == larger
    assert theme_controller.base_theme is DARK_THEME
    assert qapp.font().pixelSize() == 28
    assert qapp.styleSheet() == build_style_sheet(larger)
    theme_controller.set_preference(ThemePreference.LIGHT)
    assert theme_controller.current_theme == LIGHT_THEME.with_text_scale(2)


def test_the_text_size_stays_in_place_after_a_restart(
    settings: QSettings, create_theme_controller: ControllerFactory
) -> None:
    create_theme_controller().set_text_size(150)
    assert settings.value(TEXT_SIZE_SETTING_KEY) == 150
    restarted_controller = create_theme_controller()
    assert restarted_controller.text_size == 150
    assert restarted_controller.current_theme.font_sizes.body == 21


@pytest.mark.parametrize("stored_value", ["énorme", "120", 300, None], ids=str)
def test_an_unknown_stored_text_size_falls_back_to_the_designed_size(
    settings: QSettings, stored_value: object
) -> None:
    if stored_value is not None:
        settings.setValue(TEXT_SIZE_SETTING_KEY, stored_value)
    assert read_text_size(settings) == DEFAULT_TEXT_SIZE


def test_an_unknown_text_size_is_not_applied(create_theme_controller: ControllerFactory) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_text_size(130)
    assert theme_controller.text_size == DEFAULT_TEXT_SIZE
    assert TEXT_SIZES == (100, 125, 150, 175, 200)


def test_the_text_size_adds_to_the_font_size_of_the_system(
    monkeypatch: pytest.MonkeyPatch, create_theme_controller: ControllerFactory
) -> None:
    monkeypatch.setattr(theme_controller_module, "system_text_scale", lambda: 1.2)
    theme_controller = create_theme_controller()
    assert theme_controller.current_theme.font_sizes.body == 17
    theme_controller.set_text_size(200)
    assert theme_controller.text_scale == pytest.approx(2.4)
    assert theme_controller.current_theme.font_sizes.body == 34


def system_contrast_turns(qapp: QApplication, contrast: Qt.ContrastPreference) -> None:
    qapp.styleHints().accessibility().contrastPreferenceChanged.emit(contrast)


@pytest.mark.parametrize(
    ("colour_scheme", "expected_theme"),
    [
        (Qt.ColorScheme.Light, HIGH_CONTRAST_LIGHT_THEME),
        (Qt.ColorScheme.Dark, HIGH_CONTRAST_DARK_THEME),
        (Qt.ColorScheme.Unknown, HIGH_CONTRAST_LIGHT_THEME),
    ],
    ids=["light", "dark", "unknown"],
)
def test_each_system_colour_scheme_has_its_high_contrast_theme(
    colour_scheme: Qt.ColorScheme, expected_theme: Theme
) -> None:
    assert theme_for_colour_scheme(colour_scheme, high_contrast=True) is expected_theme


def test_without_a_choice_high_contrast_follows_the_system(
    qapp: QApplication, qtbot: QtBot, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    system_turns(qapp, Qt.ColorScheme.Dark)
    with qtbot.waitSignal(theme_controller.theme_changed) as high_contrast_signal:
        system_contrast_turns(qapp, Qt.ContrastPreference.HighContrast)
    assert high_contrast_signal.args == [HIGH_CONTRAST_DARK_THEME]
    assert theme_controller.high_contrast
    system_turns(qapp, Qt.ColorScheme.Light)
    assert theme_controller.current_theme is HIGH_CONTRAST_LIGHT_THEME
    assert qapp.styleSheet() == build_style_sheet(HIGH_CONTRAST_LIGHT_THEME)
    system_contrast_turns(qapp, Qt.ContrastPreference.NoPreference)
    assert theme_controller.current_theme is LIGHT_THEME
    assert not theme_controller.high_contrast


def test_a_forced_light_or_dark_theme_ignores_the_high_contrast_of_the_system(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_preference(ThemePreference.DARK)
    system_contrast_turns(qapp, Qt.ContrastPreference.HighContrast)
    assert theme_controller.current_theme is DARK_THEME
    assert not theme_controller.high_contrast


def test_the_high_contrast_choice_follows_the_light_or_dark_scheme_of_the_system(
    qapp: QApplication, create_theme_controller: ControllerFactory
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_preference(ThemePreference.HIGH_CONTRAST)
    assert theme_controller.high_contrast
    system_turns(qapp, Qt.ColorScheme.Dark)
    assert theme_controller.current_theme is HIGH_CONTRAST_DARK_THEME
    system_turns(qapp, Qt.ColorScheme.Light)
    assert theme_controller.current_theme is HIGH_CONTRAST_LIGHT_THEME
    system_contrast_turns(qapp, Qt.ContrastPreference.NoPreference)
    assert theme_controller.current_theme is HIGH_CONTRAST_LIGHT_THEME


def test_the_high_contrast_choice_keeps_the_text_size(
    create_theme_controller: ControllerFactory,
) -> None:
    theme_controller = create_theme_controller()
    theme_controller.set_text_size(150)
    theme_controller.set_preference(ThemePreference.HIGH_CONTRAST)
    assert theme_controller.current_theme.high_contrast
    assert theme_controller.current_theme.font_sizes.body == 21
