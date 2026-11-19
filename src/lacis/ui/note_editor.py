from typing import override

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lacis.details import written_moment
from lacis.storage.notes import EntityNote

SAVE_DELAY_MILLISECONDS = 800
EDITOR_HEIGHT = 120
PLACEHOLDER_TEXT = "Écrire une note sur cette entité. Le Markdown est accepté."
EDITOR_ACCESSIBLE_PREFIX = "Note sur "
PREVIEW_TEXT = "Aperçu"
EDIT_TEXT = "Modifier"
PREVIEW_ACCESSIBLE_PREFIX = "Aperçu de la note sur "
EMPTY_PREVIEW_TEXT = "Aucune note."
NO_NOTE_TEXT = "Enregistrée automatiquement"


def written_dates(note: EntityNote | None) -> str:
    if note is None:
        return NO_NOTE_TEXT
    created = f"Créée le {written_moment(note.created_at)}"
    if note.changed_at == note.created_at:
        return created
    return f"{created} · modifiée le {written_moment(note.changed_at)}"


class NoteText(QPlainTextEdit):
    left = Signal()

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        super().focusOutEvent(event)
        self.left.emit()


class NoteEditor(QWidget):
    edited = Signal(str, str)

    def __init__(
        self,
        identifier: str,
        entity_name: str,
        note: EntityNote | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.identifier = identifier
        self.saved_text = "" if note is None else note.text
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(SAVE_DELAY_MILLISECONDS)
        self.timer.timeout.connect(self.flush)
        self.editor = NoteText(self)
        self.editor.setPlainText(self.saved_text)
        self.editor.setPlaceholderText(PLACEHOLDER_TEXT)
        self.editor.setAccessibleName(f"{EDITOR_ACCESSIBLE_PREFIX}{entity_name}")
        self.editor.setTabChangesFocus(True)
        self.editor.setFixedHeight(EDITOR_HEIGHT)
        self.editor.textChanged.connect(self.timer.start)
        self.editor.left.connect(self.flush)
        self.preview = QLabel(self)
        self.preview.setTextFormat(Qt.TextFormat.MarkdownText)
        self.preview.setWordWrap(True)
        self.preview.setAccessibleName(f"{PREVIEW_ACCESSIBLE_PREFIX}{entity_name}")
        self.preview.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.preview.hide()
        self.mode_button = QPushButton(PREVIEW_TEXT, self)
        self.mode_button.setProperty("compact", True)
        self.mode_button.setCheckable(True)
        self.mode_button.toggled.connect(self.show_preview)
        self.dates_label = QLabel(written_dates(note), self)
        self.dates_label.setProperty("tone", "faint")
        self.dates_label.setWordWrap(True)
        foot = QHBoxLayout()
        foot.setContentsMargins(0, 0, 0, 0)
        foot.addWidget(self.dates_label, 1)
        foot.addWidget(self.mode_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self.editor)
        layout.addWidget(self.preview)
        layout.addLayout(foot)

    def text(self) -> str:
        return self.editor.toPlainText()

    def keep_text(self, text: str) -> None:
        self.saved_text = text
        blocked = self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(blocked)

    def flush(self) -> None:
        self.timer.stop()
        text = self.text()
        if text == self.saved_text:
            return
        self.saved_text = text
        self.edited.emit(self.identifier, text)

    def show_saved(self, note: EntityNote | None) -> None:
        self.dates_label.setText(written_dates(note))

    def show_preview(self, shown: bool) -> None:
        self.flush()
        self.preview.setText(self.text().strip() or EMPTY_PREVIEW_TEXT)
        self.editor.setVisible(not shown)
        self.preview.setVisible(shown)
        self.mode_button.setText(EDIT_TEXT if shown else PREVIEW_TEXT)
