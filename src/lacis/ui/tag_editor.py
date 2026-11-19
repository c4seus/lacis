from PySide6.QtCore import QStringListModel, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCompleter,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lacis.storage.tags import Tag
from lacis.ui.flow_layout import FlowLayout

FIELD_PLACEHOLDER = "Ajouter un tag, puis Entrée"
FIELD_ACCESSIBLE_PREFIX = "Ajouter un tag à "
REMOVE_MARK = "✕"
TAG_SPACING = 6


def removal_name(tag: Tag) -> str:
    return f"Retirer le tag {tag.label}"


class TagEditor(QWidget):
    added = Signal(str, str)
    removed = Signal(str, str)

    def __init__(
        self,
        identifier: str,
        entity_name: str,
        tags: tuple[Tag, ...],
        known: tuple[Tag, ...],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.identifier = identifier
        self.tags: tuple[Tag, ...] = ()
        self.buttons: list[QPushButton] = []
        self.chips = QWidget(self)
        self.chips_layout = FlowLayout(self.chips, TAG_SPACING, TAG_SPACING)
        self.chips_layout.setContentsMargins(0, 0, 0, 0)
        self.completions = QStringListModel(self)
        completer = QCompleter(self.completions, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self.field = QLineEdit(self)
        self.field.setPlaceholderText(FIELD_PLACEHOLDER)
        self.field.setAccessibleName(f"{FIELD_ACCESSIBLE_PREFIX}{entity_name}")
        self.field.setCompleter(completer)
        self.field.returnPressed.connect(self.add)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TAG_SPACING)
        layout.addWidget(self.chips)
        layout.addWidget(self.field)
        self.show_tags(tags, known)

    def show_tags(self, tags: tuple[Tag, ...], known: tuple[Tag, ...]) -> None:
        focused = QApplication.focusWidget() in self.buttons
        for button in self.buttons:
            self.chips_layout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self.tags = tags
        self.buttons = [self.chip(tag) for tag in tags]
        self.chips.setVisible(bool(tags))
        own = {tag.key for tag in tags}
        self.completions.setStringList([tag.label for tag in known if tag.key not in own])
        if focused:
            self.field.setFocus(Qt.FocusReason.OtherFocusReason)

    def chip(self, tag: Tag) -> QPushButton:
        button = QPushButton(f"{tag.label} {REMOVE_MARK}", self.chips)
        button.setProperty("compact", True)
        button.setAccessibleName(removal_name(tag))
        button.setToolTip(removal_name(tag))
        button.clicked.connect(lambda: self.removed.emit(self.identifier, tag.key))
        self.chips_layout.addWidget(button)
        return button

    def add(self) -> None:
        text = self.field.text()
        self.field.clear()
        if text.strip():
            self.added.emit(self.identifier, text)
