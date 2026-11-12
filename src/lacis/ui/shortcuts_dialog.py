from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from lacis.ui.menu_bar import MainMenuBar

SHORTCUTS_DIALOG_TITLE = "Raccourcis clavier"
CLOSE_TEXT = "Fermer"
TREE_ACCESSIBLE_NAME = "Liste des raccourcis clavier"
COLUMN_TITLES = ("Action", "Raccourci")
SEQUENCE_SEPARATOR = " ou "
GRAPH_GROUP_TITLE = "Dans le graphe"
GRAPH_KEYS = (
    ("Aller à l'entité voisine", "Flèches"),
    ("Déplacer la vue", "Maj+Flèches"),
    ("Déplacer l'entité sélectionnée", "Alt+Flèches"),
    ("Zoomer, dézoomer, ajuster", "+ / - / 0"),
    ("Désélectionner l'entité", "Échap"),
)
MINIMUM_WIDTH = 520
MINIMUM_HEIGHT = 640


@dataclass(frozen=True)
class ShortcutLine:
    description: str
    keys: str


@dataclass(frozen=True)
class ShortcutGroup:
    title: str
    lines: tuple[ShortcutLine, ...]


def visible_text(action: QAction) -> str:
    return action.text().replace("&", "").removesuffix("…")


def written_keys(action: QAction) -> str:
    return SEQUENCE_SEPARATOR.join(
        sequence.toString(QKeySequence.SequenceFormat.NativeText)
        for sequence in action.shortcuts()
    )


def action_line(action: QAction, description: str = "") -> ShortcutLine:
    return ShortcutLine(description or visible_text(action), written_keys(action))


def shortcut_groups(menu_bar: MainMenuBar) -> tuple[ShortcutGroup, ...]:
    help_menu = menu_bar.help_menu
    tab_lines = tuple(
        action_line(action, f"Onglet {visible_text(action)}") for action in menu_bar.tab_actions
    )
    return (
        ShortcutGroup(
            "Enquête",
            (
                action_line(menu_bar.search_action),
                action_line(menu_bar.expand_action),
                action_line(menu_bar.undo_action, "Annuler la dernière décision"),
                action_line(menu_bar.redo_action, "Rétablir la décision annulée"),
                action_line(menu_bar.new_investigation_action),
                action_line(menu_bar.close_investigation_action),
            ),
        ),
        ShortcutGroup(
            "Graphe",
            tuple(action_line(action) for action in menu_bar.graph_actions),
        ),
        ShortcutGroup(GRAPH_GROUP_TITLE, tuple(ShortcutLine(*keys) for keys in GRAPH_KEYS)),
        ShortcutGroup(
            "Panneaux",
            (
                action_line(menu_bar.queue_action, "Afficher ou masquer la colonne À examiner"),
                action_line(menu_bar.next_tab_action),
                action_line(menu_bar.previous_tab_action),
                *tab_lines,
            ),
        ),
        ShortcutGroup(
            "Application",
            (
                action_line(help_menu.shortcuts_action, "Afficher les raccourcis clavier"),
                action_line(help_menu.documentation_action, "Ouvrir la documentation"),
                action_line(menu_bar.quit_action),
            ),
        ),
    )


class ShortcutsDialog(QDialog):
    def __init__(self, groups: tuple[ShortcutGroup, ...], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(SHORTCUTS_DIALOG_TITLE)
        self.setMinimumSize(MINIMUM_WIDTH, MINIMUM_HEIGHT)
        self.tree = QTreeWidget(self)
        self.tree.setObjectName("shortcutsTree")
        self.tree.setAccessibleName(TREE_ACCESSIBLE_NAME)
        self.tree.setColumnCount(len(COLUMN_TITLES))
        self.tree.setHeaderLabels(list(COLUMN_TITLES))
        self.tree.setRootIsDecorated(False)
        self.tree.setItemsExpandable(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.group_items: list[QTreeWidgetItem] = []
        self.line_items: list[tuple[QTreeWidgetItem, QTreeWidgetItem]] = []
        for group in groups:
            self.add_group(group)
        self.tree.expandAll()
        self.tree.setCurrentItem(self.line_items[0][1])
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        self.button_box.button(QDialogButtonBox.StandardButton.Close).setText(CLOSE_TEXT)
        self.button_box.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.button_box)

    def add_group(self, group: ShortcutGroup) -> None:
        group_item = QTreeWidgetItem(self.tree, [group.title])
        group_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = group_item.font(0)
        font.setBold(True)
        group_item.setFont(0, font)
        group_item.setFirstColumnSpanned(True)
        for line in group.lines:
            item = QTreeWidgetItem(group_item, [line.description, line.keys])
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            item.setData(0, Qt.ItemDataRole.AccessibleTextRole, line.description)
            item.setData(1, Qt.ItemDataRole.AccessibleTextRole, line.keys)
            self.line_items.append((group_item, item))
        self.group_items.append(group_item)

    def lines(self) -> list[tuple[str, str, str]]:
        return [(group.text(0), item.text(0), item.text(1)) for group, item in self.line_items]
