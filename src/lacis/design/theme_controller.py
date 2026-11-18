from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, QSettings, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from lacis.design.fonts import application_font, system_text_scale
from lacis.design.style_sheet import build_style_sheet
from lacis.design.tokens import (
    DARK_THEME,
    HIGH_CONTRAST_DARK_THEME,
    HIGH_CONTRAST_LIGHT_THEME,
    LIGHT_THEME,
    Theme,
)


class ThemePreference(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"
    HIGH_CONTRAST = "high-contrast"


THEME_PREFERENCE_SETTING_KEY = "appearance/theme"
TEXT_SIZE_SETTING_KEY = "appearance/text_size"
HIGH_CONTRAST_NAME = "HighContrast"
TEXT_SIZES = (100, 125, 150, 175, 200)
DEFAULT_TEXT_SIZE = 100
FORCED_COLOUR_SCHEMES = {
    ThemePreference.LIGHT: Qt.ColorScheme.Light,
    ThemePreference.DARK: Qt.ColorScheme.Dark,
}


def theme_for_colour_scheme(
    colour_scheme: Qt.ColorScheme, *, high_contrast: bool = False
) -> Theme:
    dark = colour_scheme == Qt.ColorScheme.Dark
    if high_contrast:
        return HIGH_CONTRAST_DARK_THEME if dark else HIGH_CONTRAST_LIGHT_THEME
    return DARK_THEME if dark else LIGHT_THEME


def read_theme_preference(settings: QSettings) -> ThemePreference:
    stored_preference = settings.value(THEME_PREFERENCE_SETTING_KEY)
    try:
        return ThemePreference(stored_preference)
    except ValueError:
        return ThemePreference.SYSTEM


def read_text_size(settings: QSettings) -> int:
    stored_size = settings.value(TEXT_SIZE_SETTING_KEY, DEFAULT_TEXT_SIZE)
    try:
        size = int(str(stored_size))
    except ValueError:
        return DEFAULT_TEXT_SIZE
    return size if size in TEXT_SIZES else DEFAULT_TEXT_SIZE


def is_high_contrast(contrast: object) -> bool:
    return getattr(contrast, "name", None) == HIGH_CONTRAST_NAME


class SystemContrast(QObject):
    changed = Signal(bool)

    def __init__(self, style_hints: object, parent: QObject | None = None) -> None:
        super().__init__(parent)
        accessibility = getattr(style_hints, "accessibility", None)
        self.hints: Any = None if accessibility is None else accessibility()
        self.high_contrast = False
        if self.hints is not None:
            self.high_contrast = is_high_contrast(self.hints.contrastPreference())
            self.hints.contrastPreferenceChanged.connect(self.follow)

    def follow(self, contrast: object) -> None:
        self.high_contrast = is_high_contrast(contrast)
        self.changed.emit(self.high_contrast)

    def stop(self) -> None:
        if self.hints is not None:
            self.hints.contrastPreferenceChanged.disconnect(self.follow)


class ThemeController(QObject):
    theme_changed = Signal(Theme)
    preference_changed = Signal(ThemePreference)
    text_size_changed = Signal(int)

    def __init__(
        self, application: QApplication, settings: QSettings, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.application = application
        self.settings = settings
        self.style_hints = application.styleHints()
        self.system_contrast = SystemContrast(self.style_hints, self)
        self.colour_scheme = self.style_hints.colorScheme()
        self.current_theme = LIGHT_THEME
        self.base_theme = LIGHT_THEME
        self.preference = read_theme_preference(settings)
        self.text_size = read_text_size(settings)
        self.system_text_scale = system_text_scale()
        self.style_hints.colorSchemeChanged.connect(self.follow_system_colour_scheme)
        self.system_contrast.changed.connect(self.follow_system_contrast)
        self.apply_preference()

    def set_preference(self, preference: ThemePreference) -> None:
        self.preference = preference
        self.settings.setValue(THEME_PREFERENCE_SETTING_KEY, preference.value)
        self.settings.sync()
        self.apply_preference()
        self.preference_changed.emit(preference)

    @property
    def text_scale(self) -> float:
        return self.system_text_scale * self.text_size / 100

    def set_text_size(self, size: int) -> None:
        self.text_size = size if size in TEXT_SIZES else DEFAULT_TEXT_SIZE
        self.settings.setValue(TEXT_SIZE_SETTING_KEY, self.text_size)
        self.settings.sync()
        self.apply_theme(self.base_theme)
        self.text_size_changed.emit(self.text_size)

    @property
    def high_contrast(self) -> bool:
        if self.preference == ThemePreference.HIGH_CONTRAST:
            return True
        return self.preference == ThemePreference.SYSTEM and self.system_contrast.high_contrast

    def apply_preference(self) -> None:
        forced_colour_scheme = FORCED_COLOUR_SCHEMES.get(self.preference)
        if forced_colour_scheme is None:
            self.style_hints.setColorScheme(Qt.ColorScheme.Unknown)
            self.follow_system_colour_scheme(self.style_hints.colorScheme())
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
        self.colour_scheme = colour_scheme
        if self.preference not in FORCED_COLOUR_SCHEMES:
            self.apply_theme(
                theme_for_colour_scheme(colour_scheme, high_contrast=self.high_contrast)
            )

    def stop_following_the_system(self) -> None:
        self.style_hints.colorSchemeChanged.disconnect(self.follow_system_colour_scheme)
        self.system_contrast.stop()

    def follow_system_contrast(self, high_contrast: bool) -> None:
        if self.preference == ThemePreference.SYSTEM:
            self.follow_system_colour_scheme(self.colour_scheme)

    def apply_theme(self, theme: Theme) -> None:
        self.base_theme = theme
        scaled_theme = theme.with_text_scale(self.text_scale)
        self.current_theme = scaled_theme
        self.application.setFont(application_font(scaled_theme.font_sizes))
        self.apply_link_colours(scaled_theme)
        self.application.setStyleSheet(build_style_sheet(scaled_theme))
        self.theme_changed.emit(scaled_theme)
