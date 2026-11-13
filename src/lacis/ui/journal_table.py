from collections.abc import Callable
from enum import IntEnum
from typing import override

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTableView, QVBoxLayout, QWidget

from lacis.design.icons import ColoursProvider
from lacis.tables import LogRow, log_summary
from lacis.ui.data_table import (
    IDENTIFIER_ROLE,
    SORT_ROLE,
    TONE_ROLE,
    BadgeDelegate,
    Index,
    configure_table,
    stretch_column,
)

TABLE_ACCESSIBLE_NAME = "Journal de collecte"
RAW_RESPONSE_TEXT = "Réponse brute"
RAW_RESPONSE_ACCESSIBLE_NAME = "Ouvrir la réponse brute de la requête sélectionnée"
NO_RESPONSE_TOOLTIP = "Cette requête n'a pas enregistré de réponse."


class LogColumn(IntEnum):
    TIME = 0
    REQUEST = 1
    STATUS = 2
    ORIGIN = 3


COLUMN_TITLES = {
    LogColumn.TIME: "Heure",
    LogColumn.REQUEST: "Requête",
    LogColumn.STATUS: "Statut",
    LogColumn.ORIGIN: "Origine",
}


def shown_text(row: LogRow, column: LogColumn) -> str:
    texts = {
        LogColumn.TIME: row.written_time,
        LogColumn.REQUEST: row.request_text,
        LogColumn.STATUS: row.status_text,
        LogColumn.ORIGIN: row.origin_text,
    }
    return texts[column]


def spoken_text(row: LogRow, column: LogColumn) -> str:
    if column is LogColumn.TIME:
        return row.full_time
    if column is LogColumn.STATUS:
        state = "réussie" if row.succeeded else "en échec"
        return f"{row.status_text}, requête {state}"
    if column is LogColumn.ORIGIN:
        return f"servie par le {row.origin_text}"
    return shown_text(row, column)


def sort_value(row: LogRow, column: LogColumn) -> str | float:
    if column is LogColumn.TIME:
        return row.requested_at.timestamp() + row.identifier / 1_000_000
    return shown_text(row, column).casefold()


def tone_of(row: LogRow, column: LogColumn) -> str | None:
    if column is LogColumn.STATUS and row.http_status is not None:
        return "active" if row.succeeded else "high"
    if column is LogColumn.STATUS and not row.succeeded:
        return "high"
    if column is LogColumn.ORIGIN:
        return "information" if row.served_from_cache else "outline"
    return None


class LogTableModel(QAbstractTableModel):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.rows: tuple[LogRow, ...] = ()

    def show_rows(self, rows: tuple[LogRow, ...]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    @override
    def rowCount(self, parent: Index | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    @override
    def columnCount(self, parent: Index | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else len(LogColumn)

    @override
    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = LogColumn(index.column())
        values: dict[int, Callable[[], object]] = {
            Qt.ItemDataRole.DisplayRole: lambda: shown_text(row, column),
            Qt.ItemDataRole.AccessibleTextRole: lambda: spoken_text(row, column),
            Qt.ItemDataRole.ToolTipRole: lambda: row.description,
            SORT_ROLE: lambda: sort_value(row, column),
            IDENTIFIER_ROLE: lambda: row.response_identifier,
            TONE_ROLE: lambda: tone_of(row, column),
        }
        value = values.get(role)
        return None if value is None else value()

    @override
    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if orientation is Qt.Orientation.Horizontal and role in {
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.AccessibleTextRole,
        }:
            return COLUMN_TITLES[LogColumn(section)]
        return None


class JournalTab(QWidget):
    raw_requested = Signal(int)

    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("journalTab")
        self.model = LogTableModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setSortRole(SORT_ROLE)
        self.summary_label = QLabel(self)
        self.summary_label.setProperty("tone", "muted")
        self.raw_button = QPushButton(RAW_RESPONSE_TEXT, self)
        self.raw_button.setProperty("compact", True)
        self.raw_button.setAccessibleName(RAW_RESPONSE_ACCESSIBLE_NAME)
        self.raw_button.clicked.connect(self.open_current)
        self.table = QTableView(self)
        configure_table(self.table, TABLE_ACCESSIBLE_NAME)
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(BadgeDelegate(colours_provider, self.table))
        stretch_column(self.table, LogColumn.REQUEST)
        self.table.sortByColumn(LogColumn.TIME, Qt.SortOrder.DescendingOrder)
        self.table.activated.connect(self.open_row)
        self.table.selectionModel().currentRowChanged.connect(self.follow_current)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(self.summary_label, 1)
        tools.addWidget(self.raw_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(tools)
        layout.addWidget(self.table, 1)
        self.setTabOrder(self.raw_button, self.table)
        self.follow_current(QModelIndex(), QModelIndex())

    def show_rows(self, rows: tuple[LogRow, ...]) -> None:
        self.model.show_rows(rows)
        self.summary_label.setText(log_summary(rows))
        self.follow_current(QModelIndex(), QModelIndex())

    def current_response(self) -> int | None:
        current = self.table.selectionModel().currentIndex()
        return current.data(IDENTIFIER_ROLE) if current.isValid() else None

    def follow_current(self, current: QModelIndex, previous: QModelIndex) -> None:
        has_response = self.current_response() is not None
        self.raw_button.setEnabled(has_response)
        self.raw_button.setToolTip("" if has_response else NO_RESPONSE_TOOLTIP)

    def open_row(self, index: QModelIndex) -> None:
        response = index.data(IDENTIFIER_ROLE)
        if response is not None:
            self.raw_requested.emit(response)

    def open_current(self) -> None:
        response = self.current_response()
        if response is not None:
            self.raw_requested.emit(response)
