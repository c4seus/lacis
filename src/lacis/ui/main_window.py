from typing import override

from PySide6.QtCore import QByteArray, QSettings, QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QWidget

WINDOW_TITLE = "Lacis"
MINIMUM_SIZE = QSize(1024, 640)
DEFAULT_SIZE = QSize(1440, 900)
GEOMETRY_SETTING_KEY = "main_window/geometry"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(MINIMUM_SIZE)
        self.restore_saved_geometry()

    def restore_saved_geometry(self) -> None:
        saved_geometry = self.settings.value(GEOMETRY_SETTING_KEY)
        if isinstance(saved_geometry, QByteArray) and self.restoreGeometry(saved_geometry):
            return
        self.resize(DEFAULT_SIZE)

    def save_geometry(self) -> None:
        self.settings.setValue(GEOMETRY_SETTING_KEY, self.saveGeometry())
        self.settings.sync()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self.save_geometry()
        super().closeEvent(event)
