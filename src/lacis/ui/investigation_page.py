from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lacis.overview import InvestigationOverview
from lacis.storage.investigations import Investigation

UPCOMING_WORKSPACE_TEXT = "Le graphe, la file de revue et la fiche de l'enquête s'afficheront ici."
SELECTION_PREFIX = "Sélection : "
COUNTERS_ACCESSIBLE_NAME = "Compteurs de l'enquête"
UNAVAILABLE_TEXT = "?"
FIRST_PLURAL = 2


def noun_for(count: int | None, singular: str, plural: str) -> str:
    return singular if count is not None and count < FIRST_PLURAL else plural


class Counter(QWidget):
    def __init__(
        self, singular: str, plural: str, *, alert: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.singular = singular
        self.plural = plural
        self.alert = alert
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self.number_label = QLabel(self)
        self.noun_label = QLabel(self)
        self.noun_label.setProperty("tone", "muted")
        layout.addWidget(self.number_label)
        layout.addWidget(self.noun_label)
        self.show_count(0)

    def show_count(self, count: int | None) -> None:
        self.number_label.setText(UNAVAILABLE_TEXT if count is None else str(count))
        tone = "counter-alert" if self.alert and count else "counter"
        self.number_label.setProperty("tone", tone)
        self.number_label.style().unpolish(self.number_label)
        self.number_label.style().polish(self.number_label)
        self.noun_label.setText(noun_for(count, self.singular, self.plural))

    def text(self) -> str:
        return f"{self.number_label.text()} {self.noun_label.text()}"


class InvestigationHeader(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("investigationHeader")
        self.name_label = QLabel(self)
        self.name_label.setProperty("tone", "investigation-title")
        self.question_label = QLabel(self)
        self.question_label.setProperty("tone", "muted")
        self.question_label.setWordWrap(True)
        self.entity_counter = Counter("entité", "entités", parent=self)
        self.link_counter = Counter("lien", "liens", parent=self)
        self.homonym_counter = Counter("homonyme confirmé", "homonymes confirmés", parent=self)
        self.signal_counter = Counter("signal", "signaux", alert=True, parent=self)
        self.counters = QWidget(self)
        self.counters.setAccessibleName(COUNTERS_ACCESSIBLE_NAME)
        counter_layout = QHBoxLayout(self.counters)
        counter_layout.setContentsMargins(0, 0, 0, 0)
        counter_layout.setSpacing(14)
        for counter in self.all_counters():
            counter.setParent(self.counters)
            counter_layout.addWidget(counter)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(self.name_label)
        titles.addWidget(self.question_label)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(24)
        layout.addLayout(titles, 1)
        layout.addWidget(self.counters, 0, Qt.AlignmentFlag.AlignVCenter)

    def all_counters(self) -> tuple[Counter, ...]:
        return (self.entity_counter, self.link_counter, self.homonym_counter, self.signal_counter)

    def show_investigation(self, investigation: Investigation) -> None:
        self.name_label.setText(investigation.name)
        self.question_label.setText(investigation.question)
        self.question_label.setVisible(bool(investigation.question))

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.entity_counter.show_count(overview.entities)
        self.link_counter.show_count(overview.links)
        self.homonym_counter.show_count(overview.confirmed_homonyms)
        self.signal_counter.show_count(overview.signals)
        self.signal_counter.setToolTip(overview.signal_problem)
        self.counters.setAccessibleDescription(
            ", ".join(counter.text() for counter in self.all_counters())
        )


class InvestigationPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("investigationPage")
        self.header = InvestigationHeader(self)
        self.selected_entity: str | None = None
        self.selection_label = QLabel(self)
        self.selection_label.setProperty("tone", "muted")
        self.upcoming_label = QLabel(UPCOMING_WORKSPACE_TEXT, self)
        self.upcoming_label.setProperty("tone", "faint")
        self.upcoming_label.setWordWrap(True)
        body = QVBoxLayout()
        body.setContentsMargins(24, 24, 24, 24)
        body.addWidget(self.selection_label, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self.upcoming_label, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.header)
        layout.addLayout(body, 1)

    def show_investigation(self, investigation: Investigation) -> None:
        self.header.show_investigation(investigation)
        self.selected_entity = None
        self.selection_label.clear()
        self.selection_label.hide()

    def show_overview(self, overview: InvestigationOverview) -> None:
        self.header.show_overview(overview)

    def show_entity(self, identifier: str, label: str) -> None:
        self.selected_entity = identifier
        self.selection_label.setText(f"{SELECTION_PREFIX}{label}")
        self.selection_label.show()
