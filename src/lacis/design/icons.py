import re
from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import QByteArray, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QIconEngine, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from lacis.design.tokens import LIGHT_THEME, Colours

ICON_DIRECTORY = Path(__file__).resolve().parent.parent / "resources" / "icons"
ICON_NAMES = (
    "chevron-down",
    "close",
    "collapse",
    "copy",
    "expand",
    "external",
    "filter",
    "fit",
    "graph",
    "help",
    "layout",
    "monitor",
    "moon",
    "more",
    "plus",
    "refresh",
    "search",
    "sun",
    "zoom-in",
    "zoom-out",
)
LOGO_NAME = "logo"
CURRENT_COLOUR = "currentColor"
LOGO_COLOUR_TOKENS = ("muted_text", "company", "person", "address")

ColoursProvider = Callable[[], Colours]
SourceRenderer = Callable[[QIcon.Mode, QIcon.State], str]


class UnknownIconError(KeyError):
    pass


def read_icon_source(name: str) -> str:
    icon_path = ICON_DIRECTORY / f"{name}.svg"
    if not icon_path.is_file():
        raise UnknownIconError(name)
    return icon_path.read_text(encoding="utf-8")


def icon_colour(colours: Colours, mode: QIcon.Mode, state: QIcon.State) -> str:
    if mode == QIcon.Mode.Disabled:
        return colours.faint_text
    if state == QIcon.State.On:
        return colours.accent
    if mode in (QIcon.Mode.Active, QIcon.Mode.Selected):
        return colours.text
    return colours.muted_text


def colour_icon_source(source: str, colour: str) -> str:
    return source.replace(CURRENT_COLOUR, colour)


def colour_logo_source(source: str, colours: Colours) -> str:
    replacements = {
        getattr(LIGHT_THEME.colours, token): getattr(colours, token)
        for token in LOGO_COLOUR_TOKENS
    }
    pattern = re.compile("|".join(re.escape(colour) for colour in replacements))
    return pattern.sub(lambda match: replacements[match.group(0)], source)


def render_svg(source: str, painter: QPainter, area: QRectF) -> None:
    QSvgRenderer(QByteArray(source.encode("utf-8"))).render(painter, area)


class ThemedSvgIconEngine(QIconEngine):
    def __init__(self, render_source: SourceRenderer) -> None:
        super().__init__()
        self.render_source = render_source

    @override
    def paint(self, painter: QPainter, rect: QRect, mode: QIcon.Mode, state: QIcon.State) -> None:
        render_svg(self.render_source(mode, state), painter, QRectF(rect))

    @override
    def pixmap(self, size: QSize, mode: QIcon.Mode, state: QIcon.State) -> QPixmap:
        return self.scaledPixmap(size, mode, state, 1.0)

    @override
    def scaledPixmap(
        self, size: QSize, mode: QIcon.Mode, state: QIcon.State, scale: float
    ) -> QPixmap:
        pixmap = QPixmap(size * scale)
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        try:
            render_svg(
                self.render_source(mode, state),
                painter,
                QRectF(0, 0, size.width(), size.height()),
            )
        finally:
            painter.end()
        return pixmap

    @override
    def clone(self) -> QIconEngine:
        return ThemedSvgIconEngine(self.render_source)


class IconFactory:
    def __init__(self, colours_provider: ColoursProvider) -> None:
        self.colours_provider = colours_provider

    def icon(self, name: str) -> QIcon:
        source = read_icon_source(name)

        def render_source(mode: QIcon.Mode, state: QIcon.State) -> str:
            return colour_icon_source(source, icon_colour(self.colours_provider(), mode, state))

        return QIcon(ThemedSvgIconEngine(render_source))

    def icon_on_accent(self, name: str) -> QIcon:
        source = read_icon_source(name)

        def render_source(mode: QIcon.Mode, state: QIcon.State) -> str:
            colours = self.colours_provider()
            colour = colours.faint_text if mode == QIcon.Mode.Disabled else colours.text_on_accent
            return colour_icon_source(source, colour)

        return QIcon(ThemedSvgIconEngine(render_source))

    def logo(self) -> QIcon:
        source = read_icon_source(LOGO_NAME)

        def render_source(mode: QIcon.Mode, state: QIcon.State) -> str:
            return colour_logo_source(source, self.colours_provider())

        return QIcon(ThemedSvgIconEngine(render_source))
