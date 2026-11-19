import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from lacis.storage.tags import Tag
from lacis.ui.tag_editor import TagEditor

ACME = "company:111111111"
CLIENT = Tag("client", "Client")
NETWORK = Tag("réseau dupont", "réseau Dupont")


@pytest.fixture
def editor(qtbot: QtBot) -> TagEditor:
    editor = TagEditor(ACME, "ACME PLOMBERIE", (CLIENT,), (CLIENT, NETWORK))
    qtbot.addWidget(editor)
    editor.show()
    editor.activateWindow()
    return editor


def test_the_editor_shows_the_tags_of_the_entity(editor: TagEditor) -> None:
    assert [button.text() for button in editor.buttons] == ["Client ✕"]
    assert editor.buttons[0].accessibleName() == "Retirer le tag Client"
    assert editor.field.accessibleName() == "Ajouter un tag à ACME PLOMBERIE"
    assert editor.completions.stringList() == ["réseau Dupont"]


def test_an_entity_without_tags_hides_the_chips(qtbot: QtBot) -> None:
    editor = TagEditor(ACME, "ACME PLOMBERIE", (), ())
    qtbot.addWidget(editor)
    editor.show()
    assert not editor.chips.isVisible()


def test_enter_adds_the_written_tag(qtbot: QtBot, editor: TagEditor) -> None:
    QTest.keyClicks(editor.field, " Partenaire ")
    with qtbot.waitSignal(editor.added) as added:
        QTest.keyClick(editor.field, Qt.Key.Key_Return)
    assert added.args == [ACME, " Partenaire "]
    assert editor.field.text() == ""


def test_an_empty_tag_is_not_added(qtbot: QtBot, editor: TagEditor) -> None:
    QTest.keyClicks(editor.field, "   ")
    with qtbot.assertNotEmitted(editor.added):
        QTest.keyClick(editor.field, Qt.Key.Key_Return)


def test_a_chip_removes_its_tag(qtbot: QtBot, editor: TagEditor) -> None:
    with qtbot.waitSignal(editor.removed) as removed:
        editor.buttons[0].click()
    assert removed.args == [ACME, "client"]


def test_removing_the_focused_chip_moves_the_focus_to_the_field(editor: TagEditor) -> None:
    editor.buttons[0].setFocus()
    editor.show_tags((), (CLIENT, NETWORK))
    assert editor.field.hasFocus()
    assert editor.buttons == []
    assert editor.completions.stringList() == ["Client", "réseau Dupont"]


def test_new_tags_leave_the_focus_in_the_field(editor: TagEditor) -> None:
    editor.field.setFocus()
    editor.show_tags((CLIENT, NETWORK), (CLIENT, NETWORK))
    assert editor.field.hasFocus()
    assert [button.text() for button in editor.buttons] == ["Client ✕", "réseau Dupont ✕"]
