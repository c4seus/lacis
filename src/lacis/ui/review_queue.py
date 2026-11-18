from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import ColoursProvider
from lacis.graph.drawing import KIND_LABELS
from lacis.review import (
    NO_HOMONYM_TEXT,
    NO_LEAD_TEXT,
    NO_SIGNAL_TEXT,
    UNAVAILABLE_SIGNALS_PREFIX,
    HomonymEntry,
    QueueEntity,
    ReviewQueue,
)
from lacis.storage.homonym_decisions import HomonymDecision
from lacis.ui.accessibility import ScoreLabel
from lacis.ui.flow_layout import FlowLayout
from lacis.ui.focus_chain import place_after
from lacis.ui.graph_legend import KindSwatch

QUEUE_LIST_ACCESSIBLE_NAME = "Éléments à examiner"
HOMONYMS_TITLE = "Homonymes à vérifier"
LEADS_TITLE = "Pistes non étendues"
SAME_PERSON_TEXT = "Même personne"
DIFFERENT_PERSON_TEXT = "Personne différente"
EXPAND_TEXT = "Étendre"
EXPANDING_TEXT = "Extension…"
SCORE_PREFIX = "score "
FIRST_LINE_SPACING = 8
ACTIVATING_KEYS = {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}


def refresh_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def detail_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", "queue-detail")
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return label


def group_title(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text.upper(), parent)
    label.setProperty("tone", "queue-group")
    label.setAccessibleName(text)
    label.setWordWrap(True)
    return label


