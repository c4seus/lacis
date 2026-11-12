from collections.abc import Callable
from typing import override

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication, QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from lacis.design.icons import IconFactory
from lacis.details import EntityDetails, LinkLine, Reference, SignalCard, SourceLine
from lacis.graph.expansion import MAXIMUM_DEPTH, MINIMUM_DEPTH
from lacis.signals.facts import counted
from lacis.ui.flow_layout import FlowLayout
from lacis.ui.graph_legend import KindSwatch
from lacis.ui.notice_timeline import NoticeTimeline

EMPTY_TEXT = "La fiche de l'entité sélectionnée s'affichera ici."
SHEET_ACCESSIBLE_NAME = "Fiche de l'entité"
EXPAND_TEXT = "Étendre"
EXPAND_AGAIN_TEXT = "Étendre à nouveau"
DEPTH_TEXT = "Profondeur {depth}"
DEPTH_MENU_ACCESSIBLE_NAME = "Choisir la profondeur d'extension"
DIRECTORY_TEXT = "Annuaire"
DIRECTORY_TOOLTIP = "Ouvrir la fiche dans l'Annuaire des entreprises"
SIGNALS_TITLE = "Signaux d'alerte"
NOTICES_TITLE = "Annonces BODACC"
REFRESH_NOTICES_TEXT = "Rafraîchir"
LINKS_TITLE = "Liens"
SOURCES_TITLE = "Provenance"
RAW_RESPONSE_TEXT = "Réponse brute"
FINGERPRINT_PREFIX = "Empreinte SHA-256 "
COPIED_MESSAGE = "« {value} » copié dans le presse-papiers."
ACTIVATING_KEYS = {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}
LINK_ROLE_WIDTH = 110


