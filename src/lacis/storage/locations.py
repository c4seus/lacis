import os
from pathlib import Path

from PySide6.QtCore import QStandardPaths

DATA_DIRECTORY_VARIABLE = "LACIS_DATA_DIRECTORY"
INVESTIGATIONS_DIRECTORY_NAME = "investigations"


def data_directory() -> Path:
    overridden_directory = os.environ.get(DATA_DIRECTORY_VARIABLE)
    if overridden_directory:
        return Path(overridden_directory)
    data_location = QStandardPaths.StandardLocation.AppLocalDataLocation
    return Path(QStandardPaths.writableLocation(data_location))


def investigations_directory() -> Path:
    return data_directory() / INVESTIGATIONS_DIRECTORY_NAME
