from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from lacis.design.style_sheet import build_style_sheet
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme


def theme_for_colour_scheme(colour_scheme: Qt.ColorScheme) -> Theme:
    return DARK_THEME if colour_scheme == Qt.ColorScheme.Dark else LIGHT_THEME


class ThemeController(QObject):
    theme_changed = Signal(Theme)

    def __init__(self, application: QApplication, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.application = application
        self.style_hints = application.styleHints()
        self.current_theme = LIGHT_THEME
        self.style_hints.colorSchemeChanged.connect(self.follow_system_colour_scheme)
        self.apply_theme(theme_for_colour_scheme(self.style_hints.colorScheme()))

    def follow_system_colour_scheme(self, colour_scheme: Qt.ColorScheme) -> None:
        self.apply_theme(theme_for_colour_scheme(colour_scheme))

    def apply_theme(self, theme: Theme) -> None:
        self.current_theme = theme
        self.application.setStyleSheet(build_style_sheet(theme))
        self.theme_changed.emit(theme)
