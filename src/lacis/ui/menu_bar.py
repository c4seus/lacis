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
CLOSE_INVESTIGATION_ACTION_TEXT = "&Fermer l'enquête"
CLOSE_INVESTIGATION_SHORTCUT = QKeySequence("Ctrl+W")
QUEUE_ACTION_TEXT = "&Colonne À examiner"
QUEUE_SHORTCUT = QKeySequence("Ctrl+1")
QUIT_SHORTCUT = QKeySequence("Ctrl+Q")
ZOOM_IN_ACTION_TEXT = "Zoom &avant"
ZOOM_IN_SHORTCUTS = [QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")]
ZOOM_OUT_ACTION_TEXT = "Zoom a&rrière"
ZOOM_OUT_SHORTCUT = QKeySequence("Ctrl+-")
FIT_ACTION_TEXT = "A&juster le graphe à la fenêtre"
FIT_SHORTCUT = QKeySequence("Ctrl+0")
LAYOUT_ACTION_TEXT = "Réor&ganiser le graphe"
LAYOUT_SHORTCUT = QKeySequence("Ctrl+Shift+R")
DETAILS_MENU_TITLE = "&Panneau de détails"
NEXT_TAB_ACTION_TEXT = "Onglet &suivant"
NEXT_TAB_SHORTCUT = QKeySequence("Ctrl+PgDown")
PREVIOUS_TAB_ACTION_TEXT = "Onglet &précédent"
PREVIOUS_TAB_SHORTCUT = QKeySequence("Ctrl+PgUp")
TAB_ACTION_TEXTS = ("&Fiche", "Si&gnaux", "&Entités", "&Journal")
SEARCH_ACTION_TEXT = "&Rechercher une entreprise"
SEARCH_SHORTCUTS = [QKeySequence("Ctrl+F"), QKeySequence("/")]
EXPAND_ACTION_TEXT = "É&tendre la sélection"
EXPAND_SHORTCUT = QKeySequence("Ctrl+E")
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
        self.close_investigation_action = QAction(CLOSE_INVESTIGATION_ACTION_TEXT, self)
        self.close_investigation_action.setShortcut(CLOSE_INVESTIGATION_SHORTCUT)
        self.close_investigation_action.setEnabled(False)
        self.quit_action = QAction(QUIT_ACTION_TEXT, self)
        self.quit_action.setShortcut(QUIT_SHORTCUT)
        self.file_menu.addAction(self.new_investigation_action)
        self.file_menu.addAction(self.close_investigation_action)
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
        self.create_view_menu(theme_menu)
        self.create_investigation_menu()
        self.show_investigation_actions(False)
        self.update_menu_availability()

    def create_view_menu(self, theme_menu: ThemeMenu) -> None:
        self.queue_action = QAction(QUEUE_ACTION_TEXT, self)
        self.queue_action.setCheckable(True)
        self.queue_action.setShortcut(QUEUE_SHORTCUT)
        self.view_menu.addAction(self.queue_action)
        self.view_menu.addSeparator()
        self.zoom_in_action = QAction(ZOOM_IN_ACTION_TEXT, self)
        self.zoom_in_action.setShortcuts(ZOOM_IN_SHORTCUTS)
        self.zoom_out_action = QAction(ZOOM_OUT_ACTION_TEXT, self)
        self.zoom_out_action.setShortcut(ZOOM_OUT_SHORTCUT)
        self.fit_action = QAction(FIT_ACTION_TEXT, self)
        self.fit_action.setShortcut(FIT_SHORTCUT)
        self.layout_action = QAction(LAYOUT_ACTION_TEXT, self)
        self.layout_action.setShortcut(LAYOUT_SHORTCUT)
        self.view_menu.addActions(self.graph_actions)
        self.view_menu.addSeparator()
        self.create_details_menu()
        self.view_menu.addSeparator()
        self.view_menu.addMenu(theme_menu)

    def create_investigation_menu(self) -> None:
        self.search_action = QAction(SEARCH_ACTION_TEXT, self)
        self.search_action.setShortcuts(SEARCH_SHORTCUTS)
        self.expand_action = QAction(EXPAND_ACTION_TEXT, self)
        self.expand_action.setShortcut(EXPAND_SHORTCUT)
        self.expand_action.setEnabled(False)
        self.investigation_menu.addActions([self.search_action, self.expand_action])

    def create_details_menu(self) -> None:
        self.details_menu = QMenu(DETAILS_MENU_TITLE, self.view_menu)
        self.next_tab_action = QAction(NEXT_TAB_ACTION_TEXT, self)
        self.next_tab_action.setShortcut(NEXT_TAB_SHORTCUT)
        self.previous_tab_action = QAction(PREVIOUS_TAB_ACTION_TEXT, self)
        self.previous_tab_action.setShortcut(PREVIOUS_TAB_SHORTCUT)
        self.details_menu.addActions([self.next_tab_action, self.previous_tab_action])
        self.details_menu.addSeparator()
        self.tab_actions: list[QAction] = []
        for position, text in enumerate(TAB_ACTION_TEXTS, start=1):
            action = QAction(text, self)
            action.setShortcut(QKeySequence(f"Alt+{position}"))
            self.tab_actions.append(action)
        self.details_menu.addActions(self.tab_actions)
        self.view_menu.addMenu(self.details_menu)

    @property
    def graph_actions(self) -> list[QAction]:
        return [self.zoom_in_action, self.zoom_out_action, self.fit_action, self.layout_action]

    @property
    def investigation_actions(self) -> list[QAction]:
        return [
            self.queue_action,
            *self.graph_actions,
            self.next_tab_action,
            self.previous_tab_action,
            *self.tab_actions,
            self.search_action,
        ]

    def show_investigation_actions(self, shown: bool) -> None:
        for action in self.investigation_actions:
            action.setEnabled(shown)
        if not shown:
            self.expand_action.setEnabled(False)

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
