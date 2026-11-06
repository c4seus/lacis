from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QUndoCommand, QUndoStack


class InvestigationHistory(QUndoStack):
    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.indexChanged.connect(self.announce_change)

    def announce_change(self, index: int) -> None:
        self.changed.emit()

    def record(self, command: QUndoCommand) -> None:
        self.push(command)
