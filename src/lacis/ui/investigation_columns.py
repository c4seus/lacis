from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.details import EntityDetails
from lacis.graph.drawing import GraphDrawing
from lacis.overview import InvestigationOverview
from lacis.review import RunningCollection, review_queue
from lacis.signals.facts import counted
from lacis.ui.accessibility import DisclosureButton
from lacis.ui.collection_progress import CollectionProgressPanel
from lacis.ui.entity_sheet import EntitySheet
from lacis.ui.entity_table import EntitiesTab
from lacis.ui.graph_controls import FilterChip, ListViewChip, ZoomToolbar
from lacis.ui.graph_legend import GraphLegend
from lacis.ui.graph_list import GraphList
from lacis.ui.graph_view import GraphView
from lacis.ui.header_bar import create_icon_button
from lacis.ui.journal_table import JournalTab
from lacis.ui.review_queue import ReviewQueueList

QUEUE_TITLE = "À examiner"
GRAPH_EMPTY_TEXT = "Le graphe de l'enquête s'affichera ici."
DETAILS_ACCESSIBLE_NAME = "Panneau de détails"
COLLAPSE_TEXT = "Replier la colonne À examiner"
EXPAND_TEXT = "Déplier la colonne À examiner"
COLLAPSE_TOOLTIP = "Replier"
EXPAND_TOOLTIP = "Déplier"
RAIL_ACCESSIBLE_NAME = "Colonne À examiner repliée"
QUEUE_MINIMUM_WIDTH = 240
OVERLAY_MARGIN = 12
CHIP_SPACING = 6
RAIL_WIDTH = 44
RAIL_COUNT_HEIGHT = 18
GRAPH_MINIMUM_WIDTH = 320
DETAILS_MINIMUM_WIDTH = 340
SHEET_TAB_TITLE = "Fiche"
DETAILS_TABS = (("Signaux", "Les signaux d'alerte de l'enquête s'afficheront ici."),)
ENTITIES_TAB_TITLE = "Entités"
JOURNAL_TAB_TITLE = "Journal"


def counted_title(title: str, count: int) -> str:
    return f"{title} {count}" if count else title


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
            icon_factory.icon("collapse"),
            COLLAPSE_TEXT,
            COLLAPSE_TOOLTIP,
            self.head,
            DisclosureButton(expanded=True, parent=self.head),
        )
        self.head_layout.addWidget(self.collapse_button, 0, Qt.AlignmentFlag.AlignTop)
        self.review_list = ReviewQueueList(icon_factory.colours_provider, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.head)
        layout.addWidget(self.review_list, 1)

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.summary_label.setText(queue_summary(overview))
        self.review_list.show_queue(review_queue(overview))


