from typing import override

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QFocusEvent, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.storage.errors import InvestigationError
from lacis.storage.investigations import InvestigationLibrary, InvestigationSummary
from lacis.ui.header_bar import IconMark, create_icon_button
from lacis.ui.investigation_form import (
    CANCEL_TEXT,
    EditInvestigationDialog,
    NewInvestigationPanel,
)

HOME_TITLE = "Enquêtes"
HOME_SUBTITLE = (
    "Chaque enquête est une base SQLite locale, avec ses preuves et son journal de collecte."
)
NEW_INVESTIGATION_TEXT = "Nouvelle enquête"
DATA_NOTICE = (
    "Données : API Recherche d'entreprises (DINUM) et BODACC (DILA), Licence Ouverte 2.0. "
    "Les noms et mois de naissance des dirigeants sont des données personnelles : gardez vos "
    "enquêtes locales et proportionnées. Un lien dans le graphe est une piste, pas une preuve."
)
EMPTY_STATE_TITLE = "Aucune enquête pour l'instant"
EMPTY_STATE_TEXT = (
    "Une enquête rassemble les entreprises, les dirigeants et les adresses que vous suivez, "
    "avec la source de chaque information. Commencez par en créer une."
)
CREATE_FIRST_INVESTIGATION_TEXT = "Créer une première enquête"
EMPTY_STATE_TEXT_WIDTH = 600
CONTENT_MAXIMUM_WIDTH = 1040
CARD_COLUMNS = 2
CARD_ICON_SIZE = QSize(14, 14)
CARD_SPACING = 14
OPEN_KEYS = frozenset({Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space})
FIRST_PLURAL = 2
ACTIONS_TOOLTIP = "Actions"
EDIT_ACTION_TEXT = "&Modifier le nom ou la question…"
DELETE_ACTION_TEXT = "&Supprimer…"
DELETION_TITLE = "Supprimer l'enquête"
DELETION_DETAILS = (
    "Elle sera placée dans la corbeille du système avec ses preuves et son journal de "
    "collecte : vous pourrez l'en sortir tant que la corbeille n'est pas vidée."
)
DELETE_BUTTON_TEXT = "Placer dans la corbeille"
DELETION_FAILED_TITLE = "Impossible de supprimer l'enquête"


def counted(count: int, singular: str, plural: str) -> str:
    return f"<b>{count}</b> {singular if count < FIRST_PLURAL else plural}"


def modification_text(summary: InvestigationSummary) -> str:
    return f"Modifiée le {summary.modified_at.astimezone().strftime('%d/%m/%Y')}"


def deletion_question(name: str) -> str:
    return f"Supprimer l'enquête « {name} » ?"


def actions_name(name: str) -> str:
    return f"Actions de l'enquête {name}"


