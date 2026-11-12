from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.details import EntityDetails
from lacis.ui.flow_layout import FlowLayout
from lacis.ui.graph_legend import KindSwatch

EMPTY_TEXT = "La fiche de l'entité sélectionnée s'affichera ici."
SHEET_ACCESSIBLE_NAME = "Fiche de l'entité"


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
    def __init__(
        self,
        icon_factory: IconFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.icon_factory = icon_factory
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
        self.expanded_label = wrapped_label(details.expanded_on, "faint", self.content)
        self.expanded_label.setVisible(details.expanded)
        self.content_layout.addWidget(self.expanded_label)
