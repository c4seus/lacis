import runpy
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QLocale, QSettings, Qt
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication

from lacis import __version__
from lacis.application import (
    APPLICATION_NAME,
    ORGANIZATION_NAME,
    configure_application,
    create_application,
    create_settings,
    main,
)
from lacis.design.style_sheet import build_style_sheet
from lacis.design.theme_controller import ThemeController
from lacis.design.tokens import LIGHT_THEME
from lacis.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def remove_theme_controllers_created_by_main(qapp: QApplication) -> Iterator[None]:
    yield
    for theme_controller in qapp.findChildren(ThemeController):
        qapp.styleHints().colorSchemeChanged.disconnect(
            theme_controller.follow_system_colour_scheme
        )
        theme_controller.setParent(None)
    qapp.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
    qapp.setStyleSheet("")


def test_the_application_has_its_name_organisation_and_version(qapp: QApplication) -> None:
    configure_application(qapp)
    assert qapp.applicationName() == APPLICATION_NAME
    assert qapp.applicationDisplayName() == APPLICATION_NAME
    assert qapp.organizationName() == ORGANIZATION_NAME
    assert qapp.applicationVersion() == __version__


def test_the_application_uses_the_bundled_inter_font(qapp: QApplication) -> None:
    configure_application(qapp)
    assert QFontInfo(qapp.font()).family() == "Inter"


def test_the_application_speaks_french(qapp: QApplication) -> None:
    configure_application(qapp)
    assert QLocale().language() == QLocale.Language.French
    assert QLocale().territory() == QLocale.Country.France


def test_creating_the_application_reuses_the_running_one(qapp: QApplication) -> None:
    assert create_application(["lacis"]) is qapp


def test_the_version_option_prints_the_version_and_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_information:
        main(["lacis", "--version"])
    assert exit_information.value.code == 0
    assert capsys.readouterr().out.strip() == f"Lacis {__version__}"


def test_python_m_lacis_runs_the_same_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["lacis", "--version"])
    with pytest.raises(SystemExit) as exit_information:
        runpy.run_module("lacis", run_name="__main__")
    assert exit_information.value.code == 0
    assert capsys.readouterr().out.strip() == f"Lacis {__version__}"


def test_an_unknown_option_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_information:
        main(["lacis", "--unknown"])
    assert exit_information.value.code == 2
    assert "--unknown" in capsys.readouterr().err


def test_the_command_without_option_shows_the_main_window_and_runs_the_event_loop(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    visible_main_windows: list[MainWindow] = []

    def run_event_loop_once() -> int:
        visible_main_windows.extend(
            widget
            for widget in qapp.topLevelWidgets()
            if isinstance(widget, MainWindow) and widget.isVisible()
        )
        return 0

    monkeypatch.setattr(QApplication, "exec", staticmethod(run_event_loop_once))
    assert main(["lacis"]) == 0
    assert len(visible_main_windows) == 1
    assert visible_main_windows[0].windowTitle() == "Lacis"


def test_the_command_applies_the_theme_of_the_system(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis"])
    assert len(qapp.findChildren(ThemeController)) == 1
    assert qapp.styleSheet() == build_style_sheet(LIGHT_THEME)


def test_settings_are_stored_in_an_ini_file_of_the_user(isolated_user_settings: Path) -> None:
    settings = create_settings()
    assert settings.format() == QSettings.Format.IniFormat
    assert Path(settings.fileName()) == isolated_user_settings / "Lacis" / "Lacis.ini"