class InvestigationCard(QFrame):
    open_requested = Signal(str)
    edit_requested = Signal(str)
    deletion_requested = Signal(str)
    focused = Signal(QWidget)

    def __init__(
        self,
        summary: InvestigationSummary,
        icon_factory: IconFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.summary = summary
        self.setObjectName("investigationCard")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        top_row.addWidget(IconMark(icon_factory.icon("graph"), CARD_ICON_SIZE, parent=self))
        self.name_label = QLabel(summary.name, self)
        self.name_label.setProperty("tone", "card-title")
        top_row.addWidget(self.name_label)
        top_row.addStretch(1)
        self.more_button = create_icon_button(
            icon_factory.icon("more"), actions_name(summary.name), ACTIONS_TOOLTIP, self
        )
        self.actions_menu = QMenu(self.more_button)
        self.edit_action = self.actions_menu.addAction(EDIT_ACTION_TEXT)
        self.edit_action.setEnabled(not summary.problem)
        self.edit_action.triggered.connect(lambda: self.edit_requested.emit(summary.name))
        self.actions_menu.addSeparator()
        self.delete_action = self.actions_menu.addAction(DELETE_ACTION_TEXT)
        self.delete_action.triggered.connect(lambda: self.deletion_requested.emit(summary.name))
        self.more_button.setMenu(self.actions_menu)
        top_row.addWidget(self.more_button)
        layout.addLayout(top_row)

        self.question_label = QLabel(summary.problem or summary.question, self)
        self.question_label.setWordWrap(True)
        self.question_label.setProperty("tone", "muted" if summary.problem else "body")
        layout.addWidget(self.question_label)

        foot_row = QHBoxLayout()
        foot_row.setSpacing(14)
        self.entity_count_label = self.foot_label(
            counted(summary.entity_count, "entité", "entités")
        )
        self.link_count_label = self.foot_label(counted(summary.link_count, "lien", "liens"))
        self.modification_label = self.foot_label(modification_text(summary))
        foot_row.addWidget(self.entity_count_label)
        foot_row.addWidget(self.link_count_label)
        foot_row.addStretch(1)
        foot_row.addWidget(self.modification_label)
        layout.addLayout(foot_row)

        self.setAccessibleName(f"Enquête {summary.name}")
        self.setAccessibleDescription(self.description())

    def foot_label(self, text: str) -> QLabel:
        label = QLabel(text, self)
        label.setProperty("tone", "muted")
        return label

    def description(self) -> str:
        counts = (
            (
                f"{self.entity_count_label.text()}, {self.link_count_label.text()}, "
                f"{self.modification_label.text()}"
            )
            .replace("<b>", "")
            .replace("</b>", "")
        )
        return f"{self.question_label.text()} {counts}."

    @override
    def focusInEvent(self, event: QFocusEvent) -> None:
        super().focusInEvent(event)
        self.focused.emit(self)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if Qt.Key(event.key()) in OPEN_KEYS:
            self.open_requested.emit(self.summary.name)
            return
        super().keyPressEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.open_requested.emit(self.summary.name)
            return
        super().mouseReleaseEvent(event)


class HomeScreen(QScrollArea):
    investigation_opened = Signal(str)

    def __init__(
        self,
        library: InvestigationLibrary,
        icon_factory: IconFactory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.icon_factory = icon_factory
        self.cards: list[InvestigationCard] = []
        self.edit_dialog: EditInvestigationDialog | None = None
        self.setObjectName("homeScreen")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        page = QWidget(self)
        page.setObjectName("homePage")
        page_layout = QHBoxLayout(page)
        page_layout.setContentsMargins(24, 32, 24, 32)
        content = QWidget(page)
        content.setMaximumWidth(CONTENT_MAXIMUM_WIDTH)
        page_layout.addStretch(1)
        page_layout.addWidget(content, 100)
        page_layout.addStretch(1)

        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(18)
        self.content_layout.addLayout(self.create_head())
        self.new_investigation_panel = NewInvestigationPanel(library, content)
        self.new_investigation_panel.created.connect(self.show_created_investigation)
        self.new_investigation_panel.cancelled.connect(self.finish_creation)
        self.content_layout.addWidget(self.new_investigation_panel)
        self.empty_state = self.create_empty_state(content)
        self.content_layout.addWidget(self.empty_state)
        self.card_grid = QGridLayout()
        self.card_grid.setSpacing(CARD_SPACING)
        self.content_layout.addLayout(self.card_grid)
        self.notice_label = QLabel(DATA_NOTICE, content)
        self.notice_label.setWordWrap(True)
        self.notice_label.setProperty("tone", "faint")
        self.notice_label.setMaximumWidth(760)
        self.content_layout.addSpacing(10)
        self.content_layout.addWidget(self.notice_label)
        self.content_layout.addStretch(1)
        self.setWidget(page)
        self.refresh()

    def create_head(self) -> QHBoxLayout:
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self.title_label = QLabel(HOME_TITLE)
        self.title_label.setProperty("tone", "page-title")
        self.title_label.setAccessibleName(HOME_TITLE)
        subtitle = QLabel(HOME_SUBTITLE)
        subtitle.setProperty("tone", "subtitle")
        titles.addWidget(self.title_label)
        titles.addWidget(subtitle)
        head.addLayout(titles, 1)
        self.new_investigation_button = QPushButton(NEW_INVESTIGATION_TEXT)
        self.new_investigation_button.setProperty("variant", "primary")
        self.new_investigation_button.setIcon(self.icon_factory.icon_on_accent("plus"))
        self.new_investigation_button.clicked.connect(self.start_creation)
        head.addWidget(self.new_investigation_button, 0, Qt.AlignmentFlag.AlignBottom)
        return head

    def create_empty_state(self, parent: QWidget) -> QFrame:
        empty_state = QFrame(parent)
        empty_state.setObjectName("emptyState")
        layout = QVBoxLayout(empty_state)
        layout.setContentsMargins(24, 28, 24, 28)
        layout.setSpacing(8)
        title = QLabel(EMPTY_STATE_TITLE, empty_state)
        title.setProperty("tone", "card-title")
        text = QLabel(EMPTY_STATE_TEXT, empty_state)
        text.setWordWrap(True)
        text.setProperty("tone", "subtitle")
        self.create_first_button = QPushButton(CREATE_FIRST_INVESTIGATION_TEXT, empty_state)
        self.create_first_button.setProperty("variant", "primary")
        self.create_first_button.setIcon(self.icon_factory.icon_on_accent("plus"))
        self.create_first_button.clicked.connect(self.start_creation)
        layout.addWidget(title, 0, Qt.AlignmentFlag.AlignHCenter)
        text.setFixedWidth(EMPTY_STATE_TEXT_WIDTH)
        layout.addWidget(text, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(8)
        layout.addWidget(self.create_first_button, 0, Qt.AlignmentFlag.AlignHCenter)
        text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        return empty_state

    def refresh(self) -> None:
        for card in self.cards:
            self.card_grid.removeWidget(card)
            card.hide()
            card.deleteLater()
        self.cards = []
        for position, summary in enumerate(self.library.summaries()):
            card = InvestigationCard(summary, self.icon_factory)
            card.open_requested.connect(self.investigation_opened)
            card.edit_requested.connect(self.edit_investigation)
            card.deletion_requested.connect(self.delete_investigation)
            card.focused.connect(self.ensureWidgetVisible)
            row, column = divmod(position, CARD_COLUMNS)
            self.card_grid.addWidget(card, row, column)
            if self.isVisible():
                card.show()
            self.cards.append(card)
        for column in range(CARD_COLUMNS):
            self.card_grid.setColumnStretch(column, 1)
        self.update_empty_state()

    def update_empty_state(self) -> None:
        self.empty_state.setVisible(
            not self.cards and not self.new_investigation_panel.isVisibleTo(self)
        )

    def start_creation(self) -> None:
        self.new_investigation_panel.start()
        self.update_empty_state()
        self.ensureWidgetVisible(self.new_investigation_panel)

    def finish_creation(self) -> None:
        self.update_empty_state()
        self.focus_creation_button()

    def focus_creation_button(self) -> None:
        if self.empty_state.isVisibleTo(self):
            self.create_first_button.setFocus()
            return
        self.new_investigation_button.setFocus()

    def card_named(self, name: str) -> InvestigationCard:
        return next(card for card in self.cards if card.summary.name == name)

    def edit_investigation(self, name: str) -> None:
        summary = self.card_named(name).summary
        self.edit_dialog = EditInvestigationDialog(
            self.library, summary.name, summary.question, self
        )
        self.edit_dialog.saved.connect(self.show_saved_investigation)
        self.edit_dialog.open()

    def show_saved_investigation(self, name: str) -> None:
        self.refresh()
        self.card_named(name).setFocus()

    def confirm_deletion(self, name: str) -> bool:
        box = QMessageBox(
            QMessageBox.Icon.Warning,
            DELETION_TITLE,
            deletion_question(name),
            QMessageBox.StandardButton.NoButton,
            self,
        )
        box.setInformativeText(DELETION_DETAILS)
        delete_button = box.addButton(DELETE_BUTTON_TEXT, QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(CANCEL_TEXT, QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_button)
        box.setEscapeButton(cancel_button)
        box.exec()
        return box.clickedButton() is delete_button

    def delete_investigation(self, name: str) -> None:
        if not self.confirm_deletion(name):
            return
        try:
            self.library.delete(name)
        except InvestigationError as problem:
            QMessageBox.warning(self, DELETION_FAILED_TITLE, str(problem))
        self.refresh()
        self.focus_creation_button()

    def show_created_investigation(self, name: str) -> None:
        self.refresh()
        self.investigation_opened.emit(name)
