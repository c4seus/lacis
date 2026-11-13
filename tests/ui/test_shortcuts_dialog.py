from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController
from lacis.ui.help_menu import HelpMenu
from lacis.ui.main_window import MainWindow
from lacis.ui.menu_bar import MainMenuBar
from lacis.ui.shortcuts_dialog import (
    ShortcutGroup,
    ShortcutLine,
    ShortcutsDialog,
    action_line,
    shortcut_groups,
)
from lacis.ui.theme_menu import ThemeMenu


def create_menu_bar(qtbot: QtBot, theme_controller: ThemeController) -> MainMenuBar:
    menu_bar = MainMenuBar(ThemeMenu(theme_controller), HelpMenu())
    qtbot.addWidget(menu_bar)
    return menu_bar


def open_window(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> MainWindow:
    window = MainWindow(settings, theme_controller)
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    return window


def test_an_action_is_described_by_its_text_and_all_its_shortcuts(qtbot: QtBot) -> None:
    action = QAction("Zoom &avant…")
    action.setShortcuts([QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
    assert action_line(action) == ShortcutLine("Zoom avant", "Ctrl++ ou Ctrl+=")
    assert action_line(action, "Zoomer") == ShortcutLine("Zoomer", "Ctrl++ ou Ctrl+=")


def test_the_groups_list_every_shortcut_of_the_menus(
    qtbot: QtBot, theme_controller: ThemeController
) -> None:
    groups = shortcut_groups(create_menu_bar(qtbot, theme_controller))
    assert [group.title for group in groups] == [
        "Enquête",
        "Graphe",
        "Dans le graphe",
        "Panneaux",
        "Application",
    ]
    lines = {line.description: line.keys for group in groups for line in group.lines}
    assert lines["Rechercher une entreprise"] == "Ctrl+F ou /"
    assert lines["Étendre la sélection"] == "Ctrl+E"
    assert lines["Ajuster le graphe à la fenêtre"] == "Ctrl+0"
    assert lines["Onglet suivant"] == "Ctrl+PgDown"
    assert lines["Onglet Entités"] == "Alt+3"
    assert lines["Afficher les raccourcis clavier"] == "Ctrl+/"
    assert lines["Aller à l'entité voisine"] == "Flèches"
    assert lines["Annuler la dernière décision"] == "Ctrl+Z"
    assert all(lines.values())


def test_the_dialog_lists_the_shortcuts_by_group(qtbot: QtBot) -> None:
    dialog = ShortcutsDialog(
        (
            ShortcutGroup("Enquête", (ShortcutLine("Rechercher", "Ctrl+F"),)),
            ShortcutGroup("Graphe", (ShortcutLine("Ajuster", "Ctrl+0"),)),
        )
    )
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Raccourcis clavier"
    assert dialog.lines() == [
        ("Enquête", "Rechercher", "Ctrl+F"),
        ("Graphe", "Ajuster", "Ctrl+0"),
    ]
    tree = dialog.tree
    assert tree.accessibleName() == "Liste des raccourcis clavier"
    assert [tree.headerItem().text(column) for column in range(2)] == ["Action", "Raccourci"]
    current = tree.currentItem()
    assert current is not None
    assert current.text(0) == "Rechercher"
    assert current.data(1, Qt.ItemDataRole.AccessibleTextRole) == "Ctrl+F"
    assert not dialog.group_items[0].flags() & Qt.ItemFlag.ItemIsSelectable
    assert all(item.isExpanded() for item in dialog.group_items)


def test_the_help_button_opens_the_shortcuts_dialog_once(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    window = open_window(qtbot, settings, theme_controller)
    window.header_bar.help_menu.shortcuts_action.trigger()
    dialog = window.shortcuts_dialog
    assert dialog is not None
    assert dialog.isVisible()
    qtbot.waitUntil(dialog.tree.hasFocus)
    QTest.keyClick(dialog.tree, Qt.Key.Key_Escape)
    assert not dialog.isVisible()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    window.content_area.setFocus()
    QTest.keyClick(window.content_area, Qt.Key.Key_Slash, Qt.KeyboardModifier.ControlModifier)
    assert window.shortcuts_dialog is dialog
    assert dialog.isVisible()
    dialog.button_box.rejected.emit()
    assert not dialog.isVisible()
