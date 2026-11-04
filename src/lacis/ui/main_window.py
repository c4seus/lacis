from PySide6.QtCore import QSize
from PySide6.QtWidgets import QMainWindow, QWidget

WINDOW_TITLE = "Lacis"
MINIMUM_SIZE = QSize(1024, 640)
DEFAULT_SIZE = QSize(1440, 900)


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(MINIMUM_SIZE)
        self.resize(DEFAULT_SIZE)
