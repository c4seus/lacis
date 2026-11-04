from collections.abc import Sequence
from typing import override

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QIcon, QPainter, QPaintEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from lacis import __version__
from lacis.design.icons import IconFactory

HEADER_BAR_HEIGHT = 52
LOGO_SIZE = QSize(22, 22)
BREADCRUMB_SEPARATOR = "/"
BREADCRUMB_ACCESSIBLE_NAME = "Fil d'Ariane"
HOME_TRAIL = ("Enquêtes",)
BRAND_NAME = "Lacis"
LOCAL_VERSION_SEPARATOR = "+"


def displayed_version(version: str) -> str:
    return f"v{version.split(LOCAL_VERSION_SEPARATOR, 1)[0]}"


class IconMark(QWidget):
    def __init__(
        self,
        icon: QIcon,
        size: QSize,
        mode: QIcon.Mode = QIcon.Mode.Normal,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon = icon
        self.mode = mode
        self.setFixedSize(size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        try:
            self.icon.paint(painter, QRect(0, 0, self.width(), self.height()), mode=self.mode)
        finally:
            painter.end()


class Breadcrumb(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName(BREADCRUMB_ACCESSIBLE_NAME)
        self.trail_layout = QHBoxLayout(self)
        self.trail_layout.setContentsMargins(0, 0, 0, 0)
        self.trail_layout.setSpacing(8)
        self.step_labels: list[QLabel] = []
        self.set_trail(HOME_TRAIL)

    def set_trail(self, trail: Sequence[str]) -> None:
        while (item := self.trail_layout.takeAt(0)) is not None:
            removed_widget = item.widget()
            if removed_widget is not None:
                removed_widget.setParent(None)
                removed_widget.deleteLater()
        self.step_labels = []
        for position, step in enumerate(trail):
            if position > 0:
                self.trail_layout.addWidget(self.create_label(BREADCRUMB_SEPARATOR, "faint"))
            is_current_step = position == len(trail) - 1
            step_label = self.create_label(step, "current" if is_current_step else "muted")
            self.step_labels.append(step_label)
            self.trail_layout.addWidget(step_label)
        self.setAccessibleDescription(f" {BREADCRUMB_SEPARATOR} ".join(trail))

    def create_label(self, text: str, tone: str) -> QLabel:
        label = QLabel(text, self)
        label.setProperty("tone", tone)
        return label


class HeaderBar(QWidget):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(HEADER_BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.logo_mark = IconMark(icon_factory.logo(), LOGO_SIZE, parent=self)
        self.brand_label = QLabel(BRAND_NAME, self)
        self.brand_label.setProperty("tone", "brand")
        self.breadcrumb = Breadcrumb(self)
        self.version_label = QLabel(displayed_version(__version__), self)
        self.version_label.setProperty("tone", "caption")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.addWidget(self.logo_mark)
        brand_layout.addWidget(self.brand_label)
        layout.addLayout(brand_layout)
        layout.addWidget(self.breadcrumb)
        layout.addStretch(1)
        layout.addWidget(self.version_label)
