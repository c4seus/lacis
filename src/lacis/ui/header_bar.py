from collections.abc import Sequence
from typing import override

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QFocusEvent,
    QIcon,
    QKeyEvent,
    QPainter,
    QPaintEvent,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QWidget,
)

from lacis import __version__
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.ui.help_menu import HelpMenu
from lacis.ui.theme_menu import ThemeMenu

HEADER_BAR_HEIGHT = 52
LOGO_SIZE = QSize(22, 22)
SEARCH_ICON_SIZE = QSize(16, 16)
SEARCH_ICON_LEFT_MARGIN = 12
SEARCH_TEXT_LEFT_MARGIN = 22
BREADCRUMB_SEPARATOR = "/"
BREADCRUMB_ACCESSIBLE_NAME = "Fil d'Ariane"
HOME_TRAIL = ("Enquêtes",)
BRAND_NAME = "Lacis"
LOCAL_VERSION_SEPARATOR = "+"
SEARCH_PLACEHOLDER = "Dénomination, SIREN, SIRET, dirigeant ou adresse"
SEARCH_ACCESSIBLE_NAME = "Rechercher une entreprise"
SEARCH_BUTTON_TEXT = "Rechercher"
SEARCH_MAXIMUM_WIDTH = 760
ICON_BUTTON_SIZE = QSize(32, 32)
HELP_BUTTON_NAME = "Aide"
THEME_BUTTON_NAME = "Thème de l'interface"
THEME_BUTTON_TOOLTIP = "Thème"
THEME_PREFERENCE_ICONS = {
    ThemePreference.SYSTEM: "monitor",
    ThemePreference.LIGHT: "sun",
    ThemePreference.DARK: "moon",
}


NAVIGATION_KEYS = {Qt.Key.Key_Down: 1, Qt.Key.Key_Up: -1}
CHOICE_KEYS = frozenset({Qt.Key.Key_Return, Qt.Key.Key_Enter})


class SearchField(QLineEdit):
    moved = Signal(int)
    chosen = Signal()
    closed = Signal()
    left = Signal()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = Qt.Key(event.key())
        if key in NAVIGATION_KEYS:
            self.moved.emit(NAVIGATION_KEYS[key])
            return
        if key in CHOICE_KEYS:
            self.chosen.emit()
            return
        if key == Qt.Key.Key_Escape:
            self.closed.emit()
            return
        super().keyPressEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.left.emit()


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


def create_icon_button(
    icon: QIcon, accessible_name: str, tooltip: str, parent: QWidget
) -> QToolButton:
    button = QToolButton(parent)
    button.setProperty("variant", "icon")
    button.setIcon(icon)
    button.setFixedSize(ICON_BUTTON_SIZE)
    button.setAccessibleName(accessible_name)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
    return button


class HeaderBar(QWidget):
    def __init__(
        self,
        icon_factory: IconFactory,
        theme_controller: ThemeController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_factory = icon_factory
        self.setObjectName("headerBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(HEADER_BAR_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.create_brand()
        self.create_search()
        self.create_actions(theme_controller)
        self.arrange()

    def create_brand(self) -> None:
        self.logo_mark = IconMark(self.icon_factory.logo(), LOGO_SIZE, parent=self)
        self.brand_label = QLabel(BRAND_NAME, self)
        self.brand_label.setProperty("tone", "brand")
        self.breadcrumb = Breadcrumb(self)

    def create_search(self) -> None:
        self.search_field = SearchField(self)
        self.search_field.setProperty("variant", "search")
        self.search_field.setPlaceholderText(SEARCH_PLACEHOLDER)
        self.search_field.setAccessibleName(SEARCH_ACCESSIBLE_NAME)
        self.search_field.setTextMargins(SEARCH_TEXT_LEFT_MARGIN, 0, 0, 0)
        self.search_icon = IconMark(
            self.icon_factory.icon("search"),
            SEARCH_ICON_SIZE,
            QIcon.Mode.Disabled,
            self.search_field,
        )
        self.search_button = QPushButton(SEARCH_BUTTON_TEXT, self)
        self.search_button.setProperty("variant", "primary")
        self.set_search_enabled(False)

    def create_actions(self, theme_controller: ThemeController) -> None:
        self.help_button = create_icon_button(
            self.icon_factory.icon("help"), HELP_BUTTON_NAME, HELP_BUTTON_NAME, self
        )
        self.help_menu = HelpMenu(self.help_button)
        self.help_button.setMenu(self.help_menu)
        self.theme_button = create_icon_button(
            self.icon_factory.icon(THEME_PREFERENCE_ICONS[theme_controller.preference]),
            THEME_BUTTON_NAME,
            THEME_BUTTON_TOOLTIP,
            self,
        )
        self.theme_menu = ThemeMenu(theme_controller, self.theme_button)
        for preference, action in self.theme_menu.preference_actions.items():
            action.setIcon(self.icon_factory.icon(THEME_PREFERENCE_ICONS[preference]))
        self.theme_button.setMenu(self.theme_menu)
        theme_controller.preference_changed.connect(self.show_theme_preference)
        self.version_label = QLabel(displayed_version(__version__), self)
        self.version_label.setProperty("tone", "caption")

    def arrange(self) -> None:
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)
        brand_layout.addWidget(self.logo_mark)
        brand_layout.addWidget(self.brand_label)

        search_area = QWidget(self)
        search_area.setMaximumWidth(SEARCH_MAXIMUM_WIDTH)
        search_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        search_layout = QHBoxLayout(search_area)
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)
        search_layout.addWidget(self.search_field, 1)
        search_layout.addWidget(self.search_button)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.addWidget(self.help_button)
        actions_layout.addWidget(self.theme_button)
        actions_layout.addWidget(self.version_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)
        layout.addLayout(brand_layout)
        layout.addWidget(self.breadcrumb)
        layout.addStretch(1)
        layout.addWidget(search_area, 4)
        layout.addStretch(1)
        layout.addLayout(actions_layout)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.place_search_icon()

    def place_search_icon(self) -> None:
        self.search_icon.move(
            SEARCH_ICON_LEFT_MARGIN,
            (self.search_field.height() - self.search_icon.height()) // 2,
        )

    def show_theme_preference(self, preference: ThemePreference) -> None:
        self.theme_button.setIcon(self.icon_factory.icon(THEME_PREFERENCE_ICONS[preference]))

    def set_search_enabled(self, enabled: bool) -> None:
        self.search_field.setEnabled(enabled)
        self.search_button.setEnabled(enabled)
