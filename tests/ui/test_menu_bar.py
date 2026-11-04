import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme
from lacis.ui.main_window import GEOMETRY_SETTING_KEY, MainWindow
from lacis.ui.menu_bar import MainMenuBar
from lacis.ui.theme_menu import ThemeMenu

MNEMONIC_MARKER = "&"


def mnemonic(text: str) -> str:
    marker_position = text.index(MNEMONIC_MARKER)
    return text[marker_position + 1].lower()


def all_menus(menus: list[QMenu]) -> list[QMenu]:
    found_menus: list[QMenu] = []
    for menu in menus:
        found_menus.append(menu)
        submenus = [action.menu() for action in menu.actions()]
        found_menus.extend(
            all_menus([submenu for submenu in submenus if isinstance(submenu, QMenu)])
        )
    return found_menus


def open_main_window(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller)
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.activateWindow()
    qtbot.waitUntil(main_window.isActiveWindow)
    return main_window


def create_menu_bar(qtbot: QtBot, theme_controller: ThemeController) -> MainMenuBar:
    menu_bar = MainMenuBar(ThemeMenu(theme_controller))
    qtbot.addWidget(menu_bar)
    return menu_bar


def test_the_menu_bar_has_the_five_usual_menus(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    assert [menu.title() for menu in menu_bar.menus()] == [
        "&Fichier",
        "&Édition",
        "&Affichage",
        "&Enquête",
        "Ai&de",
    ]


def test_every_menu_has_its_own_mnemonic(qtbot: QtBot, theme_controller: ThemeController) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    mnemonics = [mnemonic(menu.title()) for menu in menu_bar.menus()]
    assert len(set(mnemonics)) == len(mnemonics)


def test_quit_is_in_the_file_menu_with_ctrl_q(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    assert menu_bar.file_menu.actions() == [menu_bar.quit_action]
    assert menu_bar.quit_action.text() == "&Quitter"
    assert menu_bar.quit_action.shortcut() == QKeySequence("Ctrl+Q")


def test_menus_without_entries_are_disabled(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
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


def test_the_view_menu_offers_the_theme_choice(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    theme_menu = ThemeMenu(theme_controller)
    menu_bar = MainMenuBar(theme_menu)
    qtbot.addWidget(menu_bar)
    assert menu_bar.view_menu.actions() == [theme_menu.menuAction()]
    assert menu_bar.view_menu.menuAction().isEnabled()


def test_the_view_menu_and_the_theme_button_share_the_same_choice(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    shared_menu = main_window.header_bar.theme_menu
    assert main_window.header_bar.theme_button.menu() is shared_menu
    assert main_window.main_menu_bar.view_menu.actions() == [shared_menu.menuAction()]
    shared_menu.preference_actions[ThemePreference.DARK].trigger()
    assert theme_controller.current_theme is DARK_THEME


def test_every_entry_of_a_menu_has_its_own_mnemonic(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    checked_menus = 0
    for menu in all_menus(menu_bar.menus()):
        entries = [action.text() for action in menu.actions() if not action.isSeparator()]
        mnemonics = [mnemonic(entry) for entry in entries]
        assert len(set(mnemonics)) == len(mnemonics), menu.title()
        checked_menus += 1
    assert checked_menus == len(menu_bar.menus()) + 1
