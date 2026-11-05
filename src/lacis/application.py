import argparse
import logging
import platform
import sys
import tempfile
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path

from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QApplication

from lacis import __version__
from lacis.collectors.environment import (
    REAL_COLLECTION_ENVIRONMENT,
    CollectionEnvironment,
    demo_collection_environment,
)
from lacis.design.fonts import application_font, load_bundled_fonts
from lacis.design.theme_controller import ThemeController
from lacis.diagnostics import (
    LOGGER_NAME,
    configure_logging,
    default_log_directory,
    forward_qt_messages_to_the_log,
)
from lacis.product import PRODUCT_DESCRIPTION
from lacis.storage.locations import DEMO_DIRECTORY_PREFIX, data_directory, use_data_directory
from lacis.ui.error_dialog import install_unexpected_error_handler
from lacis.ui.main_window import MainWindow

APPLICATION_NAME = "Lacis"
ORGANIZATION_NAME = "Lacis"
APPLICATION_LOCALE = QLocale(QLocale.Language.French, QLocale.Country.France)
VERSION_OPTION_HELP = "affiche la version de Lacis et quitte"
DEMO_OPTION_HELP = (
    "démarre Lacis sur une fausse API d'entreprises fictives, "
    "avec un dossier de données temporaire"
)


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lacis",
        description=PRODUCT_DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APPLICATION_NAME} {__version__}",
        help=VERSION_OPTION_HELP,
    )
    parser.add_argument("--demo", action="store_true", help=DEMO_OPTION_HELP)
    return parser.parse_args(arguments)


def configure_application(application: QApplication) -> None:
    application.setApplicationName(APPLICATION_NAME)
    application.setApplicationDisplayName(APPLICATION_NAME)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setApplicationVersion(__version__)
    QLocale.setDefault(APPLICATION_LOCALE)
    load_bundled_fonts()
    application.setFont(application_font())


def create_application(arguments: Sequence[str]) -> QApplication:
    existing_application = QApplication.instance()
    application = (
        existing_application
        if isinstance(existing_application, QApplication)
        else QApplication(list(arguments))
    )
    configure_application(application)
    return application


def create_settings() -> QSettings:
    return QSettings(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        ORGANIZATION_NAME,
        APPLICATION_NAME,
    )


def main(command_line: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv if command_line is None else command_line)
    options = parse_arguments(arguments[1:])
    with ExitStack() as demo_resources:
        collection_environment = REAL_COLLECTION_ENVIRONMENT
        if options.demo:
            demo_directory = demo_resources.enter_context(
                tempfile.TemporaryDirectory(
                    prefix=DEMO_DIRECTORY_PREFIX, ignore_cleanup_errors=True
                )
            )
            use_data_directory(Path(demo_directory))
            collection_environment = demo_collection_environment()
        return run(arguments, collection_environment)


def run(arguments: Sequence[str], collection_environment: CollectionEnvironment) -> int:
    application = create_application(arguments)
    log_file = configure_logging(default_log_directory())
    forward_qt_messages_to_the_log()
    logger = logging.getLogger(LOGGER_NAME)
    logger.info("Lacis %s started on %s, log file %s", __version__, platform.platform(), log_file)
    if collection_environment.demo:
        logger.info("Demonstration mode on the fake API, data directory %s", data_directory())
    settings = create_settings()
    theme_controller = ThemeController(application, settings, parent=application)
    main_window = MainWindow(settings, theme_controller, collection_environment)
    install_unexpected_error_handler(log_file, main_window)
    main_window.show()
    return application.exec()
