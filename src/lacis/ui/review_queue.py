from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import ColoursProvider
from lacis.graph.drawing import KIND_LABELS
from lacis.review import (
    NO_SIGNAL_TEXT,
    UNAVAILABLE_SIGNALS_PREFIX,
    QueueEntity,
    ReviewQueue,
)
from lacis.ui.graph_legend import KindSwatch

QUEUE_LIST_ACCESSIBLE_NAME = "Éléments à examiner"
SCORE_PREFIX = "score "
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
        self.score_label = QLabel(entity.written_score, self)
        self.score_label.setProperty("tone", "queue-score")
        self.score_label.setVisible(entity.score is not None)
        self.detail_label = detail_label(entity.explanation, self)
        self.first_line = QHBoxLayout()
        self.first_line.setSpacing(8)
        self.first_line.addWidget(KindSwatch(entity.kind, colours_provider, self))
        self.first_line.addWidget(self.title_label, 1)
        self.first_line.addWidget(self.score_label, 0, Qt.AlignmentFlag.AlignTop)
        self.row_layout = QVBoxLayout(self)
        self.row_layout.setContentsMargins(10, 9, 10, 9)
        self.row_layout.setSpacing(3)
        self.row_layout.addLayout(self.first_line)
        self.row_layout.addWidget(self.detail_label)
        self.describe()

    def describe(self) -> None:
        parts = [self.title_label.text(), KIND_LABELS[self.entity.kind]]
        if self.entity.score is not None:
            parts.append(f"{SCORE_PREFIX}{self.entity.written_score}")
        self.setAccessibleName(", ".join(parts))
        self.setAccessibleDescription(self.entity.explanation)

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


class ReviewQueueList(QScrollArea):
    entity_chosen = Signal(str)

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
        self.group_labels: list[QLabel] = []
        self.empty_labels: list[QLabel] = []
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
        self.group_labels = []
        self.empty_labels = []
        self.add_signals(queue)
        self.content_layout.addStretch(1)
        self.setWidget(self.content)
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

    def mark_selected(self, identifier: str | None) -> None:
        self.selected_identifier = identifier
        for row in self.rows:
            row.set_selected(row.entity.identifier == identifier)

    @property
    def group_titles(self) -> list[str]:
        return [label.accessibleName() for label in self.group_labels]
