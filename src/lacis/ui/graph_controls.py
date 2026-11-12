from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QToolButton, QVBoxLayout, QWidget

from lacis.design.icons import IconFactory
from lacis.ui.header_bar import create_icon_button

ZOOM_BUTTON_SIZE = QSize(30, 30)
ZOOM_TOOLBAR_ACCESSIBLE_NAME = "Navigation dans le graphe"
ZOOM_IN_TEXT = "Zoom avant"
ZOOM_OUT_TEXT = "Zoom arrière"
FIT_TEXT = "Ajuster à la fenêtre"
LAYOUT_TEXT = "Réorganiser le graphe"
ZOOM_IN_SHORTCUT_TEXT = "Ctrl++"
ZOOM_OUT_SHORTCUT_TEXT = "Ctrl+-"
FIT_SHORTCUT_TEXT = "Ctrl+0"
LAYOUT_SHORTCUT_TEXT = "Ctrl+Maj+R"


def tooltip_with_shortcut(text: str, shortcut: str) -> str:
    return f"{text} ({shortcut})"


class ZoomToolbar(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphToolbar")
        self.setAccessibleName(ZOOM_TOOLBAR_ACCESSIBLE_NAME)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.zoom_in_button = self.add_button(
            icon_factory, "zoom-in", ZOOM_IN_TEXT, ZOOM_IN_SHORTCUT_TEXT
        )
        self.zoom_out_button = self.add_button(
            icon_factory, "zoom-out", ZOOM_OUT_TEXT, ZOOM_OUT_SHORTCUT_TEXT
        )
        self.fit_button = self.add_button(icon_factory, "fit", FIT_TEXT, FIT_SHORTCUT_TEXT)
        self.layout_button = self.add_button(
            icon_factory, "layout", LAYOUT_TEXT, LAYOUT_SHORTCUT_TEXT
        )

    def add_button(
        self, icon_factory: IconFactory, icon_name: str, text: str, shortcut: str
    ) -> QToolButton:
        button = create_icon_button(
            icon_factory.icon(icon_name), text, tooltip_with_shortcut(text, shortcut), self
        )
        button.setFixedSize(ZOOM_BUTTON_SIZE)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        layout = self.layout()
        assert layout is not None
        layout.addWidget(button)
        return button

    @property
    def buttons(self) -> list[QToolButton]:
        return [self.zoom_in_button, self.zoom_out_button, self.fit_button, self.layout_button]
