import sqlite3
from typing import override

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lacis.storage.errors import InvalidInvestigationQuestionError, InvestigationError
from lacis.storage.investigations import (
    UNREADABLE_DATABASE_MESSAGE,
    InvestigationLibrary,
    question_problem,
)
from lacis.ui.announcements import announce

NAME_LABEL = "Nom"
NAME_HINT = "Minuscules sans accent, chiffres et tirets"
QUESTION_LABEL = "Question"
QUESTION_HINT = "Ce à quoi l'enquête doit répondre"
CANCEL_TEXT = "Annuler"
CREATE_TEXT = "Créer"
CREATION_FAILED_TITLE = "Impossible de créer l'enquête"
EDIT_TITLE = "Modifier l'enquête"
SAVE_TEXT = "Enregistrer"
EDITING_FAILED_TITLE = "Impossible de modifier l'enquête"
EDIT_DIALOG_MINIMUM_WIDTH = 520
FIELD_SPACING = 5
NAME_STRETCH = 10
QUESTION_STRETCH = 16


def writing_failure_message(problem: OSError) -> str:
    reason = problem.strerror or str(problem)
    return f"Lacis n'a pas pu écrire dans le dossier des enquêtes ({reason})."


class ValidatedField(QWidget):
    def __init__(self, label_text: str, hint: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.hint = hint
        self.problem = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(FIELD_SPACING)
        self.label = QLabel(label_text, self)
        self.label.setProperty("tone", "field-label")
        self.input = QLineEdit(self)
        self.input.setAccessibleName(label_text)
        self.input.setAccessibleDescription(hint)
        self.label.setBuddy(self.input)
        self.hint_label = QLabel(hint, self)
        self.hint_label.setProperty("tone", "faint")
        self.problem_label = QLabel(self)
        self.problem_label.setProperty("tone", "problem")
        self.problem_label.setWordWrap(True)
        self.problem_label.hide()
        layout.addWidget(self.label)
        layout.addWidget(self.input)
        layout.addWidget(self.hint_label)
        layout.addWidget(self.problem_label)

    def text(self) -> str:
        return self.input.text()

    def show_problem(self, problem: str, announced: bool = True) -> None:
        if problem == self.problem:
            return
        self.problem = problem
        self.problem_label.setText(problem)
        self.problem_label.setVisible(bool(problem))
        self.hint_label.setVisible(not problem)
        self.input.setProperty("problem", bool(problem))
        self.input.style().unpolish(self.input)
        self.input.style().polish(self.input)
        self.input.setAccessibleDescription(problem or self.hint)
        if problem and announced:
            announce(self.input, problem)


class InvestigationFields(QObject):
    submitted = Signal()

    def __init__(
        self,
        library: InvestigationLibrary,
        parent: QWidget,
        current_name: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.current_name = current_name
        self.name_field = ValidatedField(NAME_LABEL, NAME_HINT, parent)
        self.question_field = ValidatedField(QUESTION_LABEL, QUESTION_HINT, parent)
        self.name_field.input.textEdited.connect(self.check_name)
        self.question_field.input.textEdited.connect(self.check_question)
        for field in self.fields():
            field.input.returnPressed.connect(self.submitted)

    def fields(self) -> tuple[ValidatedField, ValidatedField]:
        return self.name_field, self.question_field

    def name(self) -> str:
        return self.name_field.text()

    def question(self) -> str:
        return self.question_field.text()

    def check_name(self) -> None:
        self.name_field.show_problem(self.library.name_problem(self.name(), self.current_name))

    def check_question(self) -> None:
        self.question_field.show_problem(question_problem(self.question()))

    def fill(self, name: str, question: str) -> None:
        self.name_field.input.setText(name)
        self.question_field.input.setText(question)
        for field in self.fields():
            field.show_problem("")

    def validate(self) -> bool:
        self.name_field.show_problem(
            self.library.name_problem(self.name(), self.current_name), announced=False
        )
        self.question_field.show_problem(question_problem(self.question()), announced=False)
        invalid_field = next((field for field in self.fields() if field.problem), None)
        if invalid_field is None:
            return True
        self.report(invalid_field, invalid_field.problem)
        return False

    def report(self, field: ValidatedField, problem: str) -> None:
        field.show_problem(problem, announced=False)
        field.input.setFocus()
        announce(field.input, problem)

    def report_storage_problem(self, problem: InvestigationError) -> None:
        if isinstance(problem, InvalidInvestigationQuestionError):
            self.report(self.question_field, str(problem))
            return
        self.report(self.name_field, str(problem))


class NewInvestigationPanel(QFrame):
    created = Signal(str)
    cancelled = Signal()

    def __init__(self, library: InvestigationLibrary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.library = library
        self.setObjectName("newInvestigation")
        self.fields = InvestigationFields(library, self)
        self.fields.submitted.connect(self.create_investigation)
        self.cancel_button = QPushButton(CANCEL_TEXT, self)
        self.cancel_button.setProperty("variant", "subtle")
        self.cancel_button.clicked.connect(self.cancel)
        self.create_button = QPushButton(CREATE_TEXT, self)
        self.create_button.setProperty("variant", "primary")
        self.create_button.clicked.connect(self.create_investigation)

        button_column = QVBoxLayout()
        button_column.addSpacing(self.fields.name_field.label.sizeHint().height() + FIELD_SPACING)
        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.create_button)
        button_column.addLayout(button_row)
        button_column.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self.fields.name_field, NAME_STRETCH, Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.fields.question_field, QUESTION_STRETCH, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(button_column)
        self.hide()

    def start(self) -> None:
        self.fields.fill("", "")
        self.show()
        self.fields.name_field.input.setFocus()

    def cancel(self) -> None:
        self.hide()
        self.cancelled.emit()

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)

    def create_investigation(self) -> None:
        if not self.fields.validate():
            return
        try:
            investigation = self.library.create(self.fields.name(), self.fields.question())
        except InvestigationError as problem:
            self.fields.report_storage_problem(problem)
            return
        except OSError as problem:
            QMessageBox.warning(self, CREATION_FAILED_TITLE, writing_failure_message(problem))
            return
        self.hide()
        self.created.emit(investigation.name)


class EditInvestigationDialog(QDialog):
    saved = Signal(str)

    def __init__(
        self,
        library: InvestigationLibrary,
        name: str,
        question: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.original_name = name
        self.original_question = question
        self.setWindowTitle(EDIT_TITLE)
        self.setModal(True)
        self.setMinimumWidth(EDIT_DIALOG_MINIMUM_WIDTH)
        self.fields = InvestigationFields(library, self, current_name=name)
        self.fields.fill(name, question)
        self.cancel_button = QPushButton(CANCEL_TEXT, self)
        self.cancel_button.setProperty("variant", "subtle")
        self.cancel_button.setAutoDefault(False)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton(SAVE_TEXT, self)
        self.save_button.setProperty("variant", "primary")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.save_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)
        layout.addWidget(self.fields.name_field)
        layout.addWidget(self.fields.question_field)
        layout.addLayout(button_row)
        self.fields.name_field.input.setFocus()

    def save(self) -> None:
        if not self.fields.validate():
            return
        name = self.fields.name()
        question = self.fields.question()
        try:
            if question != self.original_question:
                self.library.change_question(self.original_name, question)
            if name != self.original_name:
                self.library.rename(self.original_name, name)
        except InvestigationError as problem:
            self.fields.report_storage_problem(problem)
            return
        except sqlite3.DatabaseError:
            QMessageBox.warning(self, EDITING_FAILED_TITLE, UNREADABLE_DATABASE_MESSAGE)
            return
        except OSError as problem:
            QMessageBox.warning(self, EDITING_FAILED_TITLE, writing_failure_message(problem))
            return
        self.accept()
        self.saved.emit(name)
