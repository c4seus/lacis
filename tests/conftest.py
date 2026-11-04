import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController

OFFSCREEN_SCREEN_CONFIGURATION = Path(__file__).with_name("offscreen-screen.json")


def offscreen_platform_with_full_hd_screen() -> str:
    relative_configuration = Path(os.path.relpath(OFFSCREEN_SCREEN_CONFIGURATION))
    return f"offscreen:configfile={relative_configuration.as_posix()}"


@pytest.fixture(scope="session")
def qapp_args() -> list[str]:
    return ["lacis-tests", "-platform", offscreen_platform_with_full_hd_screen()]


@pytest.fixture(autouse=True)
def isolated_user_settings(tmp_path: Path) -> Path:
    settings_directory = tmp_path / "settings"
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(settings_directory)
    )
    return settings_directory


@pytest.fixture
def settings(isolated_user_settings: Path) -> QSettings:
    return QSettings(
        str(isolated_user_settings / "Lacis" / "Lacis.ini"), QSettings.Format.IniFormat
    )


@pytest.fixture
def theme_controller(qapp: QApplication, settings: QSettings) -> Iterator[ThemeController]:
    controller = ThemeController(qapp, settings)
    yield controller
    qapp.styleHints().colorSchemeChanged.disconnect(controller.follow_system_colour_scheme)
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")


@pytest.fixture
def icon_factory(theme_controller: ThemeController) -> IconFactory:
    return IconFactory(lambda: theme_controller.current_theme.colours)
