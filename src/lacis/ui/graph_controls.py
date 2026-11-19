from dataclasses import replace

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QFrame, QMenu, QToolButton, QVBoxLayout, QWidget

from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing
from lacis.graph.filters import (
    KIND_FILTER_LABELS,
    GraphFilter,
    flagged_choice_label,
    kind_choice_label,
)
from lacis.storage.entities import EntityKind
from lacis.storage.tags import Tag
from lacis.storage.verdicts import Verdict
from lacis.ui.header_bar import create_icon_button

ZOOM_BUTTON_SIZE = QSize(30, 30)
ZOOM_TOOLBAR_ACCESSIBLE_NAME = "Navigation dans le graphe"
ZOOM_IN_TEXT = "Zoom avant"
ZOOM_OUT_TEXT = "Zoom arrière"
FIT_TEXT = "Ajuster à la fenêtre"
LAYOUT_TEXT = "Réorganiser le graphe"
ZOOM_IN_SHORTCUT_TEXT = "Ctrl++"
ZOOM_OUT_SHORTCUT_TEXT = "Ctrl+-"
FIT_SHORTCUT_TEXT = "Ctrl+0"
LAYOUT_SHORTCUT_TEXT = "Ctrl+Maj+R"
FILTER_TEXT = "Filtres"
FILTER_ACCESSIBLE_NAME = "Filtres du graphe"
SHOW_EVERYTHING_TEXT = "Tout afficher"
TAG_MENU_TEXT = "Tag"
NO_TAG_MENU_TEXT = "Tag : aucun dans l'enquête"
EVERY_TAG_TEXT = "Tous les tags"
VERDICT_MENU_TEXT = "Verdict"
EVERY_VERDICT_TEXT = "Tous les verdicts"
LIST_VIEW_TEXT = "Vue liste"
LIST_VIEW_SHORTCUT_TEXT = "Ctrl+L"


def tooltip_with_shortcut(text: str, shortcut: str) -> str:
    return f"{text} ({shortcut})"


class ZoomToolbar(QFrame):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphToolbar")
        self.setAccessibleName(ZOOM_TOOLBAR_ACCESSIBLE_NAME)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.zoom_in_button = self.add_button(
            icon_factory, "zoom-in", ZOOM_IN_TEXT, ZOOM_IN_SHORTCUT_TEXT
        )
        self.zoom_out_button = self.add_button(
            icon_factory, "zoom-out", ZOOM_OUT_TEXT, ZOOM_OUT_SHORTCUT_TEXT
        )
        self.fit_button = self.add_button(icon_factory, "fit", FIT_TEXT, FIT_SHORTCUT_TEXT)
        self.layout_button = self.add_button(
            icon_factory, "layout", LAYOUT_TEXT, LAYOUT_SHORTCUT_TEXT
        )

    def add_button(
        self, icon_factory: IconFactory, icon_name: str, text: str, shortcut: str
    ) -> QToolButton:
        button = create_icon_button(
            icon_factory.icon(icon_name), text, tooltip_with_shortcut(text, shortcut), self
        )
        button.setFixedSize(ZOOM_BUTTON_SIZE)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)
        layout = self.layout()
        assert layout is not None
        layout.addWidget(button)
        return button

    @property
    def buttons(self) -> list[QToolButton]:
        return [self.zoom_in_button, self.zoom_out_button, self.fit_button, self.layout_button]


