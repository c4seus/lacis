import logging
import os
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import override

from PySide6.QtCore import QMessageLogContext, QStandardPaths, QtMsgType, qInstallMessageHandler

LOGGER_NAME = "lacis"
LOG_DIRECTORY_VARIABLE = "LACIS_LOG_DIRECTORY"
LOG_DIRECTORY_NAME = "logs"
LOG_FILE_NAME = "lacis.log"
MAXIMUM_LOG_FILE_SIZE = 5 * 1024 * 1024
PREVIOUS_LOG_FILES_KEPT = 3
MAXIMUM_MESSAGE_LENGTH = 2000
TRUNCATION_MARKER = " [message truncated]"
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"
QtMessageHandler = Callable[[QtMsgType, QMessageLogContext, str], None] | None
QT_MESSAGE_LEVELS = {
    QtMsgType.QtDebugMsg: logging.DEBUG,
    QtMsgType.QtInfoMsg: logging.INFO,
    QtMsgType.QtWarningMsg: logging.WARNING,
    QtMsgType.QtCriticalMsg: logging.ERROR,
    QtMsgType.QtFatalMsg: logging.CRITICAL,
}


class MessageLengthFilter(logging.Filter):
    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if len(message) > MAXIMUM_MESSAGE_LENGTH:
            record.msg = message[:MAXIMUM_MESSAGE_LENGTH] + TRUNCATION_MARKER
            record.args = None
        return True


def default_log_directory() -> Path:
    overridden_directory = os.environ.get(LOG_DIRECTORY_VARIABLE)
    if overridden_directory:
        return Path(overridden_directory)
    state_directory = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.StateLocation
    )
    return Path(state_directory) / LOG_DIRECTORY_NAME


def configure_logging(
    log_directory: Path,
    maximum_size: int = MAXIMUM_LOG_FILE_SIZE,
    previous_files_kept: int = PREVIOUS_LOG_FILES_KEPT,
) -> Path:
    log_directory.mkdir(parents=True, exist_ok=True)
    log_file = log_directory / LOG_FILE_NAME
    handler = RotatingFileHandler(
        log_file, maxBytes=maximum_size, backupCount=previous_files_kept, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(MessageLengthFilter())
    logger = logging.getLogger(LOGGER_NAME)
    for previous_handler in list(logger.handlers):
        logger.removeHandler(previous_handler)
        previous_handler.close()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return log_file


def log_qt_message(message_type: QtMsgType, context: QMessageLogContext, message: str) -> None:
    logging.getLogger(f"{LOGGER_NAME}.qt").log(QT_MESSAGE_LEVELS[message_type], message)


def forward_qt_messages_to_the_log() -> QtMessageHandler:
    return qInstallMessageHandler(log_qt_message)