class QueueRail(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueRail")
        self.setFixedWidth(RAIL_WIDTH)
        self.setAccessibleName(RAIL_ACCESSIBLE_NAME)
        self.expand_button = create_icon_button(
            icon_factory.icon("expand"),
            EXPAND_TEXT,
            EXPAND_TOOLTIP,
            self,
            DisclosureButton(expanded=False, parent=self),
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
    list_toggled = Signal(bool)

    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphArea")
        self.setMinimumWidth(GRAPH_MINIMUM_WIDTH)
        self.filter_chip = FilterChip(icon_factory, self)
        self.list_chip = ListViewChip(icon_factory, self)
        self.views = QStackedWidget(self)
        self.graph_view = GraphView(icon_factory.colours_provider, self.views)
        self.list_page = QWidget(self.views)
        self.graph_list = GraphList(icon_factory.colours_provider, self.list_page)
        self.list_layout = QVBoxLayout(self.list_page)
        self.list_layout.setSpacing(0)
        self.list_layout.addWidget(self.graph_list)
        self.views.addWidget(self.graph_view)
        self.views.addWidget(self.list_page)
        self.zoom_toolbar = ZoomToolbar(icon_factory, self)
        self.empty_label = placeholder(GRAPH_EMPTY_TEXT, self)
        self.empty_label.setWordWrap(False)
        self.legend = GraphLegend(icon_factory.colours_provider, self)
        self.progress_panel = CollectionProgressPanel(self)
        self.graph_layout = QVBoxLayout(self)
        self.graph_layout.setContentsMargins(0, 0, 0, 0)
        self.graph_layout.setSpacing(0)
        self.graph_layout.addWidget(self.views, 1)
        self.filter_chip.filter_changed.connect(self.graph_view.apply_filter)
        self.filter_chip.filter_changed.connect(self.graph_list.apply_filter)
        self.zoom_toolbar.zoom_in_button.clicked.connect(self.graph_view.zoom_in)
        self.zoom_toolbar.zoom_out_button.clicked.connect(self.graph_view.zoom_out)
        self.zoom_toolbar.fit_button.clicked.connect(self.graph_view.fit)
        self.zoom_toolbar.layout_button.clicked.connect(self.layout_requested)
        self.list_chip.toggled.connect(self.show_list)
        QWidget.setTabOrder(self.filter_chip, self.list_chip)
        QWidget.setTabOrder(self.list_chip, self.graph_view)
        QWidget.setTabOrder(self.graph_view, self.graph_list)
        self.show_controls()
        self.place_overlays()

    def is_list_shown(self) -> bool:
        return self.views.currentWidget() is self.list_page

    def shown_view(self) -> QWidget:
        return self.graph_list if self.is_list_shown() else self.graph_view

    def show_list(self, shown: bool) -> None:
        self.list_chip.setChecked(shown)
        if shown == self.is_list_shown():
            return
        had_focus = self.shown_view().hasFocus()
        self.views.setCurrentWidget(self.list_page if shown else self.graph_view)
        self.show_controls()
        if had_focus:
            self.shown_view().setFocus()
        self.list_toggled.emit(shown)

    def reveal(self, identifier: str) -> bool:
        node = self.graph_view.drawing.node(identifier)
        if node is not None and not self.filter_chip.graph_filter.shows(node):
            self.filter_chip.show_everything()
        return self.graph_view.select(identifier)

    def overlays(self) -> list[QWidget]:
        return [
            self.empty_label,
            self.filter_chip,
            self.list_chip,
            self.zoom_toolbar,
            self.legend,
            self.progress_panel,
        ]

    def show_controls(self) -> None:
        shown = bool(self.graph_view.drawing.nodes)
        drawn = shown and not self.is_list_shown()
        self.empty_label.setVisible(not shown)
        self.filter_chip.setVisible(shown)
        self.list_chip.setVisible(shown)
        self.zoom_toolbar.setVisible(drawn)
        self.legend.setVisible(drawn)

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.filter_chip.show_drawing(drawing)
        self.graph_view.show_drawing(drawing)
        self.graph_list.show_drawing(drawing)
        self.show_controls()
        self.place_overlays()

    def place_overlays(self) -> None:
        for overlay in self.overlays():
            overlay.adjustSize()
        self.progress_panel.fit()
        self.empty_label.move(
            (self.width() - self.empty_label.width()) // 2,
            (self.height() - self.empty_label.height()) // 2,
        )
        self.filter_chip.move(OVERLAY_MARGIN, OVERLAY_MARGIN)
        self.list_chip.move(
            OVERLAY_MARGIN + self.filter_chip.width() + CHIP_SPACING, OVERLAY_MARGIN
        )
        chips_height = max(self.filter_chip.height(), self.list_chip.height())
        self.list_layout.setContentsMargins(0, chips_height + 2 * OVERLAY_MARGIN, 0, 0)
        self.legend.move(OVERLAY_MARGIN, self.height() - self.legend.height() - OVERLAY_MARGIN)
        self.zoom_toolbar.move(
            self.width() - self.zoom_toolbar.width() - OVERLAY_MARGIN,
            self.height() - self.zoom_toolbar.height() - OVERLAY_MARGIN,
        )
        self.progress_panel.move(
            self.width() - self.progress_panel.width() - OVERLAY_MARGIN, OVERLAY_MARGIN
        )
        for overlay in self.overlays():
            overlay.raise_()

    def show_collections(self, collections: tuple[RunningCollection, ...]) -> None:
        self.progress_panel.show_collections(collections)
        self.place_overlays()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.place_overlays()


class DetailsPanel(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setMinimumWidth(DETAILS_MINIMUM_WIDTH)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("detailsTabs")
        self.tabs.setAccessibleName(DETAILS_ACCESSIBLE_NAME)
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setDrawBase(False)
        self.entity_sheet = EntitySheet(icon_factory, self.tabs)
        self.tabs.addTab(self.entity_sheet, SHEET_TAB_TITLE)
        self.placeholders: list[QLabel] = []
        for title, empty_text in DETAILS_TABS:
            page = QWidget(self.tabs)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            label = placeholder(empty_text, page)
            self.placeholders.append(label)
            page_layout.addWidget(label)
            page_layout.addStretch(1)
            self.tabs.addTab(page, title)
        self.entities_tab = EntitiesTab(icon_factory.colours_provider, self.tabs)
        self.entities_index = self.tabs.addTab(self.entities_tab, ENTITIES_TAB_TITLE)
        self.journal_tab = JournalTab(icon_factory.colours_provider, self.tabs)
        self.journal_index = self.tabs.addTab(self.journal_tab, JOURNAL_TAB_TITLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)

    def show_details(self, details: EntityDetails | None) -> None:
        self.entity_sheet.show_details(details)

    def show_tab(self, index: int) -> None:
        self.tabs.setCurrentIndex(index % self.tabs.count())
        self.tabs.tabBar().setFocus(Qt.FocusReason.ShortcutFocusReason)

    def show_next_tab(self) -> None:
        self.show_tab(self.tabs.currentIndex() + 1)

    def show_previous_tab(self) -> None:
        self.show_tab(self.tabs.currentIndex() - 1)

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.entities_tab.show_rows(overview.entity_rows)
        self.journal_tab.show_rows(overview.log_rows)
        self.tabs.setTabText(
            self.entities_index, counted_title(ENTITIES_TAB_TITLE, len(overview.entity_rows))
        )
        self.tabs.setTabText(
            self.journal_index, counted_title(JOURNAL_TAB_TITLE, len(overview.log_rows))
        )