class FilterChip(QToolButton):
    filter_changed = Signal(object)

    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filterChip")
        self.setIcon(icon_factory.icon("filter"))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(FILTER_ACCESSIBLE_NAME)
        self.graph_filter = GraphFilter()
        self.drawing = GraphDrawing()
        self.choices = QMenu(self)
        self.kind_actions: dict[EntityKind, QAction] = {}
        for kind in KIND_FILTER_LABELS:
            action = self.choices.addAction(KIND_FILTER_LABELS[kind])
            action.setCheckable(True)
            action.setChecked(True)
            action.toggled.connect(
                lambda shown, chosen=kind: self.change(
                    self.graph_filter.showing_kind(chosen, shown)
                )
            )
            self.kind_actions[kind] = action
        self.choices.addSeparator()
        self.flagged_action = self.choices.addAction("")
        self.flagged_action.setCheckable(True)
        self.flagged_action.toggled.connect(
            lambda flagged: self.change(self.graph_filter.showing_flagged_only(flagged))
        )
        self.tag_menu = self.choices.addMenu(TAG_MENU_TEXT)
        self.tag_group = QActionGroup(self)
        self.tag_actions: dict[str | None, QAction] = {}
        self.verdict_menu = self.choices.addMenu(VERDICT_MENU_TEXT)
        self.verdict_group = QActionGroup(self)
        self.verdict_actions: dict[Verdict | None, QAction] = {}
        verdict_choices: list[tuple[Verdict | None, str]] = [(None, EVERY_VERDICT_TEXT)]
        verdict_choices.extend((verdict, verdict.label) for verdict in Verdict)
        for verdict, label in verdict_choices:
            action = self.verdict_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(verdict is None)
            self.verdict_group.addAction(action)
            action.triggered.connect(
                lambda _checked=False, chosen=verdict: self.change(
                    self.graph_filter.showing_verdict(chosen)
                )
            )
            self.verdict_actions[verdict] = action
        self.choices.addSeparator()
        self.show_everything_action = self.choices.addAction(SHOW_EVERYTHING_TEXT)
        self.show_everything_action.triggered.connect(self.show_everything)
        self.setMenu(self.choices)
        self.show_drawing(GraphDrawing())
        self.show_tags(())

    def show_tags(self, tags: tuple[Tag, ...]) -> None:
        for action in self.tag_actions.values():
            self.tag_group.removeAction(action)
        self.tag_menu.clear()
        self.tag_actions = {}
        self.tag_menu.setTitle(TAG_MENU_TEXT if tags else NO_TAG_MENU_TEXT)
        self.tag_menu.setEnabled(bool(tags))
        choices: list[tuple[str | None, str]] = [(None, EVERY_TAG_TEXT)]
        choices.extend((tag.key, tag.label) for tag in tags)
        for key, label in choices:
            action = self.tag_menu.addAction(label)
            action.setCheckable(True)
            self.tag_group.addAction(action)
            action.triggered.connect(lambda _checked=False, chosen=key: self.choose_tag(chosen))
            self.tag_actions[key] = action
        known = {tag.key for tag in tags}
        self.choose_tag(self.graph_filter.tag if self.graph_filter.tag in known else None)

    def choose_tag(self, key: str | None) -> None:
        self.choose_annotations(key, self.graph_filter.verdict)

    def choose_annotations(self, key: str | None, verdict: Verdict | None) -> None:
        action = self.tag_actions.get(key)
        if action is not None:
            action.setChecked(True)
        self.verdict_actions[verdict].setChecked(True)
        self.change(replace(self.graph_filter, tag=key, verdict=verdict))

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.drawing = drawing
        for kind, action in self.kind_actions.items():
            action.setText(kind_choice_label(kind, drawing))
        self.flagged_action.setText(flagged_choice_label(drawing))
        self.describe()

    def describe(self) -> None:
        summary = self.graph_filter.summary(self.drawing)
        self.setText(f"{FILTER_TEXT} · {summary}")
        self.setAccessibleDescription(summary)
        self.setProperty("active", self.graph_filter.is_active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.show_everything_action.setEnabled(self.graph_filter.is_active)

    def change(self, graph_filter: GraphFilter) -> None:
        if graph_filter == self.graph_filter:
            return
        self.graph_filter = graph_filter
        self.describe()
        self.filter_changed.emit(graph_filter)

    def show_everything(self) -> None:
        for action in [*self.kind_actions.values(), self.flagged_action]:
            action.blockSignals(True)
        for action in self.kind_actions.values():
            action.setChecked(True)
        self.flagged_action.setChecked(False)
        for action in [*self.kind_actions.values(), self.flagged_action]:
            action.blockSignals(False)
        self.tag_actions[None].setChecked(True)
        self.verdict_actions[None].setChecked(True)
        self.change(GraphFilter())


class ListViewChip(QToolButton):
    def __init__(self, icon_factory: IconFactory, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewChip")
        self.setIcon(icon_factory.icon("list"))
        self.setText(LIST_VIEW_TEXT)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setCheckable(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(LIST_VIEW_TEXT)
        self.setToolTip(tooltip_with_shortcut(LIST_VIEW_TEXT, LIST_VIEW_SHORTCUT_TEXT))
