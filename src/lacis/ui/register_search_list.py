from typing import override

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lacis.graph.background import (
    BackgroundJob,
    CollectionSettings,
    add_company_job,
    register_search_job,
)
from lacis.graph.register_search import (
    IN_INVESTIGATION_TEXT,
    RegisterSearchResult,
    RegisterSearchResults,
    query_problem,
)
from lacis.storage.responses import ResponseSummary
from lacis.ui import announcements
from lacis.ui.header_bar import SearchField

SEARCH_DELAY_MILLISECONDS = 400
SEARCHING_TEXT = "Recherche dans le registre national…"
NAVIGATION_HINT = "↑ ↓ pour naviguer · Entrée pour ajouter"
ADD_TEXT = "Ajouter"
SHOW_TEXT = "Voir"
ADDING_TEXT = "Ajout…"
RESULTS_ACCESSIBLE_NAME = "Résultats de la recherche"
POPUP_MINIMUM_WIDTH = 560
POPUP_GAP = 6
MAXIMUM_LIST_HEIGHT = 380


def added_message(title: str) -> str:
    return f"{title} a été ajoutée à l'enquête."


def position_message(result: RegisterSearchResult, position: int, count: int) -> str:
    return f"{result.spoken}, {position} sur {count}"


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class SearchResultRow(QFrame):
    chosen = Signal(QFrame)

    def __init__(
        self,
        result: RegisterSearchResult,
        response: ResponseSummary,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.result = result
        self.response = response
        self.setObjectName("searchResult")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.title_label = QLabel(self)
        self.title_label.setProperty("tone", "result-title")
        self.status_label = QLabel(self)
        self.in_investigation_label = QLabel(IN_INVESTIGATION_TEXT, self)
        self.in_investigation_label.setProperty("tone", "badge-outline")
        self.details_label = QLabel(self)
        self.details_label.setProperty("tone", "muted")
        self.details_label.setWordWrap(True)
        self.action_button = QPushButton(self)
        self.action_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action_button.clicked.connect(lambda: self.chosen.emit(self))

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.addWidget(self.title_label)
        title_row.addWidget(self.status_label)
        title_row.addWidget(self.in_investigation_label)
        title_row.addStretch(1)
        text_column = QVBoxLayout()
        text_column.setSpacing(4)
        text_column.addLayout(title_row)
        text_column.addWidget(self.details_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        layout.addLayout(text_column, 1)
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.set_current(False)
        self.show_result(result)

    def show_result(self, result: RegisterSearchResult) -> None:
        self.result = result
        self.title_label.setText(result.title)
        self.status_label.setText(result.status)
        self.status_label.setProperty(
            "tone", "badge-active" if result.company.is_active else "badge-closed"
        )
        repolish(self.status_label)
        self.in_investigation_label.setVisible(result.in_investigation)
        self.details_label.setText(result.details)
        action_text = SHOW_TEXT if result.in_investigation else ADD_TEXT
        self.action_button.setText(action_text)
        self.action_button.setEnabled(True)
        self.action_button.setProperty(
            "variant", "subtle" if result.in_investigation else "primary"
        )
        repolish(self.action_button)
        self.action_button.setAccessibleName(f"{action_text} {result.title}")

    def show_adding(self) -> None:
        self.action_button.setText(ADDING_TEXT)
        self.action_button.setEnabled(False)

    def set_current(self, current: bool) -> None:
        self.setProperty("current", current)
        repolish(self)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.chosen.emit(self)
            return
        super().mouseReleaseEvent(event)


class RegisterSearchPopup(QFrame):
    row_chosen = Signal(QFrame)

    def __init__(self, anchor: QWidget, host: QWidget) -> None:
        super().__init__(host)
        self.anchor = anchor
        self.host = host
        self.rows: list[SearchResultRow] = []
        self.current_index = -1
        self.setObjectName("searchPopup")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAccessibleName(RESULTS_ACCESSIBLE_NAME)
        self.count_label = QLabel(self)
        self.count_label.setProperty("tone", "current")
        self.hint_label = QLabel(NAVIGATION_HINT, self)
        self.hint_label.setProperty("tone", "faint")
        self.message_label = QLabel(self)
        self.message_label.setWordWrap(True)
        self.footer_label = QLabel(self)
        self.footer_label.setProperty("tone", "faint")
        self.footer_label.setWordWrap(True)

        self.list_area = QScrollArea(self)
        self.list_area.setObjectName("searchList")
        self.list_area.setWidgetResizable(True)
        self.list_area.setFrameShape(QFrame.Shape.NoFrame)
        self.list_area.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.list_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        list_content = QWidget(self.list_area)
        list_content.setObjectName("searchListContent")
        self.row_layout = QVBoxLayout(list_content)
        self.row_layout.setContentsMargins(0, 0, 0, 0)
        self.row_layout.setSpacing(0)
        self.row_layout.addStretch(1)
        self.list_area.setWidget(list_content)

        self.head = QWidget(self)
        head = QHBoxLayout(self.head)
        head.setContentsMargins(14, 10, 14, 8)
        head.addWidget(self.count_label)
        head.addStretch(1)
        head.addWidget(self.hint_label)
        self.message_label.setContentsMargins(14, 12, 14, 12)
        self.footer_label.setContentsMargins(14, 8, 14, 10)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(0)
        self.main_layout.addWidget(self.head)
        self.main_layout.addWidget(self.message_label)
        self.main_layout.addWidget(self.list_area)
        self.main_layout.addWidget(self.footer_label)
        self.hide()

    def clear_rows(self) -> None:
        for row in self.rows:
            self.row_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        self.rows = []
        self.current_index = -1

    def show_message(self, message: str, *, problem: bool = False) -> None:
        self.clear_rows()
        self.head.hide()
        self.footer_label.hide()
        self.list_area.hide()
        self.show_notice(message, problem=problem)
        self.reveal()

    def show_notice(self, message: str, *, problem: bool = False) -> None:
        self.message_label.setText(message)
        self.message_label.setProperty("tone", "problem" if problem else "muted")
        repolish(self.message_label)
        self.message_label.setVisible(bool(message))

    def show_results(self, results: RegisterSearchResults) -> None:
        self.clear_rows()
        self.count_label.setText(results.count_text)
        self.head.show()
        self.hint_label.setVisible(bool(results.results))
        self.show_notice("")
        for result in results.results:
            row = SearchResultRow(result, results.page.response, self.list_area.widget())
            row.chosen.connect(self.row_chosen)
            self.row_layout.insertWidget(len(self.rows), row)
            self.rows.append(row)
        self.list_area.setVisible(bool(self.rows))
        self.footer_label.setText(results.truncation_text)
        self.footer_label.setVisible(bool(results.truncation_text))
        if self.rows:
            self.select(0)
        self.reveal()

    def select(self, index: int) -> SearchResultRow:
        if 0 <= self.current_index < len(self.rows):
            self.rows[self.current_index].set_current(False)
        self.current_index = index
        row = self.rows[index]
        row.set_current(True)
        self.list_area.ensureWidgetVisible(row, 0, 0)
        return row

    def move_current(self, step: int) -> SearchResultRow | None:
        if not self.rows:
            return None
        index = min(max(self.current_index + step, 0), len(self.rows) - 1)
        return self.select(index)

    def current_row(self) -> SearchResultRow | None:
        if 0 <= self.current_index < len(self.rows):
            return self.rows[self.current_index]
        return None

    def reveal(self) -> None:
        top_left = self.anchor.mapTo(self.host, QPoint(0, self.anchor.height() + POPUP_GAP))
        width = max(self.anchor.width(), POPUP_MINIMUM_WIDTH)
        left = min(top_left.x(), max(self.host.width() - width - POPUP_GAP, 0))
        for row in self.rows:
            row.show()
        row_width = width - 2
        rows_height = sum(row.heightForWidth(row_width) for row in self.rows)
        self.list_area.setFixedHeight(min(rows_height, MAXIMUM_LIST_HEIGHT))
        self.main_layout.activate()
        height = self.heightForWidth(width) if self.hasHeightForWidth() else 0
        self.setGeometry(left, top_left.y(), width, height or self.sizeHint().height())
        self.show()
        self.raise_()


class RegisterSearch(QObject):
    company_added = Signal(str)
    company_shown = Signal(str, str)

    def __init__(
        self, field: SearchField, popup: RegisterSearchPopup, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.field = field
        self.popup = popup
        self.settings: CollectionSettings | None = None
        self.search_job: BackgroundJob | None = None
        self.adding_jobs: dict[BackgroundJob, SearchResultRow] = {}
        self.started_jobs: list[BackgroundJob] = []
        self.delay = QTimer(self)
        self.delay.setSingleShot(True)
        self.delay.setInterval(SEARCH_DELAY_MILLISECONDS)
        self.delay.timeout.connect(self.search_now)
        field.textEdited.connect(self.schedule_search)
        field.moved.connect(self.move)
        field.chosen.connect(self.choose_current)
        field.closed.connect(self.close)
        field.left.connect(self.close)
        popup.row_chosen.connect(self.choose)

    def start(self, settings: CollectionSettings) -> None:
        self.stop()
        self.settings = settings

    def stop(self) -> None:
        self.delay.stop()
        self.settings = None
        self.search_job = None
        self.adding_jobs = {}
        for job in self.started_jobs:
            job.cancel()
        for job in self.started_jobs:
            job.wait()
        self.started_jobs = []
        self.close()

    def close(self) -> None:
        self.popup.hide()

    def schedule_search(self, text: str) -> None:
        if query_problem(text):
            self.delay.stop()
            self.cancel_search()
            self.close()
            return
        self.delay.start()

    def cancel_search(self) -> None:
        if self.search_job is not None:
            self.search_job.cancel()
            self.search_job = None

    def run(self, job: BackgroundJob) -> None:
        self.started_jobs = [started for started in self.started_jobs if started.is_running()]
        self.started_jobs.append(job)
        job.start()

    def search_now(self) -> None:
        self.delay.stop()
        if self.settings is None:
            return
        problem = query_problem(self.field.text())
        if problem:
            self.cancel_search()
            self.popup.show_message(problem, problem=True)
            announcements.announce(self.field, problem)
            return
        self.cancel_search()
        job = register_search_job(self.settings, self.field.text())
        job.succeeded.connect(self.show_results)
        job.failed.connect(self.show_search_failure)
        self.search_job = job
        self.popup.show_message(SEARCHING_TEXT)
        self.run(job)

    def show_results(self, results: RegisterSearchResults) -> None:
        if self.search_job is None or self.sender() is not self.search_job:
            return
        self.search_job = None
        self.popup.show_results(results)
        announcements.announce(self.field, results.announcement, announcements.POLITE)

    def show_search_failure(self, message: str) -> None:
        if self.search_job is None or self.sender() is not self.search_job:
            return
        self.search_job = None
        self.popup.show_message(message, problem=True)
        announcements.announce(self.field, message)

    def choose(self, row: SearchResultRow) -> None:
        result = row.result
        if result.in_investigation:
            self.close()
            self.company_shown.emit(result.identifier, result.title)
            return
        if self.settings is None or row in self.adding_jobs.values():
            return
        job = add_company_job(self.settings, result.company, row.response)
        job.succeeded.connect(self.show_added)
        job.failed.connect(self.show_adding_failure)
        self.adding_jobs[job] = row
        row.show_adding()
        self.run(job)

    def finished_row(self) -> SearchResultRow | None:
        sender = self.sender()
        row = self.adding_jobs.pop(sender, None) if isinstance(sender, BackgroundJob) else None
        return row if row in self.popup.rows else None

    def show_added(self, changes: object) -> None:
        row = self.finished_row()
        if row is None:
            return
        row.show_result(row.result.added())
        self.popup.show_notice("")
        announcements.announce(self.field, added_message(row.result.title), announcements.POLITE)
        self.company_added.emit(row.result.identifier)

    def show_adding_failure(self, message: str) -> None:
        row = self.finished_row()
        if row is None:
            return
        row.show_result(row.result)
        self.popup.show_notice(message, problem=True)
        announcements.announce(self.field, message)

    def move(self, step: int) -> None:
        if not self.popup.isVisible():
            if not query_problem(self.field.text()):
                self.search_now()
            return
        row = self.popup.move_current(step)
        if row is None:
            return
        position = self.popup.current_index + 1
        message = position_message(row.result, position, len(self.popup.rows))
        announcements.announce(self.field, message, announcements.POLITE)

    def choose_current(self) -> None:
        current_row = self.popup.current_row()
        if self.popup.isVisible() and current_row is not None and not self.delay.isActive():
            self.choose(current_row)
            return
        self.search_now()
