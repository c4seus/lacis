from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing
from lacis.overview import InvestigationOverview
from lacis.signals.facts import counted
from lacis.ui.graph_controls import FilterChip, ZoomToolbar
from lacis.ui.graph_legend import GraphLegend
from lacis.ui.graph_view import GraphView
from lacis.ui.header_bar import create_icon_button

QUEUE_TITLE = "À examiner"
QUEUE_EMPTY_TEXT = "Les signaux, les homonymes et les pistes à examiner s'afficheront ici."
GRAPH_EMPTY_TEXT = "Le graphe de l'enquête s'affichera ici."
DETAILS_ACCESSIBLE_NAME = "Panneau de détails"
COLLAPSE_TEXT = "Replier la colonne À examiner"
EXPAND_TEXT = "Déplier la colonne À examiner"
COLLAPSE_TOOLTIP = "Replier"
EXPAND_TOOLTIP = "Déplier"
RAIL_ACCESSIBLE_NAME = "Colonne À examiner repliée"
QUEUE_MINIMUM_WIDTH = 240
OVERLAY_MARGIN = 12
RAIL_WIDTH = 44
RAIL_COUNT_HEIGHT = 18
GRAPH_MINIMUM_WIDTH = 320
DETAILS_MINIMUM_WIDTH = 340
DETAILS_TABS = (
    ("Fiche", "La fiche de l'entité sélectionnée s'affichera ici."),
    ("Signaux", "Les signaux d'alerte de l'enquête s'afficheront ici."),
    ("Entités", "La liste des entités de l'enquête s'affichera ici."),
    ("Journal", "Le journal de collecte de l'enquête s'affichera ici."),
)


def queue_summary(overview: InvestigationOverview) -> str:
    signals = (
        "signaux indisponibles"
        if overview.signals is None
        else counted(overview.signals, "signal", "signaux")
    )
    homonyms = counted(overview.pending_homonyms, "homonyme", "homonymes")
    leads = counted(overview.leads, "piste", "pistes")
    return f"{signals}, {homonyms}, {leads}"


def placeholder(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", "faint")
    label.setWordWrap(True)
    return label


class QueueColumn(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueColumn")
        self.setMinimumWidth(QUEUE_MINIMUM_WIDTH)
        self.title_label = QLabel(QUEUE_TITLE.upper(), self)
        self.title_label.setProperty("tone", "column-title")
        self.title_label.setAccessibleName(QUEUE_TITLE)
        self.summary_label = QLabel(self)
        self.summary_label.setProperty("tone", "muted")
        self.head = QFrame(self)
        self.head.setObjectName("columnHead")
        self.head_layout = QHBoxLayout(self.head)
        self.head_layout.setContentsMargins(14, 14, 10, 12)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(self.title_label)
        titles.addWidget(self.summary_label)
        self.head_layout.addLayout(titles, 1)
        self.collapse_button = create_icon_button(
            icon_factory.icon("collapse"), COLLAPSE_TEXT, COLLAPSE_TOOLTIP, self.head
        )
        self.head_layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignTop)
        self.empty_label = placeholder(QUEUE_EMPTY_TEXT, self)
        body = QVBoxLayout()
        body.setContentsMargins(14, 14, 14, 14)
        body.addWidget(self.empty_label)
        body.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.head)
        layout.addLayout(body, 1)

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.summary_label.setText(queue_summary(overview))


class QueueRail(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueRail")
        self.setFixedWidth(RAIL_WIDTH)
        self.setAccessibleName(RAIL_ACCESSIBLE_NAME)
        self.expand_button = create_icon_button(
            icon_factory.icon("expand"), EXPAND_TEXT, EXPAND_TOOLTIP, self
        )
        self.count_label = QLabel(self)
        self.count_label.setProperty("tone", "rail-count")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.count_label.setFixedHeight(RAIL_COUNT_HEIGHT)
        self.count_label.hide()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 12, 6, 12)
        layout.setSpacing(6)
        layout.addWidget(self.expand_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.count_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.count_label.setText(str(overview.signals or ""))
        self.count_label.setVisible(bool(overview.signals))
        self.expand_button.setAccessibleDescription(queue_summary(overview))


class GraphArea(QFrame):
    layout_requested = Signal()

    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphArea")
        self.setMinimumWidth(GRAPH_MINIMUM_WIDTH)
        self.filter_chip = FilterChip(icon_factory, self)
        self.graph_view = GraphView(icon_factory.colours_provider, self)
        self.zoom_toolbar = ZoomToolbar(icon_factory, self)
        self.empty_label = placeholder(GRAPH_EMPTY_TEXT, self)
        self.empty_label.setWordWrap(False)
        self.legend = GraphLegend(icon_factory.colours_provider, self)
        self.graph_layout = QVBoxLayout(self)
        self.graph_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_layout.setSpacing(0)
        self.graph_layout.addWidget(self.graph_view, 1)
        self.filter_chip.filter_changed.connect(self.graph_view.apply_filter)
        self.zoom_toolbar.zoom_in_button.clicked.connect(self.graph_view.zoom_in)
        self.zoom_toolbar.zoom_out_button.clicked.connect(self.graph_view.zoom_out)
        self.zoom_toolbar.fit_button.clicked.connect(self.graph_view.fit)
        self.zoom_toolbar.layout_button.clicked.connect(self.layout_requested)
        self.show_controls(False)
        self.place_overlays()

    def overlays(self) -> list[QWidget]:
        return [self.empty_label, self.filter_chip, self.zoom_toolbar, self.legend]

    def show_controls(self, shown: bool) -> None:
        self.empty_label.setVisible(not shown)
        for control in (self.filter_chip, self.zoom_toolbar, self.legend):
            control.setVisible(shown)

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.filter_chip.show_drawing(drawing)
        self.graph_view.show_drawing(drawing)
        self.show_controls(bool(drawing.nodes))
        self.place_overlays()

    def place_overlays(self) -> None:
        for overlay in self.overlays():
            overlay.adjustSize()
        self.empty_label.move(
            (self.width() - self.empty_label.width()) // 2,
            (self.height() - self.empty_label.height()) // 2,
        )
        self.filter_chip.move(OVERLAY_MARGIN, OVERLAY_MARGIN)
        self.legend.move(OVERLAY_MARGIN, self.height() - self.legend.height() - OVERLAY_MARGIN)
        self.zoom_toolbar.move(
            self.width() - self.zoom_toolbar.width() - OVERLAY_MARGIN,
            self.height() - self.zoom_toolbar.height() - OVERLAY_MARGIN,
        )
        for overlay in self.overlays():
            overlay.raise_()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.place_overlays()


class DetailsPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setMinimumWidth(DETAILS_MINIMUM_WIDTH)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("detailsTabs")
        self.tabs.setAccessibleName(DETAILS_ACCESSIBLE_NAME)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        for title, empty_text in DETAILS_TABS:
            page = QWidget(self.tabs)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            page_layout.addWidget(placeholder(empty_text, page))
            page_layout.addStretch(1)
            self.tabs.addTab(page, title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
