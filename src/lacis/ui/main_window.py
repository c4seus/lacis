from typing import override

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget

from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT, CollectionEnvironment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.ui.about_dialog import AboutDialog
from lacis.ui.header_bar import HeaderBar
from lacis.ui.menu_bar import MainMenuBar

WINDOW_TITLE = "Lacis"
DEMO_WINDOW_TITLE = "Lacis — démonstration"
MINIMUM_SIZE = QSize(1024, 640)
DEFAULT_SIZE = QSize(1440, 900)
GEOMETRY_SETTING_KEY = "main_window/geometry"


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings,
        theme_controller: ThemeController,
        collection_environment: CollectionEnvironment = REAL_COLLECTION_ENVIRONMENT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.theme_controller = theme_controller
        self.collection_environment = collection_environment
        self.icon_factory = IconFactory(lambda: theme_controller.current_theme.colours)
        self.setWindowTitle(DEMO_WINDOW_TITLE if collection_environment.demo else WINDOW_TITLE)
        self.setMinimumSize(MINIMUM_SIZE)

        self.header_bar = HeaderBar(self.icon_factory, theme_controller)
        self.main_menu_bar = MainMenuBar(
            self.header_bar.theme_menu, self.header_bar.help_menu, self
        )
        self.main_menu_bar.quit_action.triggered.connect(self.close)
        self.header_bar.help_menu.about_action.triggered.connect(self.show_about_dialog)
        self.about_dialog: AboutDialog | None = None
        self.setMenuBar(self.main_menu_bar)
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

    def show_about_dialog(self) -> None:
        if self.about_dialog is None:
            self.about_dialog = AboutDialog(self.icon_factory, self)
        self.about_dialog.open()

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
