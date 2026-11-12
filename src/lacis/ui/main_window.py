import sqlite3
from typing import override

from PySide6.QtCore import QByteArray, QSettings, QSize, Qt
from PySide6.QtGui import QCloseEvent, QResizeEvent
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget, QVBoxLayout, QWidget

from lacis.collectors.environment import REAL_COLLECTION_ENVIRONMENT, CollectionEnvironment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.details import entity_details, raw_response
from lacis.graph.background import BackgroundJob, CollectionSettings, layout_job, move_job
from lacis.graph.expansion import MINIMUM_DEPTH
from lacis.overview import read_overview
from lacis.signals.store import SignalReport
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
from lacis.ui.raw_response_dialog import RawResponseDialog
from lacis.ui.register_search_list import RegisterSearch, RegisterSearchPopup
from lacis.ui.review_actions import ReviewActions
from lacis.ui.shortcuts_dialog import ShortcutsDialog, shortcut_groups

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
        self.main_menu_bar.close_investigation_action.triggered.connect(self.show_home)
        self.header_bar.breadcrumb.step_activated.connect(self.follow_breadcrumb)
        self.header_bar.help_menu.about_action.triggered.connect(self.show_about_dialog)
        self.about_dialog: AboutDialog | None = None
        self.header_bar.help_menu.shortcuts_action.triggered.connect(self.show_shortcuts_dialog)
        self.shortcuts_dialog: ShortcutsDialog | None = None
        self.setMenuBar(self.main_menu_bar)
        self.library = library or InvestigationLibrary(investigations_directory())
        self.content_area = QWidget()
        self.content_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.pages = QStackedWidget(self.content_area)
        self.home_screen = HomeScreen(self.library, self.icon_factory)
        self.home_screen.investigation_opened.connect(self.open_investigation)
        self.investigation_page = InvestigationPage(settings, self.icon_factory)
        self.connect_investigation_page()
        self.layout_job: BackgroundJob | None = None
        self.report: SignalReport | None = None
        self.move_jobs: list[BackgroundJob] = []
        self.pages.addWidget(self.home_screen)
        self.pages.addWidget(self.investigation_page)
        content_layout.addWidget(self.pages)
        self.current_investigation: str | None = None
        self.setCentralWidget(self.central_widget())

        self.search_popup = RegisterSearchPopup(self.header_bar.search_field, self)
        self.register_search = RegisterSearch(
            self.header_bar.search_field, self.search_popup, self
        )
        self.header_bar.search_button.clicked.connect(self.register_search.search_now)
        self.register_search.company_added.connect(self.show_added_company)
        self.register_search.adding_failed.connect(self.show_failure)
        self.notification_area = NotificationArea(self, self.icon_factory)
        self.review_actions = ReviewActions(
            self.main_menu_bar, self.notification_area.notify, self
        )
        self.connect_review_actions()
        self.register_search.company_shown.connect(self.investigation_page.show_entity)

        self.content_area.setFocus()
        self.restore_saved_geometry()

    def central_widget(self) -> QWidget:
        central_widget = QWidget(self)
        central_layout = QVBoxLayout(central_widget)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.header_bar)
        central_layout.addWidget(self.content_area, 1)
        return central_widget

    def connect_investigation_page(self) -> None:
        queue_action = self.main_menu_bar.queue_action
        queue_action.setChecked(not self.investigation_page.is_queue_collapsed())
        queue_action.toggled.connect(self.investigation_page.toggle_queue)
        self.investigation_page.queue_toggled.connect(queue_action.setChecked)
        self.investigation_page.entities_moved.connect(self.save_moved_positions)
        self.investigation_page.graph_area.layout_requested.connect(self.lay_out_again)
        graph_view = self.investigation_page.graph_view
        self.main_menu_bar.zoom_in_action.triggered.connect(graph_view.zoom_in)
        self.main_menu_bar.zoom_out_action.triggered.connect(graph_view.zoom_out)
        self.main_menu_bar.fit_action.triggered.connect(graph_view.fit)
        self.main_menu_bar.layout_action.triggered.connect(self.lay_out_again)
        self.main_menu_bar.search_action.triggered.connect(self.focus_search)
        details_panel = self.investigation_page.details_panel
        sheet = details_panel.entity_sheet
        self.main_menu_bar.expand_action.triggered.connect(lambda: sheet.expand(MINIMUM_DEPTH))
        sheet.expandable_changed.connect(self.follow_expandable)
        self.main_menu_bar.next_tab_action.triggered.connect(details_panel.show_next_tab)
        self.main_menu_bar.previous_tab_action.triggered.connect(details_panel.show_previous_tab)
        for index, action in enumerate(self.main_menu_bar.tab_actions):
            action.triggered.connect(lambda _checked, index=index: details_panel.show_tab(index))

    def connect_review_actions(self) -> None:
        review_list = self.investigation_page.queue_column.review_list
        self.review_actions.changed.connect(self.refresh_overview)
        self.review_actions.expanding_changed.connect(review_list.show_expanding)
        self.review_actions.expanding_changed.connect(
            self.investigation_page.details_panel.entity_sheet.show_running
        )
        self.investigation_page.decision_requested.connect(self.review_actions.decide)
        self.investigation_page.expansion_requested.connect(self.review_actions.expand)
        self.investigation_page.entity_selected.connect(self.show_details)
        self.investigation_page.notices_refresh_requested.connect(
            self.review_actions.refresh_notices
        )
        sheet = self.investigation_page.details_panel.entity_sheet
        sheet.raw_requested.connect(self.show_raw_response)
        self.investigation_page.details_panel.journal_tab.raw_requested.connect(
            self.show_raw_response
        )
        sheet.copied.connect(
            lambda message: self.notification_area.notify(message, NotificationKind.SUCCESS)
        )

    def open_investigation(self, name: str) -> None:
        try:
            with self.library.open(name) as opened:
                investigation = opened.investigation
        except (InvestigationError, sqlite3.DatabaseError) as problem:
            message = str(problem) if isinstance(problem, InvestigationError) else UNREADABLE
            QMessageBox.warning(self, OPENING_FAILED_TITLE, message)
            self.home_screen.refresh()
            return
        self.stop_layout()
        self.current_investigation = name
        self.investigation_page.show_investigation(investigation)
        self.refresh_overview()
        self.register_search.start(self.collection_settings(name))
        self.review_actions.start(self.collection_settings(name))
        self.header_bar.set_search_enabled(True)
        self.header_bar.breadcrumb.set_trail((*HOME_TRAIL, name))
        self.main_menu_bar.close_investigation_action.setEnabled(True)
        self.main_menu_bar.show_investigation_actions(True)
        self.follow_expandable(self.investigation_page.details_panel.entity_sheet.can_expand())
        self.pages.setCurrentWidget(self.investigation_page)
        self.header_bar.search_field.setFocus()

    def collection_settings(self, name: str) -> CollectionSettings:
        return CollectionSettings(
            self.library, name, self.collection_environment, self.collection_environment.timing
        )

    def start_layout(self, *, again: bool = False) -> None:
        if self.current_investigation is None or self.layout_job is not None:
            return
        job = layout_job(self.collection_settings(self.current_investigation), again=again)
        job.succeeded.connect(self.finish_layout)
        job.failed.connect(self.fail_layout)
        self.layout_job = job
        job.start()

    def lay_out_again(self) -> None:
        self.investigation_page.graph_view.follows_fit = True
        self.stop_layout()
        self.start_layout(again=True)

    def finish_layout(self) -> None:
        job = self.layout_job
        self.layout_job = None
        if job is None:
            return
        job.wait()
        if job.settings.investigation_name == self.current_investigation:
            self.refresh_overview()

    def fail_layout(self, message: str) -> None:
        self.layout_job = None
        self.show_failure(message)

    def stop_layout(self) -> None:
        job = self.layout_job
        self.layout_job = None
        if job is not None:
            job.cancel()
            job.wait()

    def save_moved_positions(self, moved: dict[str, tuple[float, float]]) -> None:
        if self.current_investigation is None:
            return
        job = move_job(self.collection_settings(self.current_investigation), moved)
        job.succeeded.connect(lambda: self.forget_move(job))
        job.cancelled.connect(lambda: self.forget_move(job))
        job.failed.connect(lambda message: self.fail_move(job, message))
        self.move_jobs.append(job)
        job.start()

    def forget_move(self, job: BackgroundJob) -> None:
        job.wait()
        if job in self.move_jobs:
            self.move_jobs.remove(job)

    def fail_move(self, job: BackgroundJob, message: str) -> None:
        self.forget_move(job)
        self.show_failure(message)

    def stop_moves(self) -> None:
        for job in self.move_jobs:
            job.wait()
        self.move_jobs = []

    def show_added_company(self, identifier: str, message: str) -> None:
        self.refresh_overview()
        self.notification_area.notify(message, NotificationKind.SUCCESS)

    def show_failure(self, message: str) -> None:
        self.notification_area.notify(message, NotificationKind.ERROR)

    def refresh_overview(self) -> None:
        if self.current_investigation is None:
            return
        try:
            overview = read_overview(self.library, self.current_investigation)
        except (InvestigationError, sqlite3.DatabaseError) as problem:
            message = str(problem) if isinstance(problem, InvestigationError) else UNREADABLE
            self.show_failure(message)
            return
        self.report = overview.report
        self.investigation_page.show_overview(overview)
        self.show_details(self.investigation_page.selected_entity or "")
        if overview.drawing.needs_layout:
            self.start_layout()

    def show_details(self, identifier: str) -> None:
        if self.current_investigation is None or not identifier:
            self.investigation_page.details_panel.show_details(None)
            return
        try:
            with self.library.open(self.current_investigation) as opened:
                details = entity_details(opened.connection, identifier, self.report)
        except (InvestigationError, sqlite3.DatabaseError) as problem:
            message = str(problem) if isinstance(problem, InvestigationError) else UNREADABLE
            self.show_failure(message)
            return
        self.investigation_page.details_panel.show_details(details)

    def show_raw_response(self, response_identifier: int) -> None:
        if self.current_investigation is None:
            return
        try:
            with self.library.open(self.current_investigation) as opened:
                text = raw_response(opened.connection, response_identifier)
        except (InvestigationError, sqlite3.DatabaseError) as problem:
            message = str(problem) if isinstance(problem, InvestigationError) else UNREADABLE
            self.show_failure(message)
            return
        dialog = RawResponseDialog(response_identifier, text, self)
        dialog.open()

    def focus_search(self) -> None:
        field = self.header_bar.search_field
        if field.isEnabled():
            field.setFocus(Qt.FocusReason.ShortcutFocusReason)
            field.selectAll()

    def follow_expandable(self, expandable: bool) -> None:
        shown = self.current_investigation is not None
        self.main_menu_bar.expand_action.setEnabled(shown and expandable)

    def follow_breadcrumb(self, position: int) -> None:
        if position == 0:
            self.show_home()

    def show_home(self) -> None:
        self.review_actions.stop()
        self.stop_layout()
        self.stop_moves()
        self.register_search.stop()
        self.header_bar.search_field.clear()
        self.header_bar.set_search_enabled(False)
        self.current_investigation = None
        self.main_menu_bar.close_investigation_action.setEnabled(False)
        self.main_menu_bar.show_investigation_actions(False)
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

    def show_shortcuts_dialog(self) -> None:
        if self.shortcuts_dialog is None:
            self.shortcuts_dialog = ShortcutsDialog(shortcut_groups(self.main_menu_bar), self)
        self.shortcuts_dialog.open()

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
        self.review_actions.stop()
        self.stop_layout()
        self.stop_moves()
        self.register_search.stop()
        self.save_geometry()
        super().closeEvent(event)
