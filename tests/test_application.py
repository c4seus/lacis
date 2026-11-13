import runpy
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QLocale,
    QSettings,
    QSize,
    Qt,
    qInstallMessageHandler,
)
from PySide6.QtGui import QFontInfo
from PySide6.QtWidgets import QApplication, QWidget

from lacis import __version__
from lacis.application import (
    APPLICATION_NAME,
    ORGANIZATION_NAME,
    configure_application,
    create_application,
    create_settings,
    main,
)
from lacis.collectors.endpoints import COMPANY_SEARCH_URL
from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT
from lacis.collectors.fake_plumbers import (
    FAKE_PLUMBERS_INVESTIGATION_NAME,
    FAKE_PLUMBERS_QUESTION,
)
from lacis.design.style_sheet import build_style_sheet
from lacis.design.theme_controller import ThemeController
from lacis.design.tokens import LIGHT_THEME
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.locations import DEMO_DIRECTORY_PREFIX, data_directory, investigations_directory
from lacis.ui.error_dialog import UnexpectedErrorHandler
from lacis.ui.main_window import DEMO_WINDOW_TITLE, MainWindow


def delete_windows_created_since(qapp: QApplication, windows_before: set[QWidget]) -> None:
    for window in qapp.topLevelWidgets():
        if window not in windows_before:
            window.close()
            window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


@pytest.fixture(autouse=True)
def remove_theme_controllers_created_by_main(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    qt_message_handler = qInstallMessageHandler(None)
    qInstallMessageHandler(qt_message_handler)
    windows_before = set(qapp.topLevelWidgets())
    yield
    delete_windows_created_since(qapp, windows_before)
    qInstallMessageHandler(qt_message_handler)
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


def test_the_application_is_known_to_the_desktop_with_its_icon(qapp: QApplication) -> None:
    configure_application(qapp)
    assert qapp.desktopFileName() == "io.github.c4seus.lacis"
    assert QSize(16, 16) in qapp.windowIcon().availableSizes()
    assert QSize(256, 256) in qapp.windowIcon().availableSizes()


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


def test_the_command_writes_its_start_to_the_log(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, isolated_log_directory: Path
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis"])
    log_text = (isolated_log_directory / "lacis.log").read_text(encoding="utf-8")
    assert f"Lacis {__version__} started" in log_text


def test_the_command_shows_unexpected_errors_in_a_dialog(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis"])
    assert isinstance(getattr(sys.excepthook, "__self__", None), UnexpectedErrorHandler)


@pytest.fixture
def shown_main_windows(monkeypatch: pytest.MonkeyPatch) -> list[MainWindow]:
    shown_windows: list[MainWindow] = []
    show_window = MainWindow.show

    def record_shown_window(main_window: MainWindow) -> None:
        shown_windows.append(main_window)
        show_window(main_window)

    monkeypatch.setattr(MainWindow, "show", record_shown_window)
    return shown_windows


def test_the_command_collects_from_the_real_apis_by_default(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, shown_main_windows: list[MainWindow]
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis"])
    [main_window] = shown_main_windows
    assert main_window.collection_environment is REAL_COLLECTION_ENVIRONMENT
    assert main_window.windowTitle() == "Lacis"


def test_the_demo_option_starts_lacis_on_the_fake_api(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, shown_main_windows: list[MainWindow]
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis", "--demo"])
    [main_window] = shown_main_windows
    assert main_window.windowTitle() == DEMO_WINDOW_TITLE
    assert main_window.collection_environment.demo
    transport = main_window.collection_environment.transport
    with httpx.Client(transport=transport) as client:
        response = client.get(COMPANY_SEARCH_URL, params={"q": "111111111"})
    assert response.json()["results"][0]["nom_complet"] == "ACME PLOMBERIE"


def test_the_demo_never_writes_to_the_real_data_directory(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, isolated_data_directory: Path
) -> None:
    demo_directories: list[Path] = []

    def create_an_investigation_during_the_demo() -> int:
        demo_directories.append(data_directory())
        InvestigationLibrary(investigations_directory()).create(
            FAKE_PLUMBERS_INVESTIGATION_NAME, FAKE_PLUMBERS_QUESTION
        )
        return 0

    monkeypatch.setattr(
        QApplication, "exec", staticmethod(create_an_investigation_during_the_demo)
    )
    assert main(["lacis", "--demo"]) == 0
    [demo_directory] = demo_directories
    assert demo_directory.name.startswith(DEMO_DIRECTORY_PREFIX)
    assert demo_directory != isolated_data_directory
    assert not demo_directory.exists()
    assert not isolated_data_directory.exists()


def test_the_demo_writes_its_data_directory_to_the_log(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, isolated_log_directory: Path
) -> None:
    monkeypatch.setattr(QApplication, "exec", staticmethod(lambda: 0))
    main(["lacis", "--demo"])
    log_text = (isolated_log_directory / "lacis.log").read_text(encoding="utf-8")
    assert "Demonstration mode on the fake API, data directory" in log_text
    assert DEMO_DIRECTORY_PREFIX in log_text


def test_the_help_describes_the_demo_option(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["lacis", "--help"])
    help_text = " ".join(capsys.readouterr().out.split())
    assert "--demo" in help_text
    assert "entreprises fictives" in help_text


def test_windows_left_by_the_command_are_deleted_after_each_test(qapp: QApplication) -> None:
    windows_before = set(qapp.topLevelWidgets())
    left_window = QWidget()
    left_window.show()
    delete_windows_created_since(qapp, windows_before)
    assert set(qapp.topLevelWidgets()) == windows_before
