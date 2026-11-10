import errno
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from lacis.storage.errors import (
    InvalidInvestigationQuestionError,
    InvestigationAlreadyExistsError,
)
from lacis.storage.investigations import MAXIMUM_QUESTION_LENGTH, InvestigationLibrary
from lacis.ui import investigation_form
from lacis.ui.investigation_form import (
    NewInvestigationPanel,
    ValidatedField,
    announce,
    writing_failure_message,
)

QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
EMPTY_NAME = "Le nom de l'enquête est obligatoire."
TAKEN_NAME = "Une enquête nommée « fournisseur-acme » existe déjà."
TOO_LONG_QUESTION = (
    f"La question de départ ne doit pas dépasser {MAXIMUM_QUESTION_LENGTH} caractères."
)


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("fournisseur-acme", "Ce fournisseur est-il fiable avant de signer ?")
    return library


@pytest.fixture
def announcements(monkeypatch: pytest.MonkeyPatch) -> list[tuple[QWidget, str]]:
    announced: list[tuple[QWidget, str]] = []
    monkeypatch.setattr(
        investigation_form,
        "announce",
        lambda widget, message: announced.append((widget, message)),
    )
    return announced


def open_panel(qtbot: QtBot, library: InvestigationLibrary) -> NewInvestigationPanel:
    panel = NewInvestigationPanel(library)
    qtbot.addWidget(panel)
    panel.start()
    panel.activateWindow()
    qtbot.waitUntil(panel.isActiveWindow)
    return panel


def type_into(field: ValidatedField, text: str) -> None:
    field.input.clear()
    QTest.keyClicks(field.input, text)


def test_a_field_shows_its_label_and_hint(qtbot: QtBot) -> None:
    field = ValidatedField("Nom", "Minuscules sans accent, chiffres et tirets")
    qtbot.addWidget(field)
    field.show()
    assert field.label.text() == "Nom"
    assert field.label.buddy() is field.input
    assert field.input.accessibleName() == "Nom"
    assert field.input.accessibleDescription() == "Minuscules sans accent, chiffres et tirets"
    assert field.hint_label.isVisible()
    assert not field.problem_label.isVisible()


def test_a_problem_replaces_the_hint_next_to_the_field_and_is_announced(
    qtbot: QtBot, announcements: list[tuple[QWidget, str]]
) -> None:
    field = ValidatedField("Nom", "Minuscules sans accent, chiffres et tirets")
    qtbot.addWidget(field)
    field.show()
    field.show_problem(EMPTY_NAME)
    assert field.problem_label.isVisible()
    assert field.problem_label.text() == EMPTY_NAME
    assert not field.hint_label.isVisible()
    assert field.input.property("problem") is True
    assert field.input.accessibleDescription() == EMPTY_NAME
    assert announcements == [(field.input, EMPTY_NAME)]


def test_a_problem_is_announced_once_until_it_changes(
    qtbot: QtBot, announcements: list[tuple[QWidget, str]]
) -> None:
    field = ValidatedField("Nom", "Minuscules sans accent, chiffres et tirets")
    qtbot.addWidget(field)
    field.show_problem(EMPTY_NAME)
    field.show_problem(EMPTY_NAME)
    field.show_problem("")
    assert announcements == [(field.input, EMPTY_NAME)]
    assert field.input.property("problem") is False
    assert field.input.accessibleDescription() == "Minuscules sans accent, chiffres et tirets"


