import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QColor, QKeySequence, QUndoCommand
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMenu
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme
from lacis.history import InvestigationHistory
from lacis.ui.help_menu import HelpMenu
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
    menu_bar = MainMenuBar(ThemeMenu(theme_controller), HelpMenu())
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
    menu_bar = MainMenuBar(theme_menu, HelpMenu())
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


def test_the_help_menu_and_the_help_button_share_the_same_entries(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = open_main_window(qtbot, settings, theme_controller)
    shared_menu = main_window.header_bar.help_menu
    assert main_window.header_bar.help_button.menu() is shared_menu
    assert main_window.main_menu_bar.help_menu is shared_menu
    assert main_window.main_menu_bar.actions()[-1] is shared_menu.menuAction()


class NoteCommand(QUndoCommand):
    def __init__(self, notes: list[str]) -> None:
        super().__init__("la décision d'homonyme")
        self.notes = notes

    def redo(self) -> None:
        self.notes.append("même personne")

    def undo(self) -> None:
        self.notes.pop()


def visible_text(action: QAction) -> str:
    return action.text().replace("&", "")


def test_the_edit_menu_offers_undo_and_redo_with_their_shortcuts(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    assert menu_bar.edit_menu.actions() == [menu_bar.undo_action, menu_bar.redo_action]
    assert menu_bar.edit_menu.menuAction().isEnabled()
    assert menu_bar.undo_action.shortcut() == QKeySequence("Ctrl+Z")
    assert menu_bar.redo_action.shortcut() == QKeySequence("Ctrl+Shift+Z")
    assert mnemonic(menu_bar.undo_action.text()) != mnemonic(menu_bar.redo_action.text())


def test_undo_and_redo_are_disabled_when_there_is_nothing_to_undo(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    assert visible_text(menu_bar.undo_action) == "Annuler"
    assert not menu_bar.undo_action.isEnabled()
    assert not menu_bar.redo_action.isEnabled()
    menu_bar.show_history(InvestigationHistory(menu_bar))
    assert not menu_bar.undo_action.isEnabled()


def test_the_undo_entries_name_the_action_they_apply_to(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    history = InvestigationHistory(menu_bar)
    menu_bar.show_history(history)
    notes: list[str] = []
    history.record(NoteCommand(notes))
    assert visible_text(menu_bar.undo_action) == "Annuler la décision d'homonyme"
    assert menu_bar.undo_action.isEnabled()
    menu_bar.undo_action.trigger()
    assert notes == []
    assert visible_text(menu_bar.redo_action) == "Rétablir la décision d'homonyme"
    assert not menu_bar.undo_action.isEnabled()
    menu_bar.redo_action.trigger()
    assert notes == ["même personne"]


def test_the_entries_follow_the_history_of_the_investigation_shown(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    menu_bar = create_menu_bar(qtbot, theme_controller)
    first_history = InvestigationHistory(menu_bar)
    first_history.record(NoteCommand([]))
    menu_bar.show_history(first_history)
    menu_bar.show_history(InvestigationHistory(menu_bar))
    assert not menu_bar.undo_action.isEnabled()
    menu_bar.show_history(first_history)
    assert menu_bar.undo_action.isEnabled()
    assert len(menu_bar.histories.stacks()) == 3
    menu_bar.show_history(None)
    assert not menu_bar.undo_action.isEnabled()
