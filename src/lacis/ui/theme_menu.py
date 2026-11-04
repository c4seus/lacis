from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from lacis.design.theme_controller import (
    THEME_PREFERENCE_LABELS,
    ThemeController,
    ThemePreference,
)

THEME_MENU_TITLE = "Thème"


class ThemeMenu(QMenu):
    def __init__(self, theme_controller: ThemeController, parent: QWidget | None = None) -> None:
        super().__init__(THEME_MENU_TITLE, parent)
        self.theme_controller = theme_controller
        self.preference_actions: dict[ThemePreference, QAction] = {}
        action_group = QActionGroup(self)
        action_group.setExclusive(True)
        for preference, label in THEME_PREFERENCE_LABELS.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked, chosen_preference=preference: self.choose(chosen_preference)
            )
            action_group.addAction(action)
            self.addAction(action)
            self.preference_actions[preference] = action
        theme_controller.preference_changed.connect(self.show_preference)
        self.show_preference(theme_controller.preference)

    def choose(self, preference: ThemePreference) -> None:
        self.theme_controller.set_preference(preference)

    def show_preference(self, preference: ThemePreference) -> None:
        self.preference_actions[preference].setChecked(True)
