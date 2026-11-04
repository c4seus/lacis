from PySide6.QtCore import QPoint, QSettings, QSize, Qt
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController
from lacis.ui.main_window import (
    DEFAULT_SIZE,
    GEOMETRY_SETTING_KEY,
    MINIMUM_SIZE,
    MainWindow,
)


def open_main_window(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller)
    qtbot.addWidget(main_window)
    main_window.show()
    qtbot.waitExposed(main_window)
    return main_window


def test_the_main_window_is_titled_lacis(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    assert open_main_window(qtbot, settings, theme_controller).windowTitle() == "Lacis"


def test_the_main_window_opens_at_its_default_size_the_first_time(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    assert open_main_window(qtbot, settings, theme_controller).size() == DEFAULT_SIZE


def test_the_main_window_cannot_be_smaller_than_1024_by_640(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    main_window.resize(800, 480)
    assert main_window.minimumSize() == MINIMUM_SIZE
    assert main_window.width() >= MINIMUM_SIZE.width()
    assert main_window.height() >= MINIMUM_SIZE.height()


def test_the_main_window_reopens_with_its_last_size_and_position(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    first_window = open_main_window(qtbot, settings, theme_controller)
    first_window.resize(QSize(1200, 700))
    first_window.move(QPoint(40, 60))
    expected_size = first_window.size()
    expected_position = first_window.pos()
    first_window.close()

    second_window = open_main_window(qtbot, settings, theme_controller)
    assert second_window.size() == expected_size
    assert second_window.pos() == expected_position


def test_the_main_window_reopens_maximised_when_it_was_closed_maximised(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    first_window = open_main_window(qtbot, settings, theme_controller)
    first_window.showMaximized()
    qtbot.waitUntil(first_window.isMaximized)
    first_window.close()

    second_window = open_main_window(qtbot, settings, theme_controller)
    assert second_window.windowState() & Qt.WindowState.WindowMaximized


def test_the_main_window_ignores_an_unreadable_saved_geometry(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    settings.setValue(GEOMETRY_SETTING_KEY, "not a geometry")
    assert open_main_window(qtbot, settings, theme_controller).size() == DEFAULT_SIZE


def test_the_main_window_shows_the_header_bar_at_the_top(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    assert main_window.header_bar.isVisible()
    assert main_window.header_bar.geometry().top() == 0
    assert main_window.header_bar.width() == main_window.width()
