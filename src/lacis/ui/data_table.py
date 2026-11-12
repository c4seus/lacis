from typing import override

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from lacis.design.icons import ColoursProvider
from lacis.design.tokens import Colours
from lacis.graph.drawing import SHAPES
from lacis.storage.entities import EntityKind
from lacis.ui.graph_view import kind_colour, shape_path

SORT_ROLE = Qt.ItemDataRole.UserRole
IDENTIFIER_ROLE = Qt.ItemDataRole.UserRole + 1
TONE_ROLE = Qt.ItemDataRole.UserRole + 2
KIND_ICON_SIZE = 12
KIND_ICON_SCALE = 2
BADGE_HORIZONTAL_PADDING = 6
BADGE_VERTICAL_PADDING = 1
BADGE_RADIUS = 4
NUMERIC_ALIGNMENT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
Index = QModelIndex | QPersistentModelIndex


def badge_colours(colours: Colours, tone: str) -> tuple[str | None, str | None, str]:
    palette = {
        "active": (colours.soft_success, None, colours.success),
        "closed": (colours.soft_closed, None, colours.closed),
        "outline": (None, colours.strong_border, colours.muted_text),
        "high": (colours.soft_high_severity, None, colours.high_severity),
        "medium": (colours.soft_medium_severity, None, colours.medium_severity),
        "low": (colours.soft_low_severity, None, colours.low_severity),
        "information": (colours.soft_information, None, colours.information),
    }
    return palette.get(tone, (None, colours.strong_border, colours.muted_text))


def kind_icon(colours: Colours, kind: EntityKind) -> QIcon:
    pixmap = QPixmap(KIND_ICON_SIZE * KIND_ICON_SCALE, KIND_ICON_SIZE * KIND_ICON_SCALE)
    pixmap.setDevicePixelRatio(KIND_ICON_SCALE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.translate(KIND_ICON_SIZE / 2, KIND_ICON_SIZE / 2)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(kind_colour(colours, kind)))
    size = KIND_ICON_SIZE * (0.6 if kind is EntityKind.ESTABLISHMENT else 0.8)
    painter.drawPath(shape_path(SHAPES[kind], size))
    painter.end()
    return QIcon(pixmap)


class KindIcons:
    def __init__(self, colours_provider: ColoursProvider) -> None:
        self.colours_provider = colours_provider
        self.icons: dict[tuple[EntityKind, str], QIcon] = {}

    def icon(self, kind: EntityKind) -> QIcon:
        colours = self.colours_provider()
        key = (kind, getattr(colours, kind.value))
        if key not in self.icons:
            self.icons[key] = kind_icon(colours, kind)
        return self.icons[key]


class BadgeDelegate(QStyledItemDelegate):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colours_provider = colours_provider

    @override
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Index) -> None:
        tone = index.data(TONE_ROLE)
        if not tone:
            super().paint(painter, option, index)
            return
        item_option = QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        text = item_option.text
        item_option.text = ""
        widget = item_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, item_option, painter, widget)
        metrics = item_option.fontMetrics
        width = metrics.horizontalAdvance(text) + 2 * BADGE_HORIZONTAL_PADDING
        height = metrics.height() + 2 * BADGE_VERTICAL_PADDING
        cell = QRectF(item_option.rect).adjusted(4, 0, -4, 0)
        right_aligned = bool(item_option.displayAlignment & Qt.AlignmentFlag.AlignRight)
        left = cell.right() - width if right_aligned else cell.left()
        badge = QRectF(left, cell.center().y() - height / 2, width, height)
        background, border, foreground = badge_colours(self.colours_provider(), tone)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(border)) if border else Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(QColor(background)) if background else Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(badge.adjusted(0.5, 0.5, -0.5, -0.5), BADGE_RADIUS, BADGE_RADIUS)
        painter.setPen(QColor(foreground))
        painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


def configure_table(view: QTableView, accessible_name: str) -> None:
    view.setAccessibleName(accessible_name)
    view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    view.setTabKeyNavigation(False)
    view.setShowGrid(False)
    view.setWordWrap(False)
    view.setSortingEnabled(True)
    view.setCornerButtonEnabled(False)
    view.verticalHeader().hide()
    view.verticalHeader().setDefaultSectionSize(28)
    header = view.horizontalHeader()
    header.setHighlightSections(False)
    header.setSectionsClickable(True)
    header.setStretchLastSection(False)
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)


def stretch_column(view: QTableView, stretched: int) -> None:
    header = view.horizontalHeader()
    for column in range(header.count()):
        mode = (
            QHeaderView.ResizeMode.Stretch
            if column == stretched
            else QHeaderView.ResizeMode.ResizeToContents
        )
        header.setSectionResizeMode(column, mode)
