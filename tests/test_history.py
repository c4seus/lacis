from PySide6.QtGui import QUndoCommand
from pytestqt.qtbot import QtBot

from lacis.history import InvestigationHistory


class NoteCommand(QUndoCommand):
    def __init__(self, notes: list[str], note: str) -> None:
        super().__init__("la note")
        self.notes = notes
        self.note = note

    def redo(self) -> None:
        self.notes.append(self.note)

    def undo(self) -> None:
        self.notes.remove(self.note)


def test_an_action_recorded_in_the_history_is_applied(qtbot: QtBot) -> None:
    notes: list[str] = []
    history = InvestigationHistory()
    history.record(NoteCommand(notes, "Siège partagé"))
    assert notes == ["Siège partagé"]
    assert history.canUndo()
    assert history.undoText() == "la note"


def test_an_action_can_be_undone_then_redone(qtbot: QtBot) -> None:
    notes: list[str] = []
    history = InvestigationHistory()
    history.record(NoteCommand(notes, "Siège partagé"))
    history.record(NoteCommand(notes, "Dirigeant commun"))
    history.undo()
    assert notes == ["Siège partagé"]
    history.undo()
    assert notes == []
    assert not history.canUndo()
    history.redo()
    assert notes == ["Siège partagé"]
    assert history.canRedo()


def test_a_new_action_after_an_undo_drops_the_undone_ones(qtbot: QtBot) -> None:
    notes: list[str] = []
    history = InvestigationHistory()
    history.record(NoteCommand(notes, "Siège partagé"))
    history.undo()
    history.record(NoteCommand(notes, "Dirigeant commun"))
    assert notes == ["Dirigeant commun"]
    assert not history.canRedo()


def test_every_change_of_the_history_is_announced(qtbot: QtBot) -> None:
    notes: list[str] = []
    history = InvestigationHistory()
    changes: list[None] = []
    history.changed.connect(lambda: changes.append(None))
    history.record(NoteCommand(notes, "Siège partagé"))
    history.undo()
    history.redo()
    assert len(changes) == 3
