import logging
import os
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication

from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.diagnostics import LOG_DIRECTORY_VARIABLE, LOGGER_NAME
from lacis.storage.collection_log import CollectionLog
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.locations import DATA_DIRECTORY_VARIABLE
from lacis.storage.responses import ResponseStore

OFFSCREEN_SCREEN_CONFIGURATION = Path(__file__).with_name("offscreen-screen.json")


def offscreen_platform_with_full_hd_screen() -> str:
    relative_configuration = Path(os.path.relpath(OFFSCREEN_SCREEN_CONFIGURATION))
    return f"offscreen:configfile={relative_configuration.as_posix()}"


@pytest.fixture(scope="session")
def qapp_args() -> list[str]:
    return ["lacis-tests", "-platform", offscreen_platform_with_full_hd_screen()]


@pytest.fixture(autouse=True)
def isolated_log_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    log_directory = tmp_path / "logs"
    monkeypatch.setenv(LOG_DIRECTORY_VARIABLE, str(log_directory))
    yield log_directory
    lacis_logger = logging.getLogger(LOGGER_NAME)
    for handler in list(lacis_logger.handlers):
        lacis_logger.removeHandler(handler)
        handler.close()


@pytest.fixture(autouse=True)
def isolated_data_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data_directory = tmp_path / "data"
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(data_directory))
    return data_directory


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


@pytest.fixture
def investigation_connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def response_store(investigation_connection: sqlite3.Connection) -> ResponseStore:
    return ResponseStore(investigation_connection)


@pytest.fixture
def collection_log(investigation_connection: sqlite3.Connection) -> CollectionLog:
    return CollectionLog(investigation_connection)
