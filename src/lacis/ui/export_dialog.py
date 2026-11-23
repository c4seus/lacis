from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from lacis.exports.formats import EXPORT_FORMATS, ExportFormat
from lacis.signals.facts import counted

WINDOW_TITLE = "Exporter l'enquête"
FORMAT_LABEL = "&Format"
SCOPE_LABEL = "Contenu"
DESTINATION_LABEL = "&Destination"
CHOOSE_TEXT = "C&hoisir…"
CHOOSE_FILE_ACCESSIBLE_NAME = "Choisir le fichier de destination"
CHOOSE_FOLDER_ACCESSIBLE_NAME = "Choisir le dossier de destination"
EXPORT_TEXT = "&Exporter"
CANCEL_TEXT = "Annuler"
NO_FILTER_TEXT = "Aucun filtre n'est actif dans le graphe."
MISSING_FOLDER_TEXT = "Ce dossier n'existe pas."
FOLDER_GIVEN_TEXT = "Ce chemin désigne un dossier : ajoutez un nom de fichier."
MISSING_PATH_TEXT = "Choisissez un fichier de destination."
MISSING_VAULT_TEXT = "Choisissez un dossier de destination."
FILE_GIVEN_TEXT = "Ce chemin désigne un fichier : choisissez un dossier."
NOT_EMPTY_TEXT = "Ce dossier n'est pas vide : choisissez un nouveau dossier ou un dossier vide."
NEW_FOLDER_TEXT = "Ce dossier sera créé."
REPLACED_TEXT = "Ce fichier existe déjà : il sera remplacé."
WHOLE_PREFIX = "&Toute l'enquête, "
FILTERED_PREFIX = "La &vue filtrée, "
PATH_WIDTH_IN_CHARACTERS = 48

type PathChooser = Callable[[QWidget, str, str, str], str]
type FolderChooser = Callable[[QWidget, str, str], str]


def save_file_name(parent: QWidget, title: str, path: str, filters: str) -> str:
    chosen, _filter = QFileDialog.getSaveFileName(parent, title, path, filters)
    return chosen


def existing_folder(parent: QWidget, title: str, path: str) -> str:
    return QFileDialog.getExistingDirectory(parent, title, path)


def without_extension(path: Path, extension: str) -> Path:
    if not extension:
        return path
    if path.name.endswith(extension):
        return path.with_name(path.name[: -len(extension)])
    return path.with_suffix("")


def entities_text(count: int) -> str:
    return counted(count, "entité", "entités")


@dataclass(frozen=True)
class ExportOffer:
    name: str
    folder: Path
    total: int
    shown: int | None
    chosen_format: ExportFormat


@dataclass(frozen=True)
class ExportRequest:
    export_format: ExportFormat
    filtered: bool
    destination: Path


