from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from lacis.storage.investigations import Investigation

BACK_TO_HOME_TEXT = "Retour aux enquêtes"
UPCOMING_WORKSPACE_TEXT = (
    "L'espace de travail de l'enquête, avec son graphe, ses signaux et son journal, "
    "arrive dans une prochaine version de Lacis."
)
PAGE_TEXT_WIDTH = 640


class InvestigationPage(QWidget):
    home_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("investigationPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(10)
        self.name_label = QLabel(self)
        self.name_label.setProperty("tone", "page-title")
        self.question_label = QLabel(self)
        self.question_label.setProperty("tone", "subtitle")
        self.question_label.setWordWrap(True)
        self.upcoming_label = QLabel(UPCOMING_WORKSPACE_TEXT, self)
        self.upcoming_label.setProperty("tone", "faint")
        self.upcoming_label.setWordWrap(True)
        self.back_button = QPushButton(BACK_TO_HOME_TEXT, self)
        self.back_button.clicked.connect(self.home_requested)
        for label in (self.name_label, self.question_label, self.upcoming_label):
            label.setMaximumWidth(PAGE_TEXT_WIDTH)
            label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(label, 100)
            row.addStretch(1)
            layout.addLayout(row)
        layout.addSpacing(8)
        layout.addWidget(self.back_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def show_investigation(self, investigation: Investigation) -> None:
        self.name_label.setText(investigation.name)
        self.question_label.setText(investigation.question)
        self.question_label.setVisible(bool(investigation.question))
