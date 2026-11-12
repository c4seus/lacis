from PySide6.QtCore import QByteArray, QSettings, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSplitter, QVBoxLayout, QWidget

from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing
from lacis.overview import InvestigationOverview
from lacis.storage.investigations import Investigation
from lacis.ui.investigation_columns import DetailsPanel, GraphArea, QueueColumn, QueueRail

COLUMNS_SETTING = "investigation/columns"
QUEUE_COLLAPSED_SETTING = "investigation/queue_collapsed"
DEFAULT_COLUMN_WIDTHS = (320, 700, 420)
COUNTERS_ACCESSIBLE_NAME = "Compteurs de l'enquête"
UNAVAILABLE_TEXT = "?"
FIRST_PLURAL = 2


def noun_for(count: int | None, singular: str, plural: str) -> str:
    return singular if count is not None and count < FIRST_PLURAL else plural


class Counter(QWidget):
    def __init__(
        self, singular: str, plural: str, *, alert: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.singular = singular
        self.plural = plural
        self.alert = alert
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.number_label = QLabel(self)
        self.noun_label = QLabel(self)
        self.noun_label.setProperty("tone", "muted")
        layout.addWidget(self.number_label)
        layout.addWidget(self.noun_label)
        self.show_count(0)

    def show_count(self, count: int | None) -> None:
        self.number_label.setText(UNAVAILABLE_TEXT if count is None else str(count))
        tone = "counter-alert" if self.alert and count else "counter"
        self.number_label.setProperty("tone", tone)
        self.number_label.style().unpolish(self.number_label)
        self.number_label.style().polish(self.number_label)
        self.noun_label.setText(noun_for(count, self.singular, self.plural))

    def text(self) -> str:
        return f"{self.number_label.text()} {self.noun_label.text()}"


class InvestigationHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("investigationHeader")
        self.name_label = QLabel(self)
        self.name_label.setProperty("tone", "investigation-title")
        self.question_label = QLabel(self)
        self.question_label.setProperty("tone", "muted")
        self.question_label.setWordWrap(True)
        self.entity_counter = Counter("entité", "entités", parent=self)
        self.link_counter = Counter("lien", "liens", parent=self)
        self.homonym_counter = Counter("homonyme confirmé", "homonymes confirmés", parent=self)
        self.signal_counter = Counter("signal", "signaux", alert=True, parent=self)
        self.counters = QWidget(self)
        self.counters.setAccessibleName(COUNTERS_ACCESSIBLE_NAME)
        counter_layout = QHBoxLayout(self.counters)
        counter_layout.setContentsMargins(0, 0, 0, 0)
        counter_layout.setSpacing(14)
        for counter in self.all_counters():
            counter.setParent(self.counters)
            counter_layout.addWidget(counter)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.name_label)
        titles.addWidget(self.question_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(24)
        layout.addLayout(titles, 1)
        layout.addWidget(self.counters, 0, Qt.AlignmentFlag.AlignVCenter)

    def all_counters(self) -> tuple[Counter, ...]:
        return (self.entity_counter, self.link_counter, self.homonym_counter, self.signal_counter)

    def show_investigation(self, investigation: Investigation) -> None:
        self.name_label.setText(investigation.name)
        self.question_label.setText(investigation.question)
        self.question_label.setVisible(bool(investigation.question))

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.entity_counter.show_count(overview.entities)
        self.link_counter.show_count(overview.links)
        self.homonym_counter.show_count(overview.confirmed_homonyms)
        self.signal_counter.show_count(overview.signals)
        self.signal_counter.setToolTip(overview.signal_problem)
        self.counters.setAccessibleDescription(
            ", ".join(counter.text() for counter in self.all_counters())
        )


class InvestigationPage(QWidget):
    queue_toggled = Signal(bool)
    entities_moved = Signal(dict)
    decision_requested = Signal(object, object, object)
    expansion_requested = Signal(str, str, int, bool)
    entity_selected = Signal(str)
    notices_refresh_requested = Signal(str, str)

    def __init__(
        self, settings: QSettings, icon_factory: IconFactory, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("investigationPage")
        self.header = InvestigationHeader(self)
        self.selected_entity: str | None = None
        self.queue_column = QueueColumn(icon_factory, self)
        self.queue_column.collapse_button.clicked.connect(self.collapse_queue)
        self.queue_rail = QueueRail(icon_factory, self)
        self.queue_rail.expand_button.clicked.connect(self.expand_queue)
        self.graph_area = GraphArea(icon_factory, self)
        self.details_panel = DetailsPanel(icon_factory, self)
        self.graph_view = self.graph_area.graph_view
        self.graph_view.selection_changed.connect(self.follow_selection)
        self.graph_view.entities_moved.connect(self.entities_moved)
        review_list = self.queue_column.review_list
        review_list.entity_chosen.connect(lambda identifier: self.show_entity(identifier, ""))
        review_list.decision_requested.connect(self.decision_requested)
        review_list.expansion_requested.connect(
            lambda identifier, label: self.expansion_requested.emit(identifier, label, 1, False)
        )
        sheet = self.details_panel.entity_sheet
        sheet.entity_chosen.connect(lambda identifier: self.show_entity(identifier, ""))
        sheet.expansion_requested.connect(self.expansion_requested)
        sheet.notices_refresh_requested.connect(self.notices_refresh_requested)
        self.details_panel.entities_tab.entity_chosen.connect(
            lambda identifier: self.show_entity(identifier, "")
        )
        self.columns = QSplitter(Qt.Orientation.Horizontal, self)
        self.columns.setObjectName("investigationColumns")
        self.columns.setChildrenCollapsible(False)
        self.columns.setHandleWidth(1)
        for column in (self.queue_column, self.graph_area, self.details_panel):
            self.columns.addWidget(column)
        self.columns.setStretchFactor(1, 1)
        self.restore_columns()
        self.columns.splitterMoved.connect(self.save_columns)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self.queue_rail)
        body.addWidget(self.columns, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addLayout(body, 1)
        self.show_queue(not self.settings.value(QUEUE_COLLAPSED_SETTING, False, type=bool))

    def restore_columns(self) -> None:
        state = self.settings.value(COLUMNS_SETTING)
        if not isinstance(state, QByteArray) or not self.columns.restoreState(state):
            self.columns.setSizes(list(DEFAULT_COLUMN_WIDTHS))

    def save_columns(self) -> None:
        self.settings.setValue(COLUMNS_SETTING, self.columns.saveState())

    def is_queue_collapsed(self) -> bool:
        return self.queue_column.isHidden()

    def show_queue(self, shown: bool) -> None:
        self.queue_column.setVisible(shown)
        self.queue_rail.setVisible(not shown)
        self.settings.setValue(QUEUE_COLLAPSED_SETTING, not shown)
        self.queue_toggled.emit(shown)

    def collapse_queue(self) -> None:
        if self.is_queue_collapsed():
            return
        self.save_columns()
        self.show_queue(False)
        self.queue_rail.expand_button.setFocus()

    def expand_queue(self) -> None:
        if not self.is_queue_collapsed():
            return
        self.show_queue(True)
        self.restore_columns()
        self.queue_column.collapse_button.setFocus()

    def toggle_queue(self, shown: bool) -> None:
        if shown:
            self.expand_queue()
        else:
            self.collapse_queue()

    def show_investigation(self, investigation: Investigation) -> None:
        self.header.show_investigation(investigation)
        self.selected_entity = None
        self.graph_area.show_drawing(GraphDrawing())

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.header.show_overview(overview)
        self.queue_column.show_overview(overview)
        self.queue_rail.show_overview(overview)
        self.graph_area.show_drawing(overview.drawing)
        self.details_panel.show_overview(overview)
        self.details_panel.entities_tab.mark_selected(self.selected_entity)

    def show_entity(self, identifier: str, label: str) -> None:
        self.graph_area.reveal(identifier)

    def follow_selection(self, identifier: str) -> None:
        self.selected_entity = identifier or None
        self.queue_column.review_list.mark_selected(self.selected_entity)
        self.details_panel.entities_tab.mark_selected(self.selected_entity)
        self.entity_selected.emit(identifier)
