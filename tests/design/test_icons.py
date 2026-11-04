from collections.abc import Iterator

import pytest
from PySide6.QtCore import QByteArray, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QToolButton
from pytestqt.qtbot import QtBot

from lacis.design.icons import (
    CURRENT_COLOUR,
    ICON_DIRECTORY,
    ICON_NAMES,
    LOGO_NAME,
    IconFactory,
    ThemedSvgIconEngine,
    UnknownIconError,
    colour_icon_source,
    colour_logo_source,
    icon_colour,
    read_icon_source,
)
from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Colours

PREVIEW_SIZE = QSize(48, 48)


def most_opaque_colour(image: QImage) -> QColor:
    most_opaque = QColor(Qt.GlobalColor.transparent)
    for row in range(image.height()):
        for column in range(image.width()):
            colour = image.pixelColor(column, row)
            if colour.alpha() > most_opaque.alpha():
                most_opaque = colour
    return most_opaque


def colours_of(image: QImage) -> set[str]:
    return {
        image.pixelColor(column, row).name()
        for row in range(image.height())
        for column in range(image.width())
        if image.pixelColor(column, row).alpha() == 255
    }


@pytest.mark.parametrize("name", [*ICON_NAMES, LOGO_NAME])
def test_every_icon_is_a_valid_svg_file(name: str) -> None:
    source = read_icon_source(name)
    assert QSvgRenderer(QByteArray(source.encode("utf-8"))).isValid()


@pytest.mark.parametrize("name", ICON_NAMES)
def test_every_icon_takes_its_colour_from_the_theme(name: str) -> None:
    assert CURRENT_COLOUR in read_icon_source(name)


def test_every_svg_file_of_the_icon_directory_is_listed() -> None:
    files = {path.stem for path in ICON_DIRECTORY.glob("*.svg")}
    assert files == {*ICON_NAMES, LOGO_NAME}


def test_an_unknown_icon_is_refused() -> None:
    with pytest.raises(UnknownIconError):
        read_icon_source("unknown")


@pytest.mark.parametrize(
    ("mode", "state", "token"),
    [
        (QIcon.Mode.Normal, QIcon.State.Off, "muted_text"),
        (QIcon.Mode.Active, QIcon.State.Off, "text"),
        (QIcon.Mode.Selected, QIcon.State.Off, "text"),
        (QIcon.Mode.Normal, QIcon.State.On, "accent"),
        (QIcon.Mode.Disabled, QIcon.State.On, "faint_text"),
        (QIcon.Mode.Disabled, QIcon.State.Off, "faint_text"),
    ],
)
def test_each_icon_mode_has_its_colour_token(
    mode: QIcon.Mode, state: QIcon.State, token: str
) -> None:
    colours = LIGHT_THEME.colours
    assert icon_colour(colours, mode, state) == getattr(colours, token)


def test_colouring_an_icon_replaces_every_current_colour() -> None:
    coloured = colour_icon_source(read_icon_source("more"), "#123456")
    assert CURRENT_COLOUR not in coloured
    assert coloured.count("#123456") == read_icon_source("more").count(CURRENT_COLOUR)


def test_the_logo_keeps_its_colours_in_the_light_theme() -> None:
    source = read_icon_source(LOGO_NAME)
    assert colour_logo_source(source, LIGHT_THEME.colours) == source


def test_the_logo_takes_the_entity_colours_of_the_dark_theme() -> None:
    dark_logo = colour_logo_source(read_icon_source(LOGO_NAME), DARK_THEME.colours)
    for colour in (
        DARK_THEME.colours.muted_text,
        DARK_THEME.colours.company,
        DARK_THEME.colours.person,
        DARK_THEME.colours.address,
    ):
        assert colour in dark_logo
    assert LIGHT_THEME.colours.company not in dark_logo


def test_an_icon_is_painted_with_the_colours_provided(qapp: QApplication) -> None:
    current_colours: list[Colours] = [LIGHT_THEME.colours]
    icon = IconFactory(lambda: current_colours[0]).icon("search")

    light_pixmap = icon.pixmap(PREVIEW_SIZE)
    assert most_opaque_colour(light_pixmap.toImage()) == QColor(LIGHT_THEME.colours.muted_text)

    current_colours[0] = DARK_THEME.colours
    dark_pixmap = icon.pixmap(PREVIEW_SIZE)
    assert most_opaque_colour(dark_pixmap.toImage()) == QColor(DARK_THEME.colours.muted_text)


def test_a_disabled_icon_uses_the_faint_colour(qapp: QApplication) -> None:
    icon = IconFactory(lambda: LIGHT_THEME.colours).icon("search")
    pixmap = icon.pixmap(PREVIEW_SIZE, QIcon.Mode.Disabled)
    assert most_opaque_colour(pixmap.toImage()) == QColor(LIGHT_THEME.colours.faint_text)


def test_icons_stay_sharp_on_high_density_screens(qapp: QApplication) -> None:
    icon = IconFactory(lambda: LIGHT_THEME.colours).icon("search")
    pixmap = icon.pixmap(PREVIEW_SIZE, 2.0)
    assert pixmap.devicePixelRatio() == 2.0
    assert pixmap.size() == PREVIEW_SIZE * 2


def test_the_logo_is_painted_with_the_entity_colours(qapp: QApplication) -> None:
    logo = IconFactory(lambda: LIGHT_THEME.colours).logo()
    painted_colours = colours_of(logo.pixmap(PREVIEW_SIZE).toImage())
    assert {
        LIGHT_THEME.colours.company,
        LIGHT_THEME.colours.person,
        LIGHT_THEME.colours.address,
    } <= painted_colours


@pytest.fixture
def theme_controller(qapp: QApplication, settings: QSettings) -> Iterator[ThemeController]:
    controller = ThemeController(qapp, settings)
    yield controller
    qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")


def test_a_button_icon_changes_colour_when_the_theme_changes(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    factory = IconFactory(lambda: theme_controller.current_theme.colours)
    button = QToolButton()
    button.setIcon(factory.icon("search"))
    button.setIconSize(PREVIEW_SIZE)
    qtbot.addWidget(button)
    button.show()
    qtbot.waitExposed(button)

    theme_controller.set_preference(ThemePreference.LIGHT)
    assert LIGHT_THEME.colours.muted_text in colours_of(button.grab().toImage())

    theme_controller.set_preference(ThemePreference.DARK)
    dark_colours = colours_of(button.grab().toImage())
    assert DARK_THEME.colours.muted_text in dark_colours
    assert LIGHT_THEME.colours.muted_text not in dark_colours


def test_the_icon_engine_paints_directly_on_a_painter(qapp: QApplication) -> None:
    icon = IconFactory(lambda: LIGHT_THEME.colours).icon("search")
    image = QImage(PREVIEW_SIZE, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    icon.paint(painter, QRect(QPoint(0, 0), PREVIEW_SIZE))
    painter.end()
    assert most_opaque_colour(image) == QColor(LIGHT_THEME.colours.muted_text)


def test_the_icon_engine_gives_pixmaps_and_copies_of_itself(qapp: QApplication) -> None:
    engine = ThemedSvgIconEngine(
        lambda mode, state: colour_icon_source(read_icon_source("search"), "#123456")
    )
    for pixmap in (
        engine.pixmap(PREVIEW_SIZE, QIcon.Mode.Normal, QIcon.State.Off),
        engine.clone().pixmap(PREVIEW_SIZE, QIcon.Mode.Normal, QIcon.State.Off),
    ):
        assert pixmap.size() == PREVIEW_SIZE
        assert most_opaque_colour(pixmap.toImage()) == QColor("#123456")
