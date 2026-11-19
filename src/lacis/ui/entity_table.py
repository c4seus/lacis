from collections.abc import Callable
from enum import IntEnum
from itertools import pairwise
from typing import override

from PySide6.QtCore import (
    QAbstractTableModel,
    QItemSelectionModel,
    QModelIndex,
    QObject,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import ColoursProvider
from lacis.graph.listing import sortable
from lacis.storage.tags import Tag
from lacis.storage.verdicts import Verdict
from lacis.tables import EntityRow, entities_summary
from lacis.ui.data_table import (
    IDENTIFIER_ROLE,
    NUMERIC_ALIGNMENT,
    SORT_ROLE,
    TONE_ROLE,
    BadgeDelegate,
    Index,
    KindIcons,
    configure_table,
    stretch_column,
)

TABLE_ACCESSIBLE_NAME = "Entités de l'enquête"
FILTER_PLACEHOLDER = "Filtrer les entités"
FILTER_ACCESSIBLE_NAME = "Filtrer les entités par nom"
FLAGGED_TEXT = "Signalées seulement"
FLAGGED_ACCESSIBLE_NAME = "N'afficher que les entités signalées"
SORT_ACCESSIBLE_NAME = "Trier les entités par"
TAG_ACCESSIBLE_NAME = "Filtrer les entités par tag"
EVERY_TAG_TEXT = "Tous les tags"
VERDICT_ACCESSIBLE_NAME = "Filtrer les entités par verdict"
EVERY_VERDICT_TEXT = "Tous les verdicts"
NO_STATUS_TEXT = "sans état"
NOTED_TEXT = "Oui"
NOTED_SPOKEN_TEXT = "avec une note"
NOT_NOTED_SPOKEN_TEXT = "sans note"
NO_VERDICT_SPOKEN_TEXT = "sans verdict"
LAST_TEXT = chr(0xFFFF)


class EntityColumn(IntEnum):
    NAME = 0
    KIND = 1
    STATUS = 2
    SCORE = 3
    LINKS = 4
    NOTE = 5
    VERDICT = 6


COLUMN_TITLES = {
    EntityColumn.NAME: "Entité",
    EntityColumn.KIND: "Type",
    EntityColumn.STATUS: "État",
    EntityColumn.SCORE: "Score",
    EntityColumn.LINKS: "Liens",
    EntityColumn.NOTE: "Note",
    EntityColumn.VERDICT: "Verdict",
}
SORT_CHOICES = (
    ("Score", EntityColumn.SCORE, Qt.SortOrder.DescendingOrder),
    ("Nom", EntityColumn.NAME, Qt.SortOrder.AscendingOrder),
    ("Type", EntityColumn.KIND, Qt.SortOrder.AscendingOrder),
    ("État", EntityColumn.STATUS, Qt.SortOrder.AscendingOrder),
)


ANNOTATION_COLUMNS = (EntityColumn.NOTE, EntityColumn.VERDICT)


def sort_value(row: EntityRow, column: EntityColumn) -> str | float:
    if column is EntityColumn.NAME:
        return sortable(row.label)
    if column is EntityColumn.KIND:
        return sortable(row.kind_label)
    if column is EntityColumn.STATUS:
        return sortable(row.status_text) or LAST_TEXT
    if column is EntityColumn.SCORE:
        rank, score = row.sort_score
        return rank * 10 + score
    if column in ANNOTATION_COLUMNS:
        return annotation_sort_value(row, column)
    return float(row.links)


def annotation_sort_value(row: EntityRow, column: EntityColumn) -> float:
    if column is EntityColumn.NOTE:
        return float(row.noted)
    return -1.0 if row.verdict is None else float(list(Verdict).index(row.verdict))


def shown_text(row: EntityRow, column: EntityColumn) -> str:
    texts = {
        EntityColumn.NAME: row.label,
        EntityColumn.KIND: row.kind_label,
        EntityColumn.STATUS: row.status_text,
        EntityColumn.SCORE: row.shown_score,
        EntityColumn.LINKS: str(row.links),
        EntityColumn.NOTE: NOTED_TEXT if row.noted else "",
        EntityColumn.VERDICT: "" if row.verdict is None else row.verdict.label,
    }
    return texts[column]


def spoken_text(row: EntityRow, column: EntityColumn) -> str:
    if column is EntityColumn.NAME:
        return f"{row.label}, {row.kind_label}"
    if column is EntityColumn.STATUS:
        return row.status_text or NO_STATUS_TEXT
    if column is EntityColumn.SCORE:
        return row.spoken_score
    if column is EntityColumn.LINKS:
        return f"{row.links} lien{'s' if row.links > 1 else ''}"
    if column in ANNOTATION_COLUMNS:
        return annotation_spoken_text(row, column)
    return shown_text(row, column)


def annotation_spoken_text(row: EntityRow, column: EntityColumn) -> str:
    if column is EntityColumn.NOTE:
        return NOTED_SPOKEN_TEXT if row.noted else NOT_NOTED_SPOKEN_TEXT
    return NO_VERDICT_SPOKEN_TEXT if row.verdict is None else f"verdict {row.verdict.label}"


def tone_of(row: EntityRow, column: EntityColumn) -> str | None:
    if column is EntityColumn.STATUS and row.status is not None:
        return row.status.tone.value
    if column is EntityColumn.SCORE and row.severity is not None:
        return row.severity.value
    return None


class EntityTableModel(QAbstractTableModel):
    def __init__(self, colours_provider: ColoursProvider, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.kind_icons = KindIcons(colours_provider)
        self.rows: tuple[EntityRow, ...] = ()

    def show_rows(self, rows: tuple[EntityRow, ...]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    @override
    def rowCount(self, parent: Index | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else len(self.rows)

    @override
    def columnCount(self, parent: Index | None = None) -> int:
        return 0 if parent is not None and parent.isValid() else len(EntityColumn)

    @override
    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        column = EntityColumn(index.column())
        values: dict[int, Callable[[], object]] = {
            Qt.ItemDataRole.DisplayRole: lambda: shown_text(row, column),
            Qt.ItemDataRole.AccessibleTextRole: lambda: spoken_text(row, column),
            Qt.ItemDataRole.ToolTipRole: lambda: spoken_text(row, column),
            SORT_ROLE: lambda: sort_value(row, column),
            IDENTIFIER_ROLE: lambda: row.identifier,
            TONE_ROLE: lambda: tone_of(row, column),
        }
        if role == Qt.ItemDataRole.DecorationRole and column is EntityColumn.NAME:
            return self.kind_icons.icon(row.kind)
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {
            EntityColumn.SCORE,
            EntityColumn.LINKS,
        }:
            return NUMERIC_ALIGNMENT
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
            return COLUMN_TITLES[EntityColumn(section)]
        return None


class EntityFilter(QSortFilterProxyModel):
    def __init__(self, model: EntityTableModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.entity_model = model
        self.flagged_only = False
        self.searched = ""
        self.tag: str | None = None
        self.verdict: Verdict | None = None
        self.setSourceModel(model)
        self.setSortRole(SORT_ROLE)

    def show_flagged_only(self, flagged_only: bool) -> None:
        self.refilter(lambda: setattr(self, "flagged_only", flagged_only))

    def search(self, text: str) -> None:
        self.refilter(lambda: setattr(self, "searched", text.strip().casefold()))

    def show_tag(self, tag: str | None) -> None:
        self.refilter(lambda: setattr(self, "tag", tag))

    def show_verdict(self, verdict: Verdict | None) -> None:
        self.refilter(lambda: setattr(self, "verdict", verdict))

    def refilter(self, change: Callable[[], None]) -> None:
        if hasattr(self, "beginFilterChange"):
            self.beginFilterChange()
            change()
            self.endFilterChange(QSortFilterProxyModel.Direction.Rows)
        else:
            change()
            self.invalidateRowsFilter()

    @override
    def filterAcceptsRow(self, source_row: int, source_parent: Index) -> bool:
        row = self.entity_model.rows[source_row]
        if self.flagged_only and not row.flagged:
            return False
        if self.tag is not None and self.tag not in row.tags:
            return False
        if self.verdict is not None and row.verdict is not self.verdict:
            return False
        return self.searched in row.label.casefold()


class EntitiesTab(QWidget):
    entity_chosen = Signal(str)
    tag_chosen = Signal(object)
    verdict_chosen = Signal(object)

    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("entitiesTab")
        self.following = False
        self.model = EntityTableModel(colours_provider, self)
        self.proxy = EntityFilter(self.model, self)
        self.filter_field = QLineEdit(self)
        self.filter_field.setProperty("variant", "search")
        self.filter_field.setPlaceholderText(FILTER_PLACEHOLDER)
        self.filter_field.setAccessibleName(FILTER_ACCESSIBLE_NAME)
        self.filter_field.setClearButtonEnabled(True)
        self.filter_field.textChanged.connect(self.proxy.search)
        self.flagged_box = QCheckBox(FLAGGED_TEXT, self)
        self.flagged_box.setAccessibleName(FLAGGED_ACCESSIBLE_NAME)
        self.flagged_box.toggled.connect(self.proxy.show_flagged_only)
        self.sort_box = QComboBox(self)
        self.sort_box.setAccessibleName(SORT_ACCESSIBLE_NAME)
        for title, _column, _order in SORT_CHOICES:
            self.sort_box.addItem(title)
        self.sort_box.currentIndexChanged.connect(self.sort_by_choice)
        self.tag_box, self.verdict_box = self.create_tag_box(), self.create_verdict_box()
        self.summary_label = QLabel(self)
        self.summary_label.setProperty("tone", "muted")
        self.table = QTableView(self)
        configure_table(self.table, TABLE_ACCESSIBLE_NAME)
        self.table.setModel(self.proxy)
        self.table.setItemDelegate(BadgeDelegate(colours_provider, self.table))
        stretch_column(self.table, EntityColumn.NAME)
        self.table.setColumnHidden(EntityColumn.KIND, True)
        self.table.horizontalHeader().sortIndicatorChanged.connect(self.follow_sort)
        self.table.selectionModel().currentRowChanged.connect(self.choose_current)
        self.sort_by_choice(0)
        tools = QHBoxLayout()
        tools.setSpacing(8)
        tools.addWidget(self.filter_field, 1)
        tools.addWidget(self.sort_box)
        options = QHBoxLayout()
        options.setSpacing(8)
        options.addWidget(self.flagged_box)
        options.addWidget(self.tag_box)
        options.addWidget(self.verdict_box)
        options.addStretch(1)
        options.addWidget(self.summary_label)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        layout.addLayout(tools)
        layout.addLayout(options)
        layout.addWidget(self.table, 1)
        tab_order = (
            self.filter_field,
            self.sort_box,
            self.flagged_box,
            self.tag_box,
            self.verdict_box,
            self.table,
        )
        for first, second in pairwise(tab_order):
            self.setTabOrder(first, second)
        self.show_tags((), None)

    def create_tag_box(self) -> QComboBox:
        tag_box = QComboBox(self)
        tag_box.setAccessibleName(TAG_ACCESSIBLE_NAME)
        tag_box.currentIndexChanged.connect(self.follow_tag_box)
        return tag_box

    def create_verdict_box(self) -> QComboBox:
        verdict_box = QComboBox(self)
        verdict_box.setAccessibleName(VERDICT_ACCESSIBLE_NAME)
        verdict_box.addItem(EVERY_VERDICT_TEXT, "")
        for verdict in Verdict:
            verdict_box.addItem(verdict.label, verdict.value)
        verdict_box.currentIndexChanged.connect(self.follow_verdict_box)
        return verdict_box

    def chosen_verdict(self) -> Verdict | None:
        value = str(self.verdict_box.currentData())
        return Verdict(value) if value else None

    def choose_verdict(self, verdict: Verdict | None) -> None:
        blocked = self.verdict_box.blockSignals(True)
        value = "" if verdict is None else verdict.value
        self.verdict_box.setCurrentIndex(self.verdict_box.findData(value))
        self.verdict_box.blockSignals(blocked)
        self.proxy.show_verdict(verdict)

    def follow_verdict_box(self) -> None:
        self.proxy.show_verdict(self.chosen_verdict())
        self.verdict_chosen.emit(self.chosen_verdict())

    def show_tags(self, tags: tuple[Tag, ...], chosen: str | None) -> None:
        blocked = self.tag_box.blockSignals(True)
        self.tag_box.clear()
        self.tag_box.addItem(EVERY_TAG_TEXT, None)
        for tag in tags:
            self.tag_box.addItem(tag.label, tag.key)
        self.tag_box.blockSignals(blocked)
        self.tag_box.setEnabled(bool(tags))
        self.choose_tag(chosen)

    def choose_tag(self, key: str | None) -> None:
        blocked = self.tag_box.blockSignals(True)
        self.tag_box.setCurrentIndex(max(self.tag_box.findData(key), 0))
        self.tag_box.blockSignals(blocked)
        self.proxy.show_tag(self.tag_box.currentData())

    def follow_tag_box(self, index: int) -> None:
        self.proxy.show_tag(self.tag_box.itemData(index))
        self.tag_chosen.emit(self.tag_box.itemData(index))

    def sort_by_choice(self, choice: int) -> None:
        _title, column, order = SORT_CHOICES[choice]
        self.table.sortByColumn(column, order)

    def follow_sort(self, column: int, order: Qt.SortOrder) -> None:
        for choice, (_title, sorted_column, _order) in enumerate(SORT_CHOICES):
            if sorted_column == column:
                self.sort_box.blockSignals(True)
                self.sort_box.setCurrentIndex(choice)
                self.sort_box.blockSignals(False)
        self.table.horizontalHeader().setSortIndicator(column, order)

    def show_rows(self, rows: tuple[EntityRow, ...]) -> None:
        selected = self.selected_identifier()
        self.model.show_rows(rows)
        self.summary_label.setText(entities_summary(rows))
        self.mark_selected(selected)

    def shown_identifiers(self) -> list[str]:
        return [
            self.proxy.index(row, 0).data(IDENTIFIER_ROLE) for row in range(self.proxy.rowCount())
        ]

    def selected_identifier(self) -> str | None:
        current = self.table.selectionModel().currentIndex()
        return current.data(IDENTIFIER_ROLE) if current.isValid() else None

    def mark_selected(self, identifier: str | None) -> None:
        selection = self.table.selectionModel()
        self.following = True
        try:
            identifiers = self.shown_identifiers()
            if identifier in identifiers:
                index = self.proxy.index(identifiers.index(identifier), 0)
                selection.setCurrentIndex(
                    index,
                    QItemSelectionModel.SelectionFlag.ClearAndSelect
                    | QItemSelectionModel.SelectionFlag.Rows,
                )
                self.table.scrollTo(index)
            else:
                selection.clear()
        finally:
            self.following = False

    def choose_current(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self.following or not current.isValid():
            return
        self.entity_chosen.emit(current.data(IDENTIFIER_ROLE))
