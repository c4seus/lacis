from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.details import EntityDetails
from lacis.graph.expansion import MAXIMUM_DEPTH, MINIMUM_DEPTH
from lacis.ui.flow_layout import FlowLayout
from lacis.ui.graph_legend import KindSwatch

EMPTY_TEXT = "La fiche de l'entité sélectionnée s'affichera ici."
SHEET_ACCESSIBLE_NAME = "Fiche de l'entité"
EXPAND_TEXT = "Étendre"
EXPAND_AGAIN_TEXT = "Étendre à nouveau"
DEPTH_TEXT = "Profondeur {depth}"
DEPTH_MENU_ACCESSIBLE_NAME = "Choisir la profondeur d'extension"
DIRECTORY_TEXT = "Annuaire"
DIRECTORY_TOOLTIP = "Ouvrir la fiche dans l'Annuaire des entreprises"
COPIED_MESSAGE = "« {value} » copié dans le presse-papiers."


def wrapped_label(text: str, tone: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", tone)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return label


def badge(text: str, tone: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", f"badge-{tone}")
    return label


class EntitySheet(QScrollArea):
    expansion_requested = Signal(str, str, int, bool)
    copied = Signal(str)

    def __init__(
        self,
        icon_factory: IconFactory,
        parent: QWidget | None = None,
        open_url: Callable[[QUrl], object] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.icon_factory = icon_factory
        self.open_url = open_url
        self.setObjectName("entitySheet")
        self.setAccessibleName(SHEET_ACCESSIBLE_NAME)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details: EntityDetails | None = None
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.show_details(None)

    def show_details(self, details: EntityDetails | None) -> None:
        self.details = details
        previous = self.takeWidget()
        if previous is not None:
            previous.deleteLater()
        self.content = QWidget()
        self.content.setObjectName("entitySheetContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(4)
        if details is None:
            self.empty_label = wrapped_label(EMPTY_TEXT, "faint", self.content)
            self.content_layout.addWidget(self.empty_label)
        else:
            self.add_head(details)
        self.content_layout.addStretch(1)
        self.setWidget(self.content)

    def add_head(self, details: EntityDetails) -> None:
        kicker = QHBoxLayout()
        kicker.setSpacing(6)
        kind = QFrame(self.content)
        kind.setObjectName("kindBadge")
        kind_layout = QHBoxLayout(kind)
        kind_layout.setContentsMargins(7, 1, 7, 1)
        kind_layout.setSpacing(5)
        kind_layout.addWidget(KindSwatch(details.kind, self.icon_factory.colours_provider, kind))
        self.kind_label = QLabel(details.kind_label, kind)
        self.kind_label.setProperty("tone", "badge-text")
        kind_layout.addWidget(self.kind_label)
        kicker.addWidget(kind)
        self.badge_labels = [
            badge(item.text, item.tone.value, self.content) for item in details.badges
        ]
        for label in self.badge_labels:
            kicker.addWidget(label)
        kicker.addStretch(1)
        self.content_layout.addLayout(kicker)
        self.name_label = wrapped_label(details.name, "heading", self.content)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.content_layout.addWidget(self.name_label)
        self.facts = QWidget(self.content)
        facts_layout = FlowLayout(self.facts, horizontal_spacing=12, vertical_spacing=2)
        self.fact_labels = []
        for fact in details.facts:
            label = QLabel(fact, self.facts)
            label.setProperty("tone", "muted")
            self.fact_labels.append(label)
            facts_layout.addWidget(label)
        self.facts.setVisible(bool(details.facts))
        self.content_layout.addWidget(self.facts)
        self.add_actions(details)
        self.expanded_label = wrapped_label(details.expanded_on, "faint", self.content)
        self.expanded_label.setVisible(details.expanded)
        self.content_layout.addWidget(self.expanded_label)

    def add_actions(self, details: EntityDetails) -> None:
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 10, 0, 2)
        actions.setSpacing(6)
        self.expand_button = QToolButton(self.content)
        self.expand_button.setObjectName("expandButton")
        self.expand_button.setText(EXPAND_AGAIN_TEXT if details.expanded else EXPAND_TEXT)
        self.expand_button.setAccessibleName(self.expand_button.text())
        self.expand_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.expand_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.depth_menu = QMenu(self.expand_button)
        self.depth_menu.setAccessibleName(DEPTH_MENU_ACCESSIBLE_NAME)
        for depth in range(MINIMUM_DEPTH, MAXIMUM_DEPTH + 1):
            action = self.depth_menu.addAction(DEPTH_TEXT.format(depth=depth))
            action.triggered.connect(lambda checked=False, chosen=depth: self.expand(chosen))
        self.expand_button.setMenu(self.depth_menu)
        self.expand_button.clicked.connect(lambda: self.expand(MINIMUM_DEPTH))
        self.expand_button.setVisible(details.expandable)
        self.directory_button = QPushButton(
            self.icon_factory.icon("external"), DIRECTORY_TEXT, self.content
        )
        self.directory_button.setProperty("compact", True)
        self.directory_button.setToolTip(DIRECTORY_TOOLTIP)
        self.directory_button.setVisible(bool(details.directory_url))
        self.directory_button.clicked.connect(self.open_directory)
        self.copy_button = QPushButton(
            self.icon_factory.icon("copy"), details.copy_label, self.content
        )
        self.copy_button.setProperty("compact", True)
        self.copy_button.setProperty("variant", "subtle")
        self.copy_button.clicked.connect(self.copy)
        for widget in (self.expand_button, self.directory_button, self.copy_button):
            actions.addWidget(widget)
        actions.addStretch(1)
        self.content_layout.addLayout(actions)

    def expand(self, depth: int) -> None:
        if self.details is None:
            return
        self.expansion_requested.emit(
            self.details.identifier, self.details.name, depth, self.details.expanded
        )

    def open_directory(self) -> None:
        if self.details is not None and self.details.directory_url:
            self.open_url(QUrl(self.details.directory_url))

    def copy(self) -> None:
        if self.details is None:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.details.copy_value)
        self.copied.emit(COPIED_MESSAGE.format(value=self.details.copy_value))
