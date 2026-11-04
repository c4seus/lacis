import os
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

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
