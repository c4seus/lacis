from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from lacis.details import written_moment
from lacis.storage.verdicts import EntityVerdict, Verdict

NO_VERDICT_TEXT = "Aucun verdict"
CHOICE_ACCESSIBLE_PREFIX = "Verdict sur "
REASON_PLACEHOLDER = "Raison, facultative"
REASON_ACCESSIBLE_PREFIX = "Raison du verdict sur "
UNDECIDED_TEXT = "Le verdict ne change ni les faits collectés ni les signaux."


def decided_text(verdict: EntityVerdict | None) -> str:
    if verdict is None:
        return UNDECIDED_TEXT
    return f"Décidé le {written_moment(verdict.decided_at)}"


class VerdictEditor(QWidget):
    changed = Signal(str, object, str)

    def __init__(
        self,
        identifier: str,
        entity_name: str,
        verdict: EntityVerdict | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.identifier = identifier
        self.choice = QComboBox(self)
        self.choice.setAccessibleName(f"{CHOICE_ACCESSIBLE_PREFIX}{entity_name}")
        self.choice.addItem(NO_VERDICT_TEXT, "")
        for choice in Verdict:
            self.choice.addItem(choice.label, choice.value)
        self.reason = QLineEdit(self)
        self.reason.setPlaceholderText(REASON_PLACEHOLDER)
        self.reason.setAccessibleName(f"{REASON_ACCESSIBLE_PREFIX}{entity_name}")
        self.decided_label = QLabel(self)
        self.decided_label.setProperty("tone", "faint")
        self.decided_label.setWordWrap(True)
        self.show_verdict(verdict)
        self.choice.currentIndexChanged.connect(self.save)
        self.reason.editingFinished.connect(self.save)
        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(8)
        line.addWidget(self.choice)
        line.addWidget(self.reason, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(line)
        layout.addWidget(self.decided_label)

    def chosen(self) -> Verdict | None:
        value = str(self.choice.currentData())
        return Verdict(value) if value else None

    def show_verdict(self, verdict: EntityVerdict | None) -> None:
        self.saved = verdict
        blocked = self.choice.blockSignals(True)
        value = "" if verdict is None else verdict.verdict.value
        self.choice.setCurrentIndex(self.choice.findData(value))
        self.choice.blockSignals(blocked)
        if not self.reason.hasFocus():
            self.reason.setText("" if verdict is None else verdict.reason)
        self.reason.setEnabled(verdict is not None)
        self.decided_label.setText(decided_text(verdict))

    def save(self) -> None:
        chosen = self.chosen()
        reason = self.reason.text().strip() if chosen is not None else ""
        self.reason.setEnabled(chosen is not None)
        saved = self.saved
        if saved is None and chosen is None:
            return
        if saved is not None and (saved.verdict, saved.reason) == (chosen, reason):
            return
        self.changed.emit(self.identifier, chosen, reason)
