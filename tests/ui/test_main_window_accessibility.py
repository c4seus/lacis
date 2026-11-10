from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QToolButton
from pytestqt.qtbot import QtBot

from accessibility_checks import interactive_widgets_without_accessible_name, tab_order
from lacis.design.theme_controller import ThemeController
from lacis.ui.main_window import MainWindow


def open_main_window(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller)
    qtbot.addWidget(main_window)
    main_window.show()
    qtbot.waitExposed(main_window)
    return main_window


def test_every_interactive_widget_of_the_main_window_has_a_name(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    assert interactive_widgets_without_accessible_name(main_window) == []


def test_an_unnamed_button_added_to_the_main_window_is_caught(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    unnamed_button = QToolButton()
    main_window.home_screen.content_layout.addWidget(unnamed_button)
    unnamed_button.show()
    assert interactive_widgets_without_accessible_name(main_window) == [unnamed_button]


def test_tab_goes_through_the_header_bar_in_visual_order(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    header_bar = main_window.header_bar
    header_bar.set_search_enabled(True)
    assert tab_order(main_window) == [
        header_bar.search_field,
        header_bar.search_button,
        header_bar.help_button,
        header_bar.theme_button,
        main_window.home_screen.new_investigation_button,
    ]


def test_tab_skips_the_inactive_search(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    header_bar = main_window.header_bar
    assert tab_order(main_window) == [
        header_bar.help_button,
        header_bar.theme_button,
        main_window.home_screen.new_investigation_button,
    ]
