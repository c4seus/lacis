import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler, qWarning
from PySide6.QtWidgets import QApplication

from lacis.diagnostics import (
    LOG_DIRECTORY_VARIABLE,
    LOG_FILE_NAME,
    LOGGER_NAME,
    MAXIMUM_LOG_FILE_SIZE,
    MAXIMUM_MESSAGE_LENGTH,
    PREVIOUS_LOG_FILES_KEPT,
    configure_logging,
    default_log_directory,
    forward_qt_messages_to_the_log,
    log_qt_message,
)


@pytest.fixture
def lacis_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger(LOGGER_NAME)
    yield logger
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def read_log(log_file: Path) -> str:
    for handler in logging.getLogger(LOGGER_NAME).handlers:
        handler.flush()
    return log_file.read_text(encoding="utf-8")


def test_the_log_file_is_created_in_the_log_directory(
    tmp_path: Path, lacis_logger: logging.Logger
) -> None:
    log_file = configure_logging(tmp_path / "logs")
    lacis_logger.info("Lacis started")
    assert log_file == tmp_path / "logs" / LOG_FILE_NAME
    assert "INFO lacis: Lacis started" in read_log(log_file)


def test_the_log_directory_follows_the_platform_unless_overridden(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, qapp: QApplication
) -> None:
    monkeypatch.delenv(LOG_DIRECTORY_VARIABLE, raising=False)
    assert default_log_directory().name == "logs"
    monkeypatch.setenv(LOG_DIRECTORY_VARIABLE, str(tmp_path))
    assert default_log_directory() == tmp_path


def test_the_log_rotates_under_5_megabytes_and_keeps_3_previous_files(
    tmp_path: Path, lacis_logger: logging.Logger
) -> None:
    assert MAXIMUM_LOG_FILE_SIZE == 5 * 1024 * 1024
    assert PREVIOUS_LOG_FILES_KEPT == 3
    log_file = configure_logging(tmp_path, maximum_size=1024, previous_files_kept=3)
    for line_number in range(200):
        lacis_logger.info("line %d %s", line_number, "x" * 40)
    read_log(log_file)
    log_files = sorted(path.name for path in tmp_path.iterdir())
    assert log_files == ["lacis.log", "lacis.log.1", "lacis.log.2", "lacis.log.3"]
    assert all((tmp_path / name).stat().st_size <= 1024 for name in log_files)


def test_configuring_twice_keeps_a_single_log_file(
    tmp_path: Path, lacis_logger: logging.Logger
) -> None:
    configure_logging(tmp_path / "first")
    log_file = configure_logging(tmp_path / "second")
    lacis_logger.info("once")
    assert len(lacis_logger.handlers) == 1
    assert read_log(log_file).count("once") == 1


def test_long_messages_are_truncated_so_response_bodies_never_fill_the_log(
    tmp_path: Path, lacis_logger: logging.Logger
) -> None:
    log_file = configure_logging(tmp_path)
    response_body = '{"results": [' + "0" * 10_000 + "]}"
    lacis_logger.info("Response %s", response_body)
    logged = read_log(log_file)
    assert "[message truncated]" in logged
    assert len(logged) < MAXIMUM_MESSAGE_LENGTH + 200


def test_qt_messages_go_to_the_log(tmp_path: Path, lacis_logger: logging.Logger) -> None:
    log_file = configure_logging(tmp_path)
    log_qt_message(QtMsgType.QtWarningMsg, QMessageLogContext(), "QPainter is not active")
    assert "WARNING lacis.qt: QPainter is not active" in read_log(log_file)


def test_qt_warnings_are_forwarded_once_installed(
    tmp_path: Path, lacis_logger: logging.Logger
) -> None:
    log_file = configure_logging(tmp_path)
    previous_handler = forward_qt_messages_to_the_log()
    try:
        qWarning("Forwarded warning")
    finally:
        qInstallMessageHandler(previous_handler)
    assert "WARNING lacis.qt: Forwarded warning" in read_log(log_file)
