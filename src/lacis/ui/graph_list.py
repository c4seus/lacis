from dataclasses import dataclass
from typing import override

from PySide6.QtCore import QItemSelectionModel, QModelIndex, QObject, Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QAbstractItemView, QFrame, QTreeView, QWidget

from lacis.design.icons import ColoursProvider
from lacis.graph.descriptions import graph_description
from lacis.graph.drawing import GraphDrawing
from lacis.graph.filters import GraphFilter
from lacis.graph.listing import ListedKind, graph_listing
from lacis.storage.entities import EntityKind
from lacis.ui.data_table import IDENTIFIER_ROLE, Index, KindIcons

LIST_ACCESSIBLE_NAME = "Vue liste du graphe"
KIND_ROLE = Qt.ItemDataRole.UserRole + 3
KEY_ROLE = Qt.ItemDataRole.UserRole + 4
KIND_PREFIX = "kind:"
ENTITY_PREFIX = "entity:"
LINK_PREFIX = "link:"


@dataclass(frozen=True)
class ListRow:
    key: str
    text: str
    spoken: str
    kind: EntityKind
    target: str | None = None


def kind_key(kind: EntityKind) -> str:
    return f"{KIND_PREFIX}{kind.value}"


def entity_key(identifier: str) -> str:
    return f"{ENTITY_PREFIX}{identifier}"


def link_key(entity: str, link: str) -> str:
    return f"{LINK_PREFIX}{entity}|{link}"


def is_entity(index: QModelIndex) -> bool:
    return str(index.data(KEY_ROLE)).startswith(ENTITY_PREFIX)


class GraphListModel(QStandardItemModel):
    def __init__(self, colours_provider: ColoursProvider, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.kind_icons = KindIcons(colours_provider)
        self.listing: tuple[ListedKind, ...] = ()
        self.items: dict[str, QStandardItem] = {}

    @override
    def data(self, index: Index, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role == Qt.ItemDataRole.DecorationRole:
            kind = super().data(index, KIND_ROLE)
            return None if kind is None else self.kind_icons.icon(EntityKind(kind))
        return super().data(index, role)

    def show_listing(self, listing: tuple[ListedKind, ...]) -> None:
        self.listing = listing
        self.items = {}
        self.clear()
        root = self.invisibleRootItem()
        for listed_kind in listing:
            kind = listed_kind.kind
            group = self.add_item(
                root, ListRow(kind_key(kind), listed_kind.title, listed_kind.summary, kind)
            )
            for entity in listed_kind.entities:
                entity_item = self.add_item(
                    group,
                    ListRow(
                        entity_key(entity.identifier),
                        entity.label,
                        entity.summary,
                        entity.kind,
                        entity.identifier,
                    ),
                )
                for link in entity.links:
                    self.add_item(
                        entity_item,
                        ListRow(
                            link_key(entity.identifier, link.identifier),
                            link.description,
                            link.description,
                            link.target_kind,
                            link.target,
                        ),
                    )

    def add_item(self, parent: QStandardItem, row: ListRow) -> QStandardItem:
        item = QStandardItem(row.text)
        item.setEditable(False)
        item.setData(row.spoken, Qt.ItemDataRole.AccessibleTextRole)
        item.setData(row.spoken, Qt.ItemDataRole.ToolTipRole)
        item.setData(row.kind.value, KIND_ROLE)
        item.setData(row.key, KEY_ROLE)
        item.setData(row.target, IDENTIFIER_ROLE)
        parent.appendRow(item)
        self.items[row.key] = item
        return item

    def index_of(self, key: str | None) -> QModelIndex:
        item = self.items.get(key) if key is not None else None
        return QModelIndex() if item is None else item.index()


class GraphList(QTreeView):
    entity_chosen = Signal(str)

    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphList")
        self.setAccessibleName(LIST_ACCESSIBLE_NAME)
        self.list_model = GraphListModel(colours_provider, self)
        self.setModel(self.list_model)
        self.setHeaderHidden(True)
        self.setUniformRowHeights(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.drawing = GraphDrawing()
        self.graph_filter = GraphFilter()
        self.collapsed_kinds: set[str] = set()
        self.expanded_entities: set[str] = set()
        self.following = False
        self.expanded.connect(lambda index: self.remember_expansion(index, True))
        self.collapsed.connect(lambda index: self.remember_expansion(index, False))
        self.activated.connect(self.choose)
        self.selectionModel().currentChanged.connect(self.follow_current)
        self.describe()

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.drawing = drawing
        self.refresh()

    def apply_filter(self, graph_filter: GraphFilter) -> None:
        self.graph_filter = graph_filter
        self.refresh()

    def describe(self) -> None:
        self.setAccessibleDescription(graph_description(self.drawing, self.graph_filter))

    def refresh(self) -> None:
        self.describe()
        listing = graph_listing(self.drawing, self.graph_filter)
        if listing == self.list_model.listing:
            return
        current = self.currentIndex().data(KEY_ROLE)
        self.following = True
        try:
            self.list_model.show_listing(listing)
            self.restore_expansion()
            self.move_to(self.list_model.index_of(current))
        finally:
            self.following = False

    def restore_expansion(self) -> None:
        for key, item in self.list_model.items.items():
            if key.startswith(KIND_PREFIX):
                self.setExpanded(item.index(), key not in self.collapsed_kinds)
            elif key in self.expanded_entities:
                self.setExpanded(item.index(), True)

    def remember_expansion(self, index: QModelIndex, expanded: bool) -> None:
        key = str(index.data(KEY_ROLE))
        if key.startswith(KIND_PREFIX):
            remembered, shown = self.collapsed_kinds, not expanded
        else:
            remembered, shown = self.expanded_entities, expanded
        if shown:
            remembered.add(key)
        else:
            remembered.discard(key)

    def move_to(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        self.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.ClearAndSelect
        )
        self.scrollTo(index)

    def selected_identifier(self) -> str | None:
        selected = self.selectionModel().selectedIndexes()
        return next((index.data(IDENTIFIER_ROLE) for index in selected if is_entity(index)), None)

    def mark_selected(self, identifier: str | None) -> None:
        if identifier == self.selected_identifier():
            return
        self.following = True
        try:
            if identifier is None:
                self.selectionModel().clearSelection()
            else:
                self.move_to(self.list_model.index_of(entity_key(identifier)))
        finally:
            self.following = False

    def follow_current(self, current: QModelIndex, previous: QModelIndex) -> None:
        if self.following or not is_entity(current):
            return
        self.entity_chosen.emit(current.data(IDENTIFIER_ROLE))

    def choose(self, index: QModelIndex) -> None:
        target = index.data(IDENTIFIER_ROLE)
        if target:
            self.entity_chosen.emit(target)