class ExportDialog(QDialog):
    def __init__(
        self,
        offer: ExportOffer,
        parent: QWidget | None = None,
        choose_path: PathChooser = save_file_name,
        choose_folder: FolderChooser = existing_folder,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.choose_path = choose_path
        self.choose_folder = choose_folder
        total, shown, chosen_format = offer.total, offer.shown, offer.chosen_format
        self.format_box = QComboBox(self)
        for candidate in EXPORT_FORMATS:
            self.format_box.addItem(f"{candidate.label} : {candidate.description}", candidate.key)
        self.format_box.setCurrentIndex(self.format_box.findData(chosen_format.key))
        self.current_format = chosen_format
        self.whole_button = QRadioButton(f"{WHOLE_PREFIX}{entities_text(total)}", self)
        self.filtered_button = QRadioButton(
            f"{FILTERED_PREFIX}{entities_text(shown if shown is not None else total)}", self
        )
        self.whole_button.setChecked(True)
        self.filtered_button.setEnabled(shown is not None)
        if shown is None:
            self.filtered_button.setToolTip(NO_FILTER_TEXT)
            self.filtered_button.setAccessibleDescription(NO_FILTER_TEXT)
        self.scope_group = QButtonGroup(self)
        self.scope_group.addButton(self.whole_button)
        self.scope_group.addButton(self.filtered_button)
        default_path = offer.folder / f"{offer.name}{chosen_format.extension}"
        self.path_field = QLineEdit(str(default_path), self)
        self.path_field.setMinimumWidth(
            self.fontMetrics().averageCharWidth() * PATH_WIDTH_IN_CHARACTERS
        )
        self.choose_button = QPushButton(CHOOSE_TEXT, self)
        self.choose_button.setAccessibleName(self.choose_accessible_name())
        self.choose_button.clicked.connect(self.choose)
        self.problem_label = QLabel(self)
        self.problem_label.setWordWrap(True)
        self.problem_label.setProperty("tone", "muted")
        self.buttons = QDialogButtonBox(self)
        self.export_button = self.buttons.addButton(
            EXPORT_TEXT, QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.buttons.addButton(CANCEL_TEXT, QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.format_box.currentIndexChanged.connect(self.follow_format)
        self.path_field.textChanged.connect(self.check_destination)
        self.lay_out()
        self.check_destination()

    def lay_out(self) -> None:
        scope = QVBoxLayout()
        scope.addWidget(self.whole_button)
        scope.addWidget(self.filtered_button)
        destination = QHBoxLayout()
        destination.addWidget(self.path_field, 1)
        destination.addWidget(self.choose_button)
        self.format_label = QLabel(FORMAT_LABEL, self)
        self.format_label.setBuddy(self.format_box)
        self.destination_label = QLabel(DESTINATION_LABEL, self)
        self.destination_label.setBuddy(self.path_field)
        form = QFormLayout()
        form.addRow(self.format_label, self.format_box)
        form.addRow(SCOPE_LABEL, scope)
        form.addRow(self.destination_label, destination)
        form.addRow("", self.problem_label)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)
        for button in (self.whole_button, self.filtered_button):
            button.setAccessibleName(f"{SCOPE_LABEL} : {button.text().replace('&', '')}")

    def chosen_format(self) -> ExportFormat:
        key = self.format_box.currentData()
        return next(candidate for candidate in EXPORT_FORMATS if candidate.key == key)

    def destination(self) -> Path:
        return Path(self.path_field.text().strip()).expanduser()

    def request(self) -> ExportRequest:
        return ExportRequest(
            self.chosen_format(), self.filtered_button.isChecked(), self.destination()
        )

    def choose_accessible_name(self) -> str:
        if self.chosen_format().folder:
            return CHOOSE_FOLDER_ACCESSIBLE_NAME
        return CHOOSE_FILE_ACCESSIBLE_NAME

    def follow_format(self) -> None:
        previous, chosen_format = self.current_format, self.chosen_format()
        self.current_format = chosen_format
        destination = self.destination()
        if destination.name:
            base = without_extension(destination, previous.extension)
            self.path_field.setText(str(base.with_name(f"{base.name}{chosen_format.extension}")))
        self.choose_button.setAccessibleName(self.choose_accessible_name())
        self.check_destination()

    def choose(self) -> None:
        chosen_format = self.chosen_format()
        if chosen_format.folder:
            chosen = self.choose_folder(self, WINDOW_TITLE, str(self.destination()))
        else:
            filters = f"{chosen_format.label} (*{chosen_format.extension})"
            chosen = self.choose_path(self, WINDOW_TITLE, str(self.destination()), filters)
        if chosen:
            self.path_field.setText(chosen)

    def check_destination(self) -> None:
        problem, blocking = self.destination_problem()
        self.problem_label.setText(problem)
        self.problem_label.setVisible(bool(problem))
        self.path_field.setAccessibleDescription(problem)
        self.export_button.setEnabled(not blocking)

    def destination_problem(self) -> tuple[str, bool]:
        if self.chosen_format().folder:
            return self.vault_problem()
        if not self.path_field.text().strip():
            return MISSING_PATH_TEXT, True
        destination = self.destination()
        if destination.is_dir():
            return FOLDER_GIVEN_TEXT, True
        if not destination.parent.is_dir():
            return MISSING_FOLDER_TEXT, True
        if destination.exists():
            return REPLACED_TEXT, False
        return "", False

    def vault_problem(self) -> tuple[str, bool]:
        if not self.path_field.text().strip():
            return MISSING_VAULT_TEXT, True
        destination = self.destination()
        if destination.is_dir():
            if any(destination.iterdir()):
                return NOT_EMPTY_TEXT, True
            return "", False
        if destination.exists():
            return FILE_GIVEN_TEXT, True
        if not destination.parent.is_dir():
            return MISSING_FOLDER_TEXT, True
        return NEW_FOLDER_TEXT, False
