import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme
from lacis.ui.main_window import GEOMETRY_SETTING_KEY, MainWindow
from lacis.ui.menu_bar import MainMenuBar

MNEMONIC_MARKER = "&"


def mnemonic(text: str) -> str:
    marker_position = text.index(MNEMONIC_MARKER)
    return text[marker_position + 1].lower()


def open_main_window(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller)
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.activateWindow()
    qtbot.waitUntil(main_window.isActiveWindow)
    return main_window


def test_the_menu_bar_has_the_five_usual_menus(qtbot: QtBot) -> None:
    menu_bar = MainMenuBar()
    qtbot.addWidget(menu_bar)
    assert [menu.title() for menu in menu_bar.menus()] == [
        "&Fichier",
        "&Édition",
        "&Affichage",
        "&Enquête",
        "Ai&de",
    ]


def test_every_menu_has_its_own_mnemonic(qtbot: QtBot) -> None:
    menu_bar = MainMenuBar()
    qtbot.addWidget(menu_bar)
    mnemonics = [mnemonic(menu.title()) for menu in menu_bar.menus()]
    assert len(set(mnemonics)) == len(mnemonics)


def test_quit_is_in_the_file_menu_with_ctrl_q(qtbot: QtBot) -> None:
    menu_bar = MainMenuBar()
    qtbot.addWidget(menu_bar)
    assert menu_bar.file_menu.actions() == [menu_bar.quit_action]
    assert menu_bar.quit_action.text() == "&Quitter"
    assert menu_bar.quit_action.shortcut() == QKeySequence("Ctrl+Q")


def test_menus_without_entries_are_disabled(qtbot: QtBot) -> None:
    menu_bar = MainMenuBar()
    qtbot.addWidget(menu_bar)
    assert menu_bar.file_menu.menuAction().isEnabled()
    assert not menu_bar.investigation_menu.menuAction().isEnabled()


def test_the_main_window_shows_the_menu_bar(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    assert main_window.menuBar() is main_window.main_menu_bar
    assert main_window.main_menu_bar.isVisible()


def test_alt_opens_the_menu_bar_on_the_file_menu(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    QTest.keyClick(main_window, Qt.Key.Key_Alt)
    assert QApplication.focusWidget() is main_window.main_menu_bar
    assert (
        main_window.main_menu_bar.activeAction()
        is main_window.main_menu_bar.file_menu.menuAction()
    )


def test_quit_closes_the_window_and_saves_its_geometry(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    main_window.main_menu_bar.quit_action.trigger()
    assert not main_window.isVisible()
    assert settings.contains(GEOMETRY_SETTING_KEY)


@pytest.mark.parametrize(
    ("preference", "theme"),
    [(ThemePreference.LIGHT, LIGHT_THEME), (ThemePreference.DARK, DARK_THEME)],
    ids=["light", "dark"],
)
def test_the_menu_bar_follows_the_theme(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    preference: ThemePreference,
    theme: Theme,
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    theme_controller.set_preference(preference)
    menu_bar = main_window.main_menu_bar
    menu_bar_image = menu_bar.grab().toImage()
    assert menu_bar_image.pixelColor(menu_bar.width() - 4, 2) == QColor(theme.colours.surface)
