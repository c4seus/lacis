from typing import override

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lacis.design.icons import ColoursProvider
from lacis.details import NoticeLine

TIMELINE_ACCESSIBLE_NAME = "Annonces BODACC"
NO_NOTICE_TEXT = "Aucune annonce collectée pour cette entreprise."
WITHDRAWN_TEXT = "Retirée"
JUDGMENT_PREFIX = "Jugement : "
LINE_X = 7.0
DOT_RADIUS = 5.0
DOT_TOP = 9.0
LINE_WIDTH = 2.0
ITEM_INDENT = 24


def tone_label(text: str, tone: str, parent: QWidget, *, wrapped: bool = False) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", tone)
    label.setWordWrap(wrapped)
    return label


class NoticeItem(QFrame):
    def __init__(self, notice: NoticeLine, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.notice = notice
        self.setObjectName("noticeItem")
        self.setProperty("withdrawn", notice.is_withdrawn)
        self.date_label = tone_label(notice.written_date, "notice-date", self)
        self.family_badge = tone_label(
            notice.family_label, "badge-high" if notice.is_alert else "badge-outline", self
        )
        self.withdrawn_badge = tone_label(WITHDRAWN_TEXT, "badge-closed", self)
        self.withdrawn_badge.setVisible(notice.is_withdrawn)
        when = QHBoxLayout()
        when.setSpacing(8)
        when.addWidget(self.date_label)
        when.addWidget(self.family_badge)
        when.addWidget(self.withdrawn_badge)
        when.addStretch(1)
        summary_tone = "notice-withdrawn" if notice.is_withdrawn else "notice-summary"
        self.summary_label = tone_label(
            notice.summary or notice.family_label, summary_tone, self, wrapped=True
        )
        judgment = f"{JUDGMENT_PREFIX}{notice.shown_judgment}" if notice.shown_judgment else ""
        self.notes = [
            tone_label(note, "notice-note", self, wrapped=True)
            for note in (judgment, notice.role_note, notice.withdrawn_text)
            if note
        ]
        self.court_label = tone_label(notice.court, "notice-note", self, wrapped=True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(2)
        layout.addLayout(when)
        layout.addWidget(self.summary_label)
        for note in self.notes:
            layout.addWidget(note)
        layout.addWidget(self.court_label)
        parts = [notice.written_date, notice.family_label, notice.summary]
        if notice.is_withdrawn:
            parts.append(WITHDRAWN_TEXT.lower())
        self.setAccessibleName(", ".join(part for part in parts if part))


class NoticeTimeline(QWidget):
    def __init__(
        self,
        notices: tuple[NoticeLine, ...],
        colours_provider: ColoursProvider,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.colours_provider = colours_provider
        self.setObjectName("noticeTimeline")
        self.setAccessibleName(TIMELINE_ACCESSIBLE_NAME)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(ITEM_INDENT, 0, 0, 0)
        layout.setSpacing(0)
        self.items: list[NoticeItem] = []
        self.empty_label: QLabel | None = None
        if not notices:
            self.empty_label = tone_label(NO_NOTICE_TEXT, "faint", self, wrapped=True)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.empty_label)
        for notice in notices:
            item = NoticeItem(notice, self)
            self.items.append(item)
            layout.addWidget(item)

    def dot_centres(self) -> list[QPointF]:
        return [QPointF(LINE_X, item.y() + DOT_TOP) for item in self.items]

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        if not self.items:
            return
        colours = self.colours_provider()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        centres = self.dot_centres()
        painter.setPen(QPen(QColor(colours.strong_border), LINE_WIDTH))
        painter.drawLine(centres[0], QPointF(LINE_X, self.height()))
        for item, centre in zip(self.items, centres, strict=True):
            alert = item.notice.is_alert and not item.notice.is_withdrawn
            border = colours.high_severity if alert else colours.strong_border
            fill = colours.soft_high_severity if alert else colours.surface
            pen = QPen(QColor(border), LINE_WIDTH)
            if item.notice.is_withdrawn:
                pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.setBrush(QColor(fill))
            painter.drawEllipse(
                QRectF(
                    centre.x() - DOT_RADIUS,
                    centre.y() - DOT_RADIUS,
                    DOT_RADIUS * 2,
                    DOT_RADIUS * 2,
                )
            )
        painter.end()