def wrapped_label(text: str, tone: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", tone)
    label.setWordWrap(True)
    label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
    return label


def badge(text: str, tone: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", f"badge-{tone}")
    return label


class ReferenceChip(QFrame):
    chosen = Signal(str)

    def __init__(self, reference: Reference, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reference = reference
        self.setObjectName("referenceChip")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(f"Sélectionner {reference.label}")
        self.label = QLabel(reference.label, self)
        self.label.setProperty("tone", "chip")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(6)
        self.swatch_layout = layout
        layout.addWidget(self.label)

    def add_swatch(self, swatch: QWidget) -> None:
        self.swatch_layout.insertWidget(0, swatch)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() is Qt.MouseButton.LeftButton:
            self.chosen.emit(self.reference.identifier)
            event.accept()
            return
        super().mousePressEvent(event)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in ACTIVATING_KEYS:
            self.chosen.emit(self.reference.identifier)
            event.accept()
            return
        super().keyPressEvent(event)


class SectionTitle(QWidget):
    def __init__(
        self,
        title: str,
        count: str,
        parent: QWidget | None = None,
        action: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.title_label = QLabel(title.upper(), self)
        self.title_label.setProperty("tone", "section-title")
        self.count_label = QLabel(count, self)
        self.count_label.setProperty("tone", "section-count")
        rule = QFrame(self)
        rule.setObjectName("sectionRule")
        rule.setFixedHeight(1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 16, 0, 6)
        layout.setSpacing(8)
        layout.addWidget(self.title_label)
        layout.addWidget(self.count_label)
        layout.addWidget(rule, 1, Qt.AlignmentFlag.AlignVCenter)
        if action is not None:
            action.setParent(self)
            layout.addWidget(action)
        self.setAccessibleName(f"{title}, {count}")


class SignalCardView(QFrame):
    def __init__(self, card: SignalCard, sheet: "EntitySheet") -> None:
        super().__init__(sheet.content)
        self.card = card
        self.setObjectName("signalCard")
        self.setProperty("severity", card.severity.value)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.severity_badge = badge(card.severity.label, card.severity.value, self)
        self.title_label = QLabel(card.title, self)
        self.title_label.setProperty("tone", "card-heading")
        self.score_label = QLabel(card.written_score, self)
        self.score_label.setProperty("tone", "queue-score")
        head.addWidget(self.severity_badge)
        head.addWidget(self.title_label, 1)
        head.addWidget(self.score_label)
        self.explanation_label = wrapped_label(card.explanation, "body", self)
        references = QWidget(self)
        references_layout = FlowLayout(references)
        self.chips = [sheet.reference_chip(reference, references) for reference in card.references]
        for chip in self.chips:
            references_layout.addWidget(chip)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        layout.addLayout(head)
        layout.addWidget(self.explanation_label)
        layout.addWidget(references)
        self.setAccessibleName(f"{card.title}, sévérité {card.severity.label.lower()}")


class LinkRow(QWidget):
    def __init__(self, line: LinkLine, sheet: "EntitySheet") -> None:
        super().__init__(sheet.content)
        self.line = line
        self.role_label = QLabel(line.role, self)
        self.role_label.setProperty("tone", "muted")
        self.role_label.setFixedWidth(LINK_ROLE_WIDTH)
        self.role_label.setWordWrap(True)
        self.chip = sheet.reference_chip(line.reference, self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(8)
        layout.addWidget(self.role_label)
        layout.addWidget(self.chip)
        layout.addStretch(1)
        if line.closed:
            layout.addWidget(badge("Fermé", "closed", self))


class SourceRow(QFrame):
    raw_requested = Signal(int)

    def __init__(self, line: SourceLine, parent: QWidget) -> None:
        super().__init__(parent)
        self.line = line
        self.setObjectName("sourceRow")
        self.name_label = QLabel(line.source_name, self)
        self.name_label.setProperty("tone", "card-heading")
        self.date_label = QLabel(line.written_date, self)
        self.date_label.setProperty("tone", "muted")
        self.fingerprint_label = QLabel(f"{FINGERPRINT_PREFIX}{line.short_fingerprint}", self)
        self.fingerprint_label.setProperty("tone", "fingerprint")
        self.fingerprint_label.setToolTip(line.fingerprint)
        self.fingerprint_label.setAccessibleName(f"{FINGERPRINT_PREFIX}{line.fingerprint}")
        self.fingerprint_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.raw_button = QPushButton(RAW_RESPONSE_TEXT, self)
        self.raw_button.setProperty("compact", True)
        self.raw_button.setAccessibleName(
            f"{RAW_RESPONSE_TEXT} {line.source_name} du {line.written_date}"
        )
        self.raw_button.clicked.connect(lambda: self.raw_requested.emit(line.response_identifier))
        first = QHBoxLayout()
        first.setSpacing(8)
        first.addWidget(self.name_label)
        first.addWidget(self.date_label, 1)
        first.addWidget(self.raw_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(2)
        layout.addLayout(first)
        layout.addWidget(self.fingerprint_label)


class EntitySheet(QScrollArea):
    entity_chosen = Signal(str)
    expansion_requested = Signal(str, str, int, bool)
    raw_requested = Signal(int)
    copied = Signal(str)
    notices_refresh_requested = Signal(str, str)

    def __init__(
        self,
        icon_factory: IconFactory,
        parent: QWidget | None = None,
        open_url: Callable[[QUrl], object] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.icon_factory = icon_factory
        self.open_url = open_url
        self.setObjectName("entitySheet")
        self.setAccessibleName(SHEET_ACCESSIBLE_NAME)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details: EntityDetails | None = None
        self.running: set[str] = set()
        self.timeline: NoticeTimeline | None = None
        self.refresh_button: QPushButton | None = None
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.chips: list[ReferenceChip] = []
        self.signal_cards: list[SignalCardView] = []
        self.link_rows: list[LinkRow] = []
        self.source_rows: list[SourceRow] = []
        self.section_titles: list[SectionTitle] = []
        self.show_details(None)

    def reference_chip(self, reference: Reference, parent: QWidget) -> ReferenceChip:
        chip = ReferenceChip(reference, parent)
        chip.add_swatch(KindSwatch(reference.kind, self.icon_factory.colours_provider, chip))
        chip.chosen.connect(self.entity_chosen)
        self.chips.append(chip)
        return chip

    def show_details(self, details: EntityDetails | None) -> None:
        self.details = details
        previous = self.takeWidget()
        if previous is not None:
            previous.deleteLater()
        self.content = QWidget()
        self.content.setObjectName("entitySheetContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(16, 16, 16, 16)
        self.content_layout.setSpacing(4)
        self.chips = []
        self.signal_cards = []
        self.link_rows = []
        self.source_rows = []
        self.section_titles = []
        self.timeline = None
        self.refresh_button = None
        if details is None:
            self.empty_label = wrapped_label(EMPTY_TEXT, "faint", self.content)
            self.content_layout.addWidget(self.empty_label)
        else:
            self.add_head(details)
            self.add_signals(details)
            self.add_notices(details)
            self.add_links(details)
            self.add_sources(details)
        self.content_layout.addStretch(1)
        self.setWidget(self.content)
        self.show_running(self.running)

    def add_head(self, details: EntityDetails) -> None:
        kicker = QHBoxLayout()
        kicker.setSpacing(6)
        kind = QFrame(self.content)
        kind.setObjectName("kindBadge")
        kind_layout = QHBoxLayout(kind)
        kind_layout.setContentsMargins(7, 1, 7, 1)
        kind_layout.setSpacing(5)
        kind_layout.addWidget(KindSwatch(details.kind, self.icon_factory.colours_provider, kind))
        self.kind_label = QLabel(details.kind_label, kind)
        self.kind_label.setProperty("tone", "badge-text")
        kind_layout.addWidget(self.kind_label)
        kicker.addWidget(kind)
        self.badge_labels = [
            badge(item.text, item.tone.value, self.content) for item in details.badges
        ]
        for label in self.badge_labels:
            kicker.addWidget(label)
        kicker.addStretch(1)
        self.content_layout.addLayout(kicker)
        self.name_label = wrapped_label(details.name, "heading", self.content)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.content_layout.addWidget(self.name_label)
        self.facts = QWidget(self.content)
        facts_layout = FlowLayout(self.facts, horizontal_spacing=12, vertical_spacing=2)
        self.fact_labels = []
        for fact in details.facts:
            label = QLabel(fact, self.facts)
            label.setProperty("tone", "muted")
            self.fact_labels.append(label)
            facts_layout.addWidget(label)
        self.facts.setVisible(bool(details.facts))
        self.content_layout.addWidget(self.facts)
        self.add_actions(details)
        self.expanded_label = wrapped_label(details.expanded_on, "faint", self.content)
        self.expanded_label.setVisible(details.expanded)
        self.content_layout.addWidget(self.expanded_label)

    def add_actions(self, details: EntityDetails) -> None:
        actions = QHBoxLayout()
        actions.setContentsMargins(0, 10, 0, 2)
        actions.setSpacing(6)
        self.expand_button = QToolButton(self.content)
        self.expand_button.setObjectName("expandButton")
        self.expand_button.setText(EXPAND_AGAIN_TEXT if details.expanded else EXPAND_TEXT)
        self.expand_button.setAccessibleName(self.expand_button.text())
        self.expand_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.expand_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.depth_menu = QMenu(self.expand_button)
        self.depth_menu.setAccessibleName(DEPTH_MENU_ACCESSIBLE_NAME)
        for depth in range(MINIMUM_DEPTH, MAXIMUM_DEPTH + 1):
            action = self.depth_menu.addAction(DEPTH_TEXT.format(depth=depth))
            action.triggered.connect(lambda checked=False, chosen=depth: self.expand(chosen))
        self.expand_button.setMenu(self.depth_menu)
        self.expand_button.clicked.connect(lambda: self.expand(MINIMUM_DEPTH))
        self.expand_button.setVisible(details.expandable)
        self.directory_button = QPushButton(
            self.icon_factory.icon("external"), DIRECTORY_TEXT, self.content
        )
        self.directory_button.setProperty("compact", True)
        self.directory_button.setToolTip(DIRECTORY_TOOLTIP)
        self.directory_button.setVisible(bool(details.directory_url))
        self.directory_button.clicked.connect(self.open_directory)
        self.copy_button = QPushButton(
            self.icon_factory.icon("copy"), details.copy_label, self.content
        )
        self.copy_button.setProperty("compact", True)
        self.copy_button.setProperty("variant", "subtle")
        self.copy_button.clicked.connect(self.copy)
        for widget in (self.expand_button, self.directory_button, self.copy_button):
            actions.addWidget(widget)
        actions.addStretch(1)
        self.content_layout.addLayout(actions)

    def add_section_title(self, title: str, count: str) -> None:
        section_title = SectionTitle(title, count, self.content)
        self.section_titles.append(section_title)
        self.content_layout.addWidget(section_title)

    def add_signals(self, details: EntityDetails) -> None:
        if not details.signals:
            return
        self.add_section_title(SIGNALS_TITLE, str(len(details.signals)))
        for card in details.signals:
            view = SignalCardView(card, self)
            self.signal_cards.append(view)
            self.content_layout.addWidget(view)

    def add_notices(self, details: EntityDetails) -> None:
        if not details.has_notices:
            return
        self.refresh_button = QPushButton(
            self.icon_factory.icon("refresh"), REFRESH_NOTICES_TEXT, self.content
        )
        self.refresh_button.setProperty("variant", "link")
        self.refresh_button.setProperty("compact", True)
        self.refresh_button.setAccessibleName(f"Rafraîchir les annonces de {details.name}")
        self.refresh_button.clicked.connect(self.refresh_notices)
        section_title = SectionTitle(
            NOTICES_TITLE, str(len(details.notices)), self.content, self.refresh_button
        )
        self.section_titles.append(section_title)
        self.content_layout.addWidget(section_title)
        self.timeline = NoticeTimeline(
            details.notices, self.icon_factory.colours_provider, self.content
        )
        self.timeline.link_requested.connect(lambda url: self.open_url(QUrl(url)))
        self.timeline.raw_requested.connect(self.raw_requested)
        self.content_layout.addWidget(self.timeline)

    def refresh_notices(self) -> None:
        if self.details is not None:
            self.notices_refresh_requested.emit(self.details.identifier, self.details.name)

    def show_running(self, running: set[str]) -> None:
        self.running = set(running)
        busy = self.details is not None and self.details.identifier in self.running
        if self.details is not None:
            self.expand_button.setEnabled(not busy)
        if self.refresh_button is not None:
            self.refresh_button.setEnabled(not busy)

    def add_links(self, details: EntityDetails) -> None:
        if not details.links:
            return
        self.add_section_title(LINKS_TITLE, str(len(details.links)))
        for line in details.links:
            row = LinkRow(line, self)
            self.link_rows.append(row)
            self.content_layout.addWidget(row)

    def add_sources(self, details: EntityDetails) -> None:
        if not details.sources:
            return
        self.add_section_title(SOURCES_TITLE, counted(len(details.sources), "réponse", "réponses"))
        for line in details.sources:
            row = SourceRow(line, self.content)
            row.raw_requested.connect(self.raw_requested)
            self.source_rows.append(row)
            self.content_layout.addWidget(row)

    def expand(self, depth: int) -> None:
        if self.details is None:
            return
        self.expansion_requested.emit(
            self.details.identifier, self.details.name, depth, self.details.expanded
        )

    def open_directory(self) -> None:
        if self.details is not None and self.details.directory_url:
            self.open_url(QUrl(self.details.directory_url))

    def copy(self) -> None:
        if self.details is None:
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setText(self.details.copy_value)
        self.copied.emit(COPIED_MESSAGE.format(value=self.details.copy_value))
