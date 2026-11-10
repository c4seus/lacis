import sqlite3
from typing import override

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT, CollectionEnvironment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.graph.background import CollectionSettings
from lacis.storage.errors import InvestigationError
from lacis.storage.investigations import UNREADABLE_DATABASE_MESSAGE as UNREADABLE
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.locations import investigations_directory
from lacis.ui.about_dialog import AboutDialog
from lacis.ui.header_bar import HOME_TRAIL, HeaderBar
from lacis.ui.home_screen import HomeScreen
from lacis.ui.investigation_page import InvestigationPage
from lacis.ui.menu_bar import MainMenuBar
from lacis.ui.notifications import NotificationArea, NotificationKind
from lacis.ui.register_search_list import RegisterSearch, RegisterSearchPopup

WINDOW_TITLE = "Lacis"
DEMO_WINDOW_TITLE = "Lacis — démonstration"
MINIMUM_SIZE = QSize(1024, 640)
DEFAULT_SIZE = QSize(1440, 900)
GEOMETRY_SETTING_KEY = "main_window/geometry"
OPENING_FAILED_TITLE = "Impossible d'ouvrir l'enquête"


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: QSettings,
        theme_controller: ThemeController,
        collection_environment: CollectionEnvironment = REAL_COLLECTION_ENVIRONMENT,
        library: InvestigationLibrary | None = None,
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
        self.main_menu_bar.new_investigation_action.triggered.connect(self.start_new_investigation)
        self.header_bar.help_menu.about_action.triggered.connect(self.show_about_dialog)
        self.about_dialog: AboutDialog | None = None
        self.setMenuBar(self.main_menu_bar)
        self.library = library or InvestigationLibrary(investigations_directory())
        self.content_area = QWidget()
        self.content_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(self.content_area)
        self.home_screen = HomeScreen(self.library, self.icon_factory)
        self.home_screen.investigation_opened.connect(self.open_investigation)
        self.investigation_page = InvestigationPage()
        self.investigation_page.home_requested.connect(self.show_home)
        self.pages.addWidget(self.home_screen)
        self.pages.addWidget(self.investigation_page)
        content_layout.addWidget(self.pages)
        self.current_investigation: str | None = None
        central_widget = QWidget(self)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.header_bar)
        central_layout.addWidget(self.content_area, 1)
        self.setCentralWidget(central_widget)

        self.search_popup = RegisterSearchPopup(self.header_bar.search_field, self)
        self.register_search = RegisterSearch(
            self.header_bar.search_field, self.search_popup, self
        )
        self.header_bar.search_button.clicked.connect(self.register_search.search_now)
        self.register_search.company_added.connect(self.show_added_company)
        self.register_search.adding_failed.connect(self.show_failure)
        self.notification_area = NotificationArea(self, self.icon_factory)
        self.register_search.company_shown.connect(self.investigation_page.show_entity)

        self.content_area.setFocus()
        self.restore_saved_geometry()

    def open_investigation(self, name: str) -> None:
        try:
            with self.library.open(name) as opened:
                investigation = opened.investigation
        except (InvestigationError, sqlite3.DatabaseError) as problem:
            message = str(problem) if isinstance(problem, InvestigationError) else UNREADABLE
            QMessageBox.warning(self, OPENING_FAILED_TITLE, message)
            self.home_screen.refresh()
            return
        self.current_investigation = name
        self.investigation_page.show_investigation(investigation)
        self.show_investigation_counts()
        self.register_search.start(
            CollectionSettings(
                self.library,
                name,
                self.collection_environment,
                self.collection_environment.timing,
            )
        )
        self.header_bar.set_search_enabled(True)
        self.header_bar.breadcrumb.set_trail((*HOME_TRAIL, name))
        self.pages.setCurrentWidget(self.investigation_page)
        self.investigation_page.back_button.setFocus()

    def show_added_company(self, identifier: str, message: str) -> None:
        self.show_investigation_counts()
        self.notification_area.notify(message, NotificationKind.SUCCESS)

    def show_failure(self, message: str) -> None:
        self.notification_area.notify(message, NotificationKind.ERROR)

    def show_investigation_counts(self) -> None:
        if self.current_investigation is not None:
            self.investigation_page.show_summary(self.library.summary(self.current_investigation))

    def show_home(self) -> None:
        self.register_search.stop()
        self.header_bar.search_field.clear()
        self.header_bar.set_search_enabled(False)
        self.current_investigation = None
        self.header_bar.breadcrumb.set_trail(HOME_TRAIL)
        self.home_screen.refresh()
        self.pages.setCurrentWidget(self.home_screen)

    def start_new_investigation(self) -> None:
        if self.pages.currentWidget() is not self.home_screen:
            self.show_home()
        self.home_screen.start_creation()

    def show_about_dialog(self) -> None:
        if self.about_dialog is None:
            self.about_dialog = AboutDialog(self.icon_factory, self)
        self.about_dialog.open()

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self.search_popup.isVisible():
            self.search_popup.reveal()
        self.notification_area.place()

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
        self.register_search.stop()
        self.save_geometry()
        super().closeEvent(event)
