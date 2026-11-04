from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenu, QMenuBar, QWidget

FILE_MENU_TITLE = "&Fichier"
EDIT_MENU_TITLE = "&Édition"
VIEW_MENU_TITLE = "&Affichage"
INVESTIGATION_MENU_TITLE = "&Enquête"
HELP_MENU_TITLE = "Ai&de"
QUIT_ACTION_TEXT = "&Quitter"
QUIT_SHORTCUT = QKeySequence("Ctrl+Q")


class MainMenuBar(QMenuBar):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.file_menu = self.addMenu(FILE_MENU_TITLE)
        self.edit_menu = self.addMenu(EDIT_MENU_TITLE)
        self.view_menu = self.addMenu(VIEW_MENU_TITLE)
        self.investigation_menu = self.addMenu(INVESTIGATION_MENU_TITLE)
        self.help_menu = self.addMenu(HELP_MENU_TITLE)

        self.quit_action = QAction(QUIT_ACTION_TEXT, self)
        self.quit_action.setShortcut(QUIT_SHORTCUT)
        self.file_menu.addAction(self.quit_action)
        self.update_menu_availability()

    def menus(self) -> list[QMenu]:
        return [
            self.file_menu,
            self.edit_menu,
            self.view_menu,
            self.investigation_menu,
            self.help_menu,
        ]

    def update_menu_availability(self) -> None:
        for menu in self.menus():
            menu.menuAction().setEnabled(bool(menu.actions()))
