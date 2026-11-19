from datetime import UTC, datetime

import pytest
from pytestqt.qtbot import QtBot

from lacis.storage.verdicts import EntityVerdict, Verdict
from lacis.ui.verdict_editor import NO_VERDICT_TEXT, UNDECIDED_TEXT, VerdictEditor

ACME = "company:111111111"
DECIDED = datetime(2026, 11, 19, 9, 30, tzinfo=UTC)


@pytest.fixture
def editor(qtbot: QtBot) -> VerdictEditor:
    editor = VerdictEditor(ACME, "ACME PLOMBERIE", None)
    qtbot.addWidget(editor)
    editor.show()
    return editor


def test_an_entity_without_verdict_offers_every_verdict(editor: VerdictEditor) -> None:
    choices = [editor.choice.itemText(index) for index in range(editor.choice.count())]
    assert choices == [NO_VERDICT_TEXT, "À vérifier", "Suspect", "Écarté", "Confirmé"]
    assert editor.chosen() is None
    assert not editor.reason.isEnabled()
    assert editor.decided_label.text() == UNDECIDED_TEXT
    assert editor.choice.accessibleName() == "Verdict sur ACME PLOMBERIE"
    assert editor.reason.accessibleName() == "Raison du verdict sur ACME PLOMBERIE"


@pytest.mark.parametrize("verdict", list(Verdict))
def test_choosing_a_verdict_saves_it(
    qtbot: QtBot, editor: VerdictEditor, verdict: Verdict
) -> None:
    with qtbot.waitSignal(editor.changed) as changed:
        editor.choice.setCurrentIndex(editor.choice.findData(verdict.value))
    assert changed.args == [ACME, verdict, ""]
    assert editor.reason.isEnabled()


def test_a_reason_is_saved_when_the_field_is_left(qtbot: QtBot) -> None:
    verdict = EntityVerdict(Verdict.SUSPECT, "", DECIDED)
    editor = VerdictEditor(ACME, "ACME PLOMBERIE", verdict)
    qtbot.addWidget(editor)
    assert editor.decided_label.text().startswith("Décidé le ")
    editor.reason.setText("  Même gérant. ")
    with qtbot.waitSignal(editor.changed) as changed:
        editor.reason.editingFinished.emit()
    assert changed.args == [ACME, Verdict.SUSPECT, "Même gérant."]


def test_nothing_is_saved_when_nothing_changed(qtbot: QtBot) -> None:
    verdict = EntityVerdict(Verdict.CONFIRMED, "Vu au greffe.", DECIDED)
    editor = VerdictEditor(ACME, "ACME PLOMBERIE", verdict)
    qtbot.addWidget(editor)
    with qtbot.assertNotEmitted(editor.changed):
        editor.reason.editingFinished.emit()
    empty = VerdictEditor(ACME, "ACME PLOMBERIE", None)
    qtbot.addWidget(empty)
    with qtbot.assertNotEmitted(empty.changed):
        empty.reason.editingFinished.emit()


def test_withdrawing_a_verdict_drops_its_reason(qtbot: QtBot) -> None:
    verdict = EntityVerdict(Verdict.DISMISSED, "Homonyme.", DECIDED)
    editor = VerdictEditor(ACME, "ACME PLOMBERIE", verdict)
    qtbot.addWidget(editor)
    assert editor.reason.text() == "Homonyme."
    with qtbot.waitSignal(editor.changed) as changed:
        editor.choice.setCurrentIndex(0)
    assert changed.args == [ACME, None, ""]
    assert not editor.reason.isEnabled()


def test_a_saved_verdict_is_shown_without_saving_again(
    qtbot: QtBot, editor: VerdictEditor
) -> None:
    verdict = EntityVerdict(Verdict.TO_CHECK, "À revoir.", DECIDED)
    with qtbot.assertNotEmitted(editor.changed):
        editor.show_verdict(verdict)
    assert editor.chosen() is Verdict.TO_CHECK
    assert editor.reason.text() == "À revoir."
    editor.show()
    editor.activateWindow()
    editor.reason.setFocus()
    editor.reason.setText("En cours")
    editor.show_verdict(verdict)
    assert editor.reason.text() == "En cours"
