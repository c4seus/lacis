import logging
import sys
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from lacis.diagnostics import LOGGER_NAME

ERROR_DIALOG_TITLE = "Erreur inattendue"
ERROR_MESSAGE = (
    "Lacis a rencontré une erreur inattendue. L'action en cours n'a pas abouti, "
    "mais vous pouvez continuer à travailler."
)
LOG_LOCATION_MESSAGE = "Les détails ont été enregistrés dans le journal\u00a0:\n{log_file}"
OPEN_LOG_DIRECTORY_TEXT = "Ouvrir le dossier du journal"
CLOSE_TEXT = "Fermer"
UNHANDLED_EXCEPTION_LOG_MESSAGE = "Unhandled exception"


class ErrorDialog(QMessageBox):
    def __init__(self, log_file: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.log_file = log_file
        self.setIcon(QMessageBox.Icon.Critical)
        self.setWindowTitle(ERROR_DIALOG_TITLE)
        self.setText(ERROR_MESSAGE)
        self.setInformativeText(LOG_LOCATION_MESSAGE.format(log_file=log_file))
        self.open_log_directory_button = QPushButton(OPEN_LOG_DIRECTORY_TEXT, self)
        self.open_log_directory_button.clicked.connect(self.open_log_directory)
        self.addButton(self.open_log_directory_button, QMessageBox.ButtonRole.ActionRole)
        self.close_button = self.addButton(CLOSE_TEXT, QMessageBox.ButtonRole.RejectRole)
        self.setDefaultButton(self.close_button)

    def open_log_directory(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_file.parent)))


class UnexpectedErrorHandler:
    def __init__(self, log_file: Path, parent: QWidget | None = None) -> None:
        self.log_file = log_file
        self.parent = parent
        self.error_dialog: ErrorDialog | None = None

    def handle(
        self,
        exception_type: type[BaseException],
        exception: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        if issubclass(exception_type, KeyboardInterrupt):
            sys.__excepthook__(exception_type, exception, traceback)
            return
        logging.getLogger(LOGGER_NAME).critical(
            UNHANDLED_EXCEPTION_LOG_MESSAGE, exc_info=(exception_type, exception, traceback)
        )
        if self.error_dialog is not None and self.error_dialog.isVisible():
            return
        self.error_dialog = ErrorDialog(self.log_file, self.parent)
        self.error_dialog.open()


def install_unexpected_error_handler(
    log_file: Path, parent: QWidget | None = None
) -> UnexpectedErrorHandler:
    handler = UnexpectedErrorHandler(log_file, parent)
    sys.excepthook = handler.handle
    return handler
