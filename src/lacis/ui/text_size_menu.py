from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from lacis.design.theme_controller import TEXT_SIZES, ThemeController

TEXT_SIZE_MENU_TITLE = "Taille du te&xte"
SIZE_LABELS = {
    100: "&100\u00a0%",
    125: "1&25\u00a0%",
    150: "1&50\u00a0%",
    175: "1&75\u00a0%",
    200: "2&00\u00a0%",
}


class TextSizeMenu(QMenu):
    def __init__(self, theme_controller: ThemeController, parent: QWidget | None = None) -> None:
        super().__init__(TEXT_SIZE_MENU_TITLE, parent)
        self.theme_controller = theme_controller
        self.size_actions: dict[int, QAction] = {}
        action_group = QActionGroup(self)
        action_group.setExclusive(True)
        for size in TEXT_SIZES:
            action = QAction(SIZE_LABELS[size], self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda checked=False, chosen_size=size: theme_controller.set_text_size(chosen_size)
            )
            action_group.addAction(action)
            self.addAction(action)
            self.size_actions[size] = action
        theme_controller.text_size_changed.connect(self.show_size)
        self.show_size(theme_controller.text_size)

    def show_size(self, size: int) -> None:
        self.size_actions[size].setChecked(True)
