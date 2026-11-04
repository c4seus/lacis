from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QMenu, QWidget

HELP_MENU_TITLE = "Ai&de"
DOCUMENTATION_ACTION_TEXT = "&Documentation"
DOCUMENTATION_URL = "https://github.com/c4seus/lacis#readme"
DOCUMENTATION_SHORTCUT = QKeySequence("F1")
REPORT_PROBLEM_ACTION_TEXT = "&Signaler un problème…"
REPORT_PROBLEM_URL = "https://github.com/c4seus/lacis/issues/new/choose"


class HelpMenu(QMenu):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(HELP_MENU_TITLE, parent)
        self.documentation_action = self.add_link(
            DOCUMENTATION_ACTION_TEXT, DOCUMENTATION_URL, DOCUMENTATION_SHORTCUT
        )
        self.report_problem_action = self.add_link(REPORT_PROBLEM_ACTION_TEXT, REPORT_PROBLEM_URL)

    def add_link(self, text: str, url: str, shortcut: QKeySequence | None = None) -> QAction:
        action = QAction(text, self)
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        self.addAction(action)
        return action