def test_an_announcement_reaches_the_accessibility_layer(qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    announce(widget, EMPTY_NAME)


def test_the_panel_starts_empty_with_the_focus_on_the_name(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    fields = panel.fields
    assert panel.isVisible()
    assert fields.name() == ""
    assert fields.question() == ""
    assert fields.name_field.input.hasFocus()
    assert fields.question_field.hint_label.text() == "Ce à quoi l'enquête doit répondre"
    assert panel.create_button.text() == "Créer"
    assert panel.cancel_button.text() == "Annuler"


def test_the_name_is_validated_as_the_user_types(
    qtbot: QtBot, library: InvestigationLibrary, announcements: list[tuple[QWidget, str]]
) -> None:
    panel = open_panel(qtbot, library)
    name_field = panel.fields.name_field
    type_into(name_field, "Faux")
    assert name_field.problem.startswith("Le nom de l'enquête ne peut contenir que")
    type_into(name_field, "fournisseur-acme")
    assert name_field.problem == TAKEN_NAME
    type_into(name_field, "faux-plombiers-31")
    assert name_field.problem == ""
    assert TAKEN_NAME in [message for _, message in announcements]


def test_emptying_the_name_shows_that_it_is_required(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    name_field = panel.fields.name_field
    QTest.keyClicks(name_field.input, "a")
    QTest.keyClick(name_field.input, Qt.Key.Key_Backspace)
    assert name_field.problem == EMPTY_NAME


def test_the_question_is_validated_as_the_user_types(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    question_field = panel.fields.question_field
    question_field.input.setText("?" * MAXIMUM_QUESTION_LENGTH)
    QTest.keyClicks(question_field.input, "?")
    assert question_field.problem == TOO_LONG_QUESTION
    QTest.keyClick(question_field.input, Qt.Key.Key_Backspace)
    assert question_field.problem == ""


def test_creating_a_valid_investigation_closes_the_panel(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    type_into(panel.fields.name_field, "faux-plombiers-31")
    panel.fields.question_field.input.setText(QUESTION)
    with qtbot.waitSignal(panel.created) as created:
        panel.create_button.click()
    assert created.args == ["faux-plombiers-31"]
    assert not panel.isVisible()
    with library.open("faux-plombiers-31") as opened:
        assert opened.investigation.question == QUESTION


def test_enter_in_a_field_creates_the_investigation(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    type_into(panel.fields.name_field, "faux-plombiers-31")
    with qtbot.waitSignal(panel.created):
        QTest.keyClick(panel.fields.name_field.input, Qt.Key.Key_Return)
    assert "faux-plombiers-31" in library.names()


def test_an_invalid_form_creates_nothing_and_focuses_the_first_problem(
    qtbot: QtBot, library: InvestigationLibrary, announcements: list[tuple[QWidget, str]]
) -> None:
    panel = open_panel(qtbot, library)
    fields = panel.fields
    fields.question_field.input.setText("?" * (MAXIMUM_QUESTION_LENGTH + 1))
    fields.question_field.input.setFocus()
    panel.create_button.click()
    assert library.names() == ["fournisseur-acme"]
    assert panel.isVisible()
    assert fields.name_field.problem == EMPTY_NAME
    assert fields.question_field.problem == TOO_LONG_QUESTION
    assert fields.name_field.input.hasFocus()
    assert announcements == [(fields.name_field.input, EMPTY_NAME)]


def test_a_question_problem_alone_focuses_the_question(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    fields = panel.fields
    fields.name_field.input.setText("faux-plombiers-31")
    fields.question_field.input.setText("?" * (MAXIMUM_QUESTION_LENGTH + 1))
    panel.create_button.click()
    assert fields.question_field.input.hasFocus()
    assert library.names() == ["fournisseur-acme"]


def test_a_name_taken_meanwhile_is_shown_next_to_the_name(
    qtbot: QtBot,
    library: InvestigationLibrary,
    monkeypatch: pytest.MonkeyPatch,
    announcements: list[tuple[QWidget, str]],
) -> None:
    panel = open_panel(qtbot, library)
    fields = panel.fields
    fields.name_field.input.setText("faux-plombiers-31")

    def taken_meanwhile(name: str, question: str) -> None:
        raise InvestigationAlreadyExistsError(name)

    monkeypatch.setattr(library, "create", taken_meanwhile)
    panel.create_button.click()
    expected = "Une enquête nommée « faux-plombiers-31 » existe déjà."
    assert fields.name_field.problem == expected
    assert announcements == [(fields.name_field.input, expected)]
    assert panel.isVisible()


def test_a_question_refused_by_the_storage_is_shown_next_to_the_question(
    qtbot: QtBot, library: InvestigationLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    panel = open_panel(qtbot, library)
    fields = panel.fields
    fields.name_field.input.setText("faux-plombiers-31")

    def refused(name: str, question: str) -> None:
        raise InvalidInvestigationQuestionError(TOO_LONG_QUESTION)

    monkeypatch.setattr(library, "create", refused)
    panel.create_button.click()
    assert fields.question_field.problem == TOO_LONG_QUESTION
    assert fields.question_field.input.hasFocus()


def test_a_folder_that_cannot_be_written_is_reported(
    qtbot: QtBot, library: InvestigationLibrary, monkeypatch: pytest.MonkeyPatch
) -> None:
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda parent, title, text: warnings.append((title, text))
    )
    panel = open_panel(qtbot, library)
    panel.fields.name_field.input.setText("faux-plombiers-31")

    def unwritable(name: str, question: str) -> None:
        raise PermissionError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(library, "create", unwritable)
    panel.create_button.click()
    assert warnings == [
        (
            "Impossible de créer l'enquête",
            "Lacis n'a pas pu écrire dans le dossier des enquêtes (Permission denied).",
        )
    ]
    assert panel.isVisible()


def test_a_writing_failure_without_reason_shows_the_error() -> None:
    assert writing_failure_message(OSError("disque plein")) == (
        "Lacis n'a pas pu écrire dans le dossier des enquêtes (disque plein)."
    )


def test_cancelling_hides_the_panel_and_creates_nothing(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    type_into(panel.fields.name_field, "faux-plombiers-31")
    with qtbot.waitSignal(panel.cancelled):
        panel.cancel_button.click()
    assert not panel.isVisible()
    assert library.names() == ["fournisseur-acme"]


def test_escape_cancels_the_creation(qtbot: QtBot, library: InvestigationLibrary) -> None:
    panel = open_panel(qtbot, library)
    with qtbot.waitSignal(panel.cancelled):
        QTest.keyClick(panel.fields.question_field.input, Qt.Key.Key_Escape)
    assert not panel.isVisible()


def test_other_keys_do_not_cancel_the_creation(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    QTest.keyClick(panel, Qt.Key.Key_A)
    assert panel.isVisible()


def test_starting_again_clears_the_previous_attempt(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    panel = open_panel(qtbot, library)
    type_into(panel.fields.name_field, "Faux")
    panel.cancel_button.click()
    panel.start()
    assert panel.fields.name() == ""
    assert panel.fields.name_field.problem == ""
