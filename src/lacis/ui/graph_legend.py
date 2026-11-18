from typing import override

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPainter, QPaintEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lacis.design.icons import ColoursProvider
from lacis.graph.drawing import SHAPES, EdgeKind
from lacis.signals.signal import Severity
from lacis.storage.entities import EntityKind
from lacis.ui.flow_layout import FlowLayout
from lacis.ui.graph_view import (
    NOTE_MARKER_HEIGHT,
    NOTE_MARKER_WIDTH,
    RING_COUNTS,
    RING_GAP,
    RING_WIDTH,
    arrow_head,
    draw_note_page,
    edge_colour,
    edge_pen,
    kind_colour,
    note_page_path,
    ring_pen,
    shape_path,
)

LEGEND_ACCESSIBLE_NAME = "Légende du graphe"
LEGEND_SWATCH_SIZE = 10
RING_SWATCH_SIZE = 16
LINK_SWATCH_WIDTH = 22
SIGNAL_LEGEND_TEXT = "Signal :"
NOTE_LEGEND_TEXT = "Note"
KIND_ENTRIES = (
    (EntityKind.COMPANY, "Entreprise"),
    (EntityKind.PERSON, "Personne"),
    (EntityKind.ADDRESS, "Adresse"),
    (EntityKind.ESTABLISHMENT, "Établissement"),
    (EntityKind.FOREIGN_COMPANY, "Étranger"),
)
LINK_ENTRIES = (
    (EdgeKind.DIRECTS, "Mandat"),
    (EdgeKind.STRUCTURE, "Rattachement"),
    (EdgeKind.IDENTITY, "Même personne"),
)
SEVERITY_ENTRIES = (
    (Severity.HIGH, "fort"),
    (Severity.MEDIUM, "moyen"),
    (Severity.LOW, "faible"),
)


class KindSwatch(QWidget):
    def __init__(
        self, kind: EntityKind, colours_provider: ColoursProvider, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.colours_provider = colours_provider
        self.setFixedSize(LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(kind_colour(self.colours_provider(), self.kind)))
        size = LEGEND_SWATCH_SIZE * (0.6 if self.kind is EntityKind.ESTABLISHMENT else 0.9)
        painter.drawPath(shape_path(SHAPES[self.kind], size))
        painter.end()


class LinkSwatch(QWidget):
    def __init__(
        self, kind: EdgeKind, colours_provider: ColoursProvider, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.colours_provider = colours_provider
        self.setFixedSize(LINK_SWATCH_WIDTH, LEGEND_SWATCH_SIZE)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        colours = self.colours_provider()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        middle = self.height() / 2
        start = QPointF(1, middle)
        end = QPointF(self.width() - 1, middle)
        painter.setPen(edge_pen(colours, self.kind))
        if self.kind is EdgeKind.DIRECTS:
            arrow = arrow_head(end, start)
            painter.drawLine(QLineF(start, (arrow.at(1) + arrow.at(2)) / 2))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(edge_colour(colours, self.kind))
            painter.drawPolygon(arrow)
        else:
            painter.drawLine(QLineF(start, end))
        painter.end()


class RingSwatch(QWidget):
    def __init__(
        self,
        severity: Severity,
        colours_provider: ColoursProvider,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.severity = severity
        self.colours_provider = colours_provider
        self.setFixedSize(RING_SWATCH_SIZE, RING_SWATCH_SIZE)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(ring_pen(self.colours_provider(), self.severity))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for order in range(RING_COUNTS[self.severity]):
            inset = RING_WIDTH / 2 + order * (RING_WIDTH + RING_GAP)
            painter.drawEllipse(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
        painter.end()


class NoteSwatch(QWidget):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colours_provider = colours_provider
        self.setFixedSize(int(NOTE_MARKER_WIDTH) + 2, int(NOTE_MARKER_HEIGHT) + 2)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(1, 1, NOTE_MARKER_WIDTH, NOTE_MARKER_HEIGHT)
        draw_note_page(painter, note_page_path(area), self.colours_provider())
        painter.end()


class GraphLegend(QFrame):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphLegend")
        self.setAccessibleName(LEGEND_ACCESSIBLE_NAME)
        self.entry_labels: list[QLabel] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        kinds = self.add_row(layout)
        for kind, text in KIND_ENTRIES:
            self.add_entry(kinds, KindSwatch(kind, colours_provider, self), text, "legend")
        links = self.add_row(layout)
        for edge_kind, text in LINK_ENTRIES:
            self.add_entry(links, LinkSwatch(edge_kind, colours_provider, self), text, "legend")
        signals = self.add_row(layout)
        signal_label = QLabel(SIGNAL_LEGEND_TEXT, self)
        signal_label.setProperty("tone", "legend-signal")
        self.entry_labels.append(signal_label)
        signals.addWidget(signal_label)
        for severity, text in SEVERITY_ENTRIES:
            self.add_entry(signals, RingSwatch(severity, colours_provider, self), text, "legend")
        notes = self.add_row(layout)
        self.add_entry(notes, NoteSwatch(colours_provider, self), NOTE_LEGEND_TEXT, "legend")
        self.setAccessibleDescription(", ".join(self.texts))

    def add_row(self, layout: QVBoxLayout) -> FlowLayout:
        row = FlowLayout(horizontal_spacing=10, vertical_spacing=4)
        layout.addLayout(row)
        return row

    def add_entry(self, row: FlowLayout, swatch: QWidget, text: str, tone: str) -> None:
        entry = QWidget(self)
        entry_layout = QHBoxLayout(entry)
        entry_layout.setContentsMargins(0, 0, 0, 0)
        entry_layout.setSpacing(5)
        swatch.setParent(entry)
        entry_layout.addWidget(swatch)
        label = QLabel(text, entry)
        label.setProperty("tone", tone)
        entry_layout.addWidget(label)
        self.entry_labels.append(label)
        row.addWidget(entry)

    def fit(self, available_width: int) -> None:
        self.adjustSize()
        if self.width() > available_width:
            self.resize(available_width, self.heightForWidth(available_width))

    @property
    def texts(self) -> list[str]:
        return [label.text() for label in self.entry_labels]
