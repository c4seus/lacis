import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

DATA_DIRECTORY_VARIABLE = "LACIS_DATA_DIRECTORY"
CONFIGURATION_DIRECTORY_VARIABLE = "LACIS_CONFIGURATION_DIRECTORY"
INVESTIGATIONS_DIRECTORY_NAME = "investigations"
DEMO_DIRECTORY_PREFIX = "lacis-demo-"


def data_directory() -> Path:
    overridden_directory = os.environ.get(DATA_DIRECTORY_VARIABLE)
    if overridden_directory:
        return Path(overridden_directory)
    data_location = QStandardPaths.StandardLocation.AppLocalDataLocation
    return Path(QStandardPaths.writableLocation(data_location))


def investigations_directory() -> Path:
    return data_directory() / INVESTIGATIONS_DIRECTORY_NAME


def use_data_directory(directory: Path) -> None:
    os.environ[DATA_DIRECTORY_VARIABLE] = str(directory)


def configuration_directory() -> Path:
    overridden_directory = os.environ.get(CONFIGURATION_DIRECTORY_VARIABLE)
    if overridden_directory:
        return Path(overridden_directory)
    configuration_location = QStandardPaths.StandardLocation.AppConfigLocation
    return Path(QStandardPaths.writableLocation(configuration_location))
