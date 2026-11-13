from enum import StrEnum

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from lacis.design.style_sheet import build_style_sheet
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme


class ThemePreference(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


THEME_PREFERENCE_SETTING_KEY = "appearance/theme"
FORCED_COLOUR_SCHEMES = {
    ThemePreference.LIGHT: Qt.ColorScheme.Light,
    ThemePreference.DARK: Qt.ColorScheme.Dark,
}


def theme_for_colour_scheme(colour_scheme: Qt.ColorScheme) -> Theme:
    return DARK_THEME if colour_scheme == Qt.ColorScheme.Dark else LIGHT_THEME


def read_theme_preference(settings: QSettings) -> ThemePreference:
    stored_preference = settings.value(THEME_PREFERENCE_SETTING_KEY)
    try:
        return ThemePreference(stored_preference)
    except ValueError:
        return ThemePreference.SYSTEM


class ThemeController(QObject):
    theme_changed = Signal(Theme)
    preference_changed = Signal(ThemePreference)

    def __init__(
        self, application: QApplication, settings: QSettings, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.application = application
        self.settings = settings
        self.style_hints = application.styleHints()
        self.current_theme = LIGHT_THEME
        self.preference = read_theme_preference(settings)
        self.style_hints.colorSchemeChanged.connect(self.follow_system_colour_scheme)
        self.apply_preference()

    def set_preference(self, preference: ThemePreference) -> None:
        self.preference = preference
        self.settings.setValue(THEME_PREFERENCE_SETTING_KEY, preference.value)
        self.settings.sync()
        self.apply_preference()
        self.preference_changed.emit(preference)

    def apply_preference(self) -> None:
        forced_colour_scheme = FORCED_COLOUR_SCHEMES.get(self.preference)
        if forced_colour_scheme is None:
            self.style_hints.setColorScheme(Qt.ColorScheme.Unknown)
            self.apply_theme(theme_for_colour_scheme(self.style_hints.colorScheme()))
            return
        self.style_hints.setColorScheme(forced_colour_scheme)
        self.apply_theme(theme_for_colour_scheme(forced_colour_scheme))

    def apply_link_colours(self, theme: Theme) -> None:
        palette = self.application.palette()
        link_colour = QColor(theme.colours.accent)
        palette.setColor(QPalette.ColorRole.Link, link_colour)
        palette.setColor(QPalette.ColorRole.LinkVisited, link_colour)
        self.application.setPalette(palette)

    def follow_system_colour_scheme(self, colour_scheme: Qt.ColorScheme) -> None:
        if self.preference == ThemePreference.SYSTEM:
            self.apply_theme(theme_for_colour_scheme(colour_scheme))

    def apply_theme(self, theme: Theme) -> None:
        self.current_theme = theme
        self.apply_link_colours(theme)
        self.application.setStyleSheet(build_style_sheet(theme))
        self.theme_changed.emit(theme)