class QueueRow(QFrame):
    activated = Signal(str)

    def __init__(
        self,
        entity: QueueEntity,
        colours_provider: ColoursProvider,
        title: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.entity = entity
        self.setObjectName("queueRow")
        self.setProperty("selected", False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.title_label = QLabel(title or entity.label, self)
        self.title_label.setProperty("tone", "queue-title")
        self.title_label.setWordWrap(True)
        self.score_label = ScoreLabel(entity.written_score, entity.written_score, self)
        self.score_label.setProperty("tone", "queue-score")
        self.score_label.setVisible(entity.score is not None)
        self.detail_label = detail_label(entity.explanation, self)
        self.swatch = KindSwatch(entity.kind, colours_provider, self)
        self.first_line = QHBoxLayout()
        self.first_line.setSpacing(FIRST_LINE_SPACING)
        self.first_line.addWidget(self.swatch)
        self.first_line.addWidget(self.title_label, 1)
        self.corner_line = QHBoxLayout()
        self.corner_line.setContentsMargins(0, 0, 0, 0)
        self.corner_line.addStretch(1)
        self.row_layout = QVBoxLayout(self)
        self.row_layout.setContentsMargins(10, 9, 10, 9)
        self.row_layout.setSpacing(3)
        self.row_layout.addLayout(self.first_line)
        self.row_layout.addLayout(self.corner_line)
        self.row_layout.addWidget(self.detail_label)
        self.corner: QWidget = self.score_label
        self.corner_beside_title = False
        self.set_corner(self.score_label)
        self.describe()

    def set_corner(self, widget: QWidget) -> None:
        for layout in (self.first_line, self.corner_line):
            layout.removeWidget(self.corner)
        self.corner = widget
        widget.setMinimumWidth(1)
        self.corner_beside_title = False
        self.place_corner(beside_title=True)

    def corner_fits_beside_title(self) -> bool:
        margins = self.row_layout.contentsMargins()
        needed = (
            margins.left()
            + margins.right()
            + self.swatch.minimumWidth()
            + 2 * FIRST_LINE_SPACING
            + self.title_label.minimumSizeHint().width()
            + self.corner.sizeHint().width()
        )
        return self.width() >= needed

    def place_corner(self, *, beside_title: bool) -> None:
        if beside_title == self.corner_beside_title:
            return
        self.corner_beside_title = beside_title
        if beside_title:
            self.corner_line.removeWidget(self.corner)
            self.first_line.addWidget(self.corner, 0, Qt.AlignmentFlag.AlignTop)
        else:
            self.first_line.removeWidget(self.corner)
            self.corner_line.insertWidget(0, self.corner)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.place_corner(beside_title=self.corner_fits_beside_title())

    def describe(self) -> None:
        parts = [self.title_label.text(), KIND_LABELS[self.entity.kind]]
        if self.entity.score is not None:
            parts.append(f"{SCORE_PREFIX}{self.entity.written_score}")
        self.setAccessibleName(", ".join(parts))
        self.setAccessibleDescription(self.entity.explanation)

    def add_actions(self, buttons: list[QPushButton]) -> None:
        actions = FlowLayout(horizontal_spacing=6, vertical_spacing=6)
        actions.setContentsMargins(0, 4, 0, 0)
        for button in buttons:
            actions.addWidget(button)
        self.row_layout.addLayout(actions)

    def set_selected(self, selected: bool) -> None:
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        refresh_style(self)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.activated.emit(self.entity.identifier)
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in ACTIVATING_KEYS:
            self.activated.emit(self.entity.identifier)
            event.accept()
            return
        super().keyPressEvent(event)


def action_button(text: str, accessible_name: str, parent: QWidget) -> QPushButton:
    button = QPushButton(text, parent)
    button.setProperty("compact", True)
    button.setAccessibleName(accessible_name)
    return button


class ReviewQueueList(QScrollArea):
    entity_chosen = Signal(str)
    decision_requested = Signal(object, object, object)
    expansion_requested = Signal(str, str)

    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("reviewQueue")
        self.setAccessibleName(QUEUE_LIST_ACCESSIBLE_NAME)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.colours_provider = colours_provider
        self.queue = ReviewQueue((), (), ())
        self.rows: list[QueueRow] = []
        self.expand_buttons: dict[str, QPushButton] = {}
        self.lead_rows: dict[str, QueueRow] = {}
        self.decision_buttons: list[QPushButton] = []
        self.group_labels: list[QLabel] = []
        self.empty_labels: list[QLabel] = []
        self.expanding: set[str] = set()
        self.selected_identifier: str | None = None
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.show_queue(self.queue)

    def show_queue(self, queue: ReviewQueue) -> None:
        self.queue = queue
        previous = self.takeWidget()
        if previous is not None:
            previous.deleteLater()
        self.content = QWidget()
        self.content.setObjectName("reviewQueueContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 4, 8, 8)
        self.content_layout.setSpacing(4)
        self.rows = []
        self.expand_buttons = {}
        self.lead_rows = {}
        self.decision_buttons = []
        self.group_labels = []
        self.empty_labels = []
        self.add_signals(queue)
        self.add_homonyms(queue)
        self.add_leads(queue)
        self.content_layout.addStretch(1)
        self.setWidget(self.content)
        place_after(self, self.content)
        self.mark_selected(self.selected_identifier)

    def add_group_title(self, text: str) -> None:
        label = group_title(text, self.content)
        self.group_labels.append(label)
        self.content_layout.addWidget(label)

    def add_empty_text(self, text: str) -> None:
        label = detail_label(text, self.content)
        label.setProperty("tone", "queue-empty")
        self.empty_labels.append(label)
        self.content_layout.addWidget(label)

    def add_row(self, entity: QueueEntity, title: str = "") -> QueueRow:
        row = QueueRow(entity, self.colours_provider, title, self.content)
        row.activated.connect(self.entity_chosen)
        self.rows.append(row)
        self.content_layout.addWidget(row)
        return row

    def add_signals(self, queue: ReviewQueue) -> None:
        if queue.signal_problem:
            self.add_group_title(UNAVAILABLE_SIGNALS_PREFIX.removesuffix(" : "))
            self.add_empty_text(queue.signal_problem)
            return
        if not queue.signal_groups:
            self.add_group_title(NO_SIGNAL_TEXT)
            return
        for group in queue.signal_groups:
            self.add_group_title(group.title)
            for entity in group.entities:
                self.add_row(entity)

    def add_homonyms(self, queue: ReviewQueue) -> None:
        self.add_group_title(HOMONYMS_TITLE)
        if not queue.homonyms:
            self.add_empty_text(NO_HOMONYM_TEXT)
        for entry in queue.homonyms:
            self.add_homonym(entry)

    def add_homonym(self, entry: HomonymEntry) -> None:
        row = self.add_row(entry.first, entry.title)
        badge = QLabel(entry.confidence_label, row)
        badge.setProperty("tone", "badge-outline")
        row.score_label.hide()
        row.set_corner(badge)
        row.setAccessibleName(f"{entry.title}, confiance {entry.confidence_label.lower()}")
        people = (entry.first.identifier, entry.second.identifier)
        labels = (entry.first.label, entry.second.label)
        same = action_button(SAME_PERSON_TEXT, f"{SAME_PERSON_TEXT} : {entry.title}", row)
        different = action_button(
            DIFFERENT_PERSON_TEXT, f"{DIFFERENT_PERSON_TEXT} : {entry.title}", row
        )
        same.setProperty("variant", "primary")
        same.clicked.connect(
            lambda: self.decision_requested.emit(people, labels, HomonymDecision.SAME_PERSON)
        )
        different.clicked.connect(
            lambda: self.decision_requested.emit(people, labels, HomonymDecision.DIFFERENT_PERSON)
        )
        self.decision_buttons.extend([same, different])
        row.add_actions([same, different])

    def add_leads(self, queue: ReviewQueue) -> None:
        self.add_group_title(LEADS_TITLE)
        if not queue.leads:
            self.add_empty_text(NO_LEAD_TEXT)
        for lead in queue.leads:
            row = self.add_row(lead)
            button = action_button(EXPAND_TEXT, f"{EXPAND_TEXT} {lead.label}", row)
            button.clicked.connect(
                lambda checked=False, chosen=lead: self.expansion_requested.emit(
                    chosen.identifier, chosen.label
                )
            )
            self.expand_buttons[lead.identifier] = button
            self.lead_rows[lead.identifier] = row
            row.set_corner(button)
        self.show_expanding(self.expanding)

    def show_expanding(self, expanding: set[str]) -> None:
        self.expanding = set(expanding)
        for identifier, button in self.expand_buttons.items():
            running = identifier in self.expanding
            if running and button.hasFocus():
                self.lead_rows[identifier].setFocus(Qt.FocusReason.OtherFocusReason)
            button.setEnabled(not running)
            button.setText(EXPANDING_TEXT if running else EXPAND_TEXT)

    def mark_selected(self, identifier: str | None) -> None:
        self.selected_identifier = identifier
        for row in self.rows:
            row.set_selected(row.entity.identifier == identifier)

    @property
    def group_titles(self) -> list[str]:
        return [label.accessibleName() for label in self.group_labels]
