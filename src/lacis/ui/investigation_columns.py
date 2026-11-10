from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from lacis.overview import InvestigationOverview
from lacis.signals.facts import counted

QUEUE_TITLE = "À examiner"
QUEUE_EMPTY_TEXT = "Les signaux, les homonymes et les pistes à examiner s'afficheront ici."
GRAPH_EMPTY_TEXT = "Le graphe de l'enquête s'affichera ici."
DETAILS_ACCESSIBLE_NAME = "Panneau de détails"
QUEUE_MINIMUM_WIDTH = 240
GRAPH_MINIMUM_WIDTH = 320
DETAILS_MINIMUM_WIDTH = 340
DETAILS_TABS = (
    ("Fiche", "La fiche de l'entité sélectionnée s'affichera ici."),
    ("Signaux", "Les signaux d'alerte de l'enquête s'afficheront ici."),
    ("Entités", "La liste des entités de l'enquête s'affichera ici."),
    ("Journal", "Le journal de collecte de l'enquête s'affichera ici."),
)


def queue_summary(overview: InvestigationOverview) -> str:
    signals = (
        "signaux indisponibles"
        if overview.signals is None
        else counted(overview.signals, "signal", "signaux")
    )
    homonyms = counted(overview.pending_homonyms, "homonyme", "homonymes")
    leads = counted(overview.leads, "piste", "pistes")
    return f"{signals}, {homonyms}, {leads}"


def placeholder(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setProperty("tone", "faint")
    label.setWordWrap(True)
    return label


class QueueColumn(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("queueColumn")
        self.setMinimumWidth(QUEUE_MINIMUM_WIDTH)
        self.title_label = QLabel(QUEUE_TITLE.upper(), self)
        self.title_label.setProperty("tone", "column-title")
        self.title_label.setAccessibleName(QUEUE_TITLE)
        self.summary_label = QLabel(self)
        self.summary_label.setProperty("tone", "muted")
        self.head = QFrame(self)
        self.head.setObjectName("columnHead")
        self.head_layout = QHBoxLayout(self.head)
        self.head_layout.setContentsMargins(14, 14, 10, 12)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(self.title_label)
        titles.addWidget(self.summary_label)
        self.head_layout.addLayout(titles, 1)
        self.empty_label = placeholder(QUEUE_EMPTY_TEXT, self)
        body = QVBoxLayout()
        body.setContentsMargins(14, 14, 14, 14)
        body.addWidget(self.empty_label)
        body.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.head)
        layout.addLayout(body, 1)

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.summary_label.setText(queue_summary(overview))


class GraphArea(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphArea")
        self.setMinimumWidth(GRAPH_MINIMUM_WIDTH)
        self.empty_label = placeholder(GRAPH_EMPTY_TEXT, self)
        self.empty_label.setWordWrap(False)
        self.graph_layout = QVBoxLayout(self)
        self.graph_layout.addStretch(1)
        self.graph_layout.addWidget(self.empty_label, 0, Qt.AlignmentFlag.AlignCenter)


class DetailsPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("detailsPanel")
        self.setMinimumWidth(DETAILS_MINIMUM_WIDTH)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("detailsTabs")
        self.tabs.setAccessibleName(DETAILS_ACCESSIBLE_NAME)
        self.tabs.setDocumentMode(True)
        for title, empty_text in DETAILS_TABS:
            page = QWidget(self.tabs)
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(16, 16, 16, 16)
            page_layout.addWidget(placeholder(empty_text, page))
            page_layout.addStretch(1)
            self.tabs.addTab(page, title)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabs)
