from typing import override

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.ui.header_bar import HeaderBar

WINDOW_TITLE = "Lacis"
MINIMUM_SIZE = QSize(1024, 640)
DEFAULT_SIZE = QSize(1440, 900)
GEOMETRY_SETTING_KEY = "main_window/geometry"


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings,
        theme_controller: ThemeController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.theme_controller = theme_controller
        self.icon_factory = IconFactory(lambda: theme_controller.current_theme.colours)
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(MINIMUM_SIZE)

        self.header_bar = HeaderBar(self.icon_factory, theme_controller)
        self.content_area = QWidget()
        self.content_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        central_widget = QWidget(self)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.header_bar)
        central_layout.addWidget(self.content_area, 1)
        self.setCentralWidget(central_widget)

        self.content_area.setFocus()
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
