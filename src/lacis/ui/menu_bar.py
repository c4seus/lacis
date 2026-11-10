from PySide6.QtGui import QAction, QKeySequence, QUndoGroup
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget

from lacis.history import InvestigationHistory
from lacis.ui.help_menu import HelpMenu
from lacis.ui.theme_menu import ThemeMenu

FILE_MENU_TITLE = "&Fichier"
EDIT_MENU_TITLE = "&Édition"
VIEW_MENU_TITLE = "&Affichage"
INVESTIGATION_MENU_TITLE = "&Enquête"
QUIT_ACTION_TEXT = "&Quitter"
NEW_INVESTIGATION_ACTION_TEXT = "&Nouvelle enquête…"
NEW_INVESTIGATION_SHORTCUT = QKeySequence("Ctrl+N")
QUIT_SHORTCUT = QKeySequence("Ctrl+Q")
UNDO_PREFIX = "&Annuler"
REDO_PREFIX = "&Rétablir"
UNDO_SHORTCUT = QKeySequence("Ctrl+Z")
REDO_SHORTCUT = QKeySequence("Ctrl+Shift+Z")


class MainMenuBar(QMenuBar):
    def __init__(
        self, theme_menu: ThemeMenu, help_menu: HelpMenu, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.file_menu = self.addMenu(FILE_MENU_TITLE)
        self.edit_menu = self.addMenu(EDIT_MENU_TITLE)
        self.view_menu = self.addMenu(VIEW_MENU_TITLE)
        self.investigation_menu = self.addMenu(INVESTIGATION_MENU_TITLE)
        self.help_menu = help_menu
        self.addMenu(help_menu)

        self.new_investigation_action = QAction(NEW_INVESTIGATION_ACTION_TEXT, self)
        self.new_investigation_action.setShortcut(NEW_INVESTIGATION_SHORTCUT)
        self.quit_action = QAction(QUIT_ACTION_TEXT, self)
        self.quit_action.setShortcut(QUIT_SHORTCUT)
        self.file_menu.addAction(self.new_investigation_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.quit_action)
        self.histories = QUndoGroup(self)
        self.no_history = InvestigationHistory(self)
        self.histories.addStack(self.no_history)
        self.undo_action = self.histories.createUndoAction(self, UNDO_PREFIX)
        self.undo_action.setShortcut(UNDO_SHORTCUT)
        self.redo_action = self.histories.createRedoAction(self, REDO_PREFIX)
        self.redo_action.setShortcut(REDO_SHORTCUT)
        self.edit_menu.addActions([self.undo_action, self.redo_action])
        self.view_menu.addMenu(theme_menu)
        self.update_menu_availability()

    def menus(self) -> list[QMenu]:
        return [
            self.file_menu,
            self.edit_menu,
            self.view_menu,
            self.investigation_menu,
            self.help_menu,
        ]

    def show_history(self, history: InvestigationHistory | None) -> None:
        shown_history = history if history is not None else self.no_history
        if shown_history not in self.histories.stacks():
            self.histories.addStack(shown_history)
        self.histories.setActiveStack(shown_history)

    def update_menu_availability(self) -> None:
        for menu in self.menus():
            menu.menuAction().setEnabled(bool(menu.actions()))
