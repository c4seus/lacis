from datetime import UTC, datetime

import pytest
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from lacis.storage.notes import EntityNote
from lacis.ui.note_editor import (
    EMPTY_PREVIEW_TEXT,
    NO_NOTE_TEXT,
    SAVE_DELAY_MILLISECONDS,
    NoteEditor,
    written_dates,
)

CREATED = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
CHANGED = datetime(2026, 11, 19, 14, 5, tzinfo=UTC)
NOTE = EntityNote("Même gérant que **DUPONT SERVICES**.", CREATED, CHANGED)
ACME = "company:111111111"


@pytest.fixture
def editor(qtbot: QtBot) -> NoteEditor:
    editor = NoteEditor(ACME, "ACME PLOMBERIE", NOTE)
    qtbot.addWidget(editor)
    editor.show()
    return editor


def test_the_editor_shows_the_note_and_its_dates(editor: NoteEditor) -> None:
    assert editor.text() == NOTE.text
    assert editor.editor.accessibleName() == "Note sur ACME PLOMBERIE"
    assert editor.editor.tabChangesFocus()
    assert editor.dates_label.text().startswith("Créée le ")
    assert " · modifiée le " in editor.dates_label.text()
    assert editor.mode_button.text() == "Aperçu"


def test_dates_say_when_the_note_was_written() -> None:
    assert written_dates(None) == NO_NOTE_TEXT
    assert " · " not in written_dates(EntityNote("Note.", CREATED, CREATED))


def test_a_change_is_saved_after_a_pause(qtbot: QtBot, editor: NoteEditor) -> None:
    editor.editor.setPlainText("Gérant de paille ?")
    assert editor.timer.isActive()
    with qtbot.waitSignal(editor.edited, timeout=SAVE_DELAY_MILLISECONDS * 5) as edited:
        pass
    assert edited.args == [ACME, "Gérant de paille ?"]
    with qtbot.assertNotEmitted(editor.edited):
        editor.flush()


def test_leaving_the_editor_saves_at_once(qtbot: QtBot) -> None:
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    editor = NoteEditor(ACME, "ACME PLOMBERIE", None, root)
    other = QLineEdit(root)
    layout.addWidget(editor)
    layout.addWidget(other)
    root.show()
    root.activateWindow()
    editor.editor.setFocus()
    qtbot.waitUntil(editor.editor.hasFocus)
    editor.editor.insertPlainText("À vérifier.")
    with qtbot.waitSignal(editor.edited, timeout=100) as edited:
        other.setFocus()
    assert edited.args == [ACME, "À vérifier."]
    assert not editor.timer.isActive()


def test_kept_text_is_not_saved_again(qtbot: QtBot, editor: NoteEditor) -> None:
    with qtbot.assertNotEmitted(editor.edited):
        editor.keep_text("Texte en cours.")
        editor.flush()
    assert editor.text() == "Texte en cours."
    assert not editor.timer.isActive()


def test_the_preview_shows_the_note_as_markdown(qtbot: QtBot, editor: NoteEditor) -> None:
    editor.editor.setPlainText("Voir **ACME**.")
    with qtbot.waitSignal(editor.edited) as edited:
        editor.mode_button.click()
    assert edited.args == [ACME, "Voir **ACME**."]
    assert editor.pages.currentWidget() is editor.preview
    assert editor.preview.text() == "Voir **ACME**."
    assert editor.mode_button.text() == "Modifier"
    editor.mode_button.click()
    assert editor.pages.currentWidget() is editor.editor
    assert editor.mode_button.text() == "Aperçu"


def test_the_preview_of_an_empty_note_says_so(editor: NoteEditor) -> None:
    editor.editor.clear()
    editor.mode_button.click()
    assert editor.preview.text() == EMPTY_PREVIEW_TEXT


def test_saved_dates_are_shown(editor: NoteEditor) -> None:
    editor.show_saved(None)
    assert editor.dates_label.text() == NO_NOTE_TEXT
