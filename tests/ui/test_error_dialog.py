import sys
from pathlib import Path
from types import TracebackType

import pytest
from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from lacis.diagnostics import configure_logging
from lacis.ui.error_dialog import (
    ErrorDialog,
    UnexpectedErrorHandler,
    install_unexpected_error_handler,
)


class FailingAction(QObject):
    triggered = Signal()


def raised(exception: BaseException) -> tuple[type[BaseException], BaseException, TracebackType]:
    with pytest.raises(type(exception)) as raised_exception:
        raise exception
    return raised_exception.type, raised_exception.value, raised_exception.tb


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    return configure_logging(tmp_path / "logs")


@pytest.fixture
def parent_window(qtbot: QtBot) -> QWidget:
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    return window


@pytest.fixture
def restored_exception_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)


def test_the_error_dialog_explains_in_french_and_gives_the_log_path(
    qtbot: QtBot, log_file: Path
) -> None:
    dialog = ErrorDialog(log_file)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Erreur inattendue"
    assert dialog.text().startswith("Lacis a rencontré une erreur inattendue.")
    assert str(log_file) in dialog.informativeText()
    assert dialog.icon() == QMessageBox.Icon.Critical
    assert dialog.close_button.text() == "Fermer"
    assert dialog.defaultButton() is dialog.close_button


def test_the_error_dialog_opens_the_log_directory(
    qtbot: QtBot, log_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened_urls: list[QUrl] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(opened_urls.append))
    dialog = ErrorDialog(log_file)
    qtbot.addWidget(dialog)
    assert dialog.open_log_directory_button.text() == "Ouvrir le dossier du journal"
    dialog.open_log_directory_button.click()
    assert opened_urls == [QUrl.fromLocalFile(str(log_file.parent))]


def test_an_unexpected_error_is_logged_with_its_traceback(
    qtbot: QtBot, log_file: Path, parent_window: QWidget
) -> None:
    handler = UnexpectedErrorHandler(log_file, parent_window)
    handler.handle(*raised(ValueError("SIREN invalide")))
    assert handler.error_dialog is not None
    qtbot.addWidget(handler.error_dialog)
    log_text = log_file.read_text(encoding="utf-8")
    assert "CRITICAL lacis: Unhandled exception" in log_text
    assert "ValueError: SIREN invalide" in log_text
    assert "Traceback" in log_text


def test_an_unexpected_error_shows_the_dialog_over_the_window(
    qtbot: QtBot, log_file: Path, parent_window: QWidget
) -> None:
    handler = UnexpectedErrorHandler(log_file, parent_window)
    handler.handle(*raised(RuntimeError("boom")))
    dialog = handler.error_dialog
    assert dialog is not None
    qtbot.addWidget(dialog)
    qtbot.waitExposed(dialog)
    assert dialog.isVisible()
    assert dialog.parent() is parent_window
    assert parent_window.isVisible()


def test_a_second_error_does_not_stack_another_dialog(
    qtbot: QtBot, log_file: Path, parent_window: QWidget
) -> None:
    handler = UnexpectedErrorHandler(log_file, parent_window)
    handler.handle(*raised(RuntimeError("first")))
    first_dialog = handler.error_dialog
    assert first_dialog is not None
    qtbot.addWidget(first_dialog)
    handler.handle(*raised(RuntimeError("second")))
    assert handler.error_dialog is first_dialog
    assert "RuntimeError: second" in log_file.read_text(encoding="utf-8")


def test_a_new_error_after_closing_the_dialog_opens_it_again(
    qtbot: QtBot, log_file: Path, parent_window: QWidget
) -> None:
    handler = UnexpectedErrorHandler(log_file, parent_window)
    handler.handle(*raised(RuntimeError("first")))
    first_dialog = handler.error_dialog
    assert first_dialog is not None
    qtbot.addWidget(first_dialog)
    first_dialog.close()
    handler.handle(*raised(RuntimeError("second")))
    assert handler.error_dialog is not first_dialog
    assert handler.error_dialog is not None
    qtbot.addWidget(handler.error_dialog)


def test_interrupting_with_ctrl_c_keeps_the_default_behaviour(
    log_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    received: list[type[BaseException]] = []
    monkeypatch.setattr(
        sys,
        "__excepthook__",
        lambda exception_type, exception, traceback: received.append(exception_type),
    )
    handler = UnexpectedErrorHandler(log_file)
    handler.handle(*raised(KeyboardInterrupt()))
    assert received == [KeyboardInterrupt]
    assert handler.error_dialog is None


def test_an_error_in_an_action_shows_the_dialog_instead_of_closing(
    qtbot: QtBot, log_file: Path, parent_window: QWidget, restored_exception_hook: None
) -> None:
    handler = install_unexpected_error_handler(log_file, parent_window)
    action = FailingAction()

    def fail() -> None:
        raise RuntimeError("expansion failed")

    action.triggered.connect(fail)
    action.triggered.emit()
    assert handler.error_dialog is not None
    qtbot.addWidget(handler.error_dialog)
    assert handler.error_dialog.isVisible()
    assert parent_window.isVisible()
    assert "RuntimeError: expansion failed" in log_file.read_text(encoding="utf-8")
