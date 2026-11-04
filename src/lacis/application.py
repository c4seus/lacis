import argparse
import sys
from collections.abc import Sequence

from PySide6.QtCore import QLocale, QSettings
from PySide6.QtWidgets import QApplication

from lacis import __version__
from lacis.design.theme_controller import ThemeController
from lacis.ui.main_window import MainWindow

APPLICATION_NAME = "Lacis"
ORGANIZATION_NAME = "Lacis"
APPLICATION_LOCALE = QLocale(QLocale.Language.French, QLocale.Country.France)
COMMAND_DESCRIPTION = (
    "Cartographie des entreprises françaises, de leurs dirigeants et de leurs adresses."
)
VERSION_OPTION_HELP = "affiche la version de Lacis et quitte"


def parse_arguments(arguments: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lacis",
        description=COMMAND_DESCRIPTION,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APPLICATION_NAME} {__version__}",
        help=VERSION_OPTION_HELP,
    )
    return parser.parse_args(arguments)


def configure_application(application: QApplication) -> None:
    application.setApplicationName(APPLICATION_NAME)
    application.setApplicationDisplayName(APPLICATION_NAME)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setApplicationVersion(__version__)
    QLocale.setDefault(APPLICATION_LOCALE)


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
    parse_arguments(arguments[1:])
    application = create_application(arguments)
    settings = create_settings()
    ThemeController(application, settings, parent=application)
    main_window = MainWindow(settings)
    main_window.show()
    return application.exec()
