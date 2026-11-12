from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from lacis.review import RunningCollection

PANEL_ACCESSIBLE_NAME = "Collectes en cours"
CANCEL_TEXT = "Annuler"
PANEL_WIDTH = 300
BAR_HEIGHT = 4


class CollectionProgressRow(QFrame):
    cancel_requested = Signal(str)

    def __init__(self, collection: RunningCollection, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.identifier = collection.identifier
        self.setObjectName("collectionProgressRow")
        self.title_label = QLabel(collection.title, self)
        self.title_label.setProperty("tone", "current")
        self.title_label.setWordWrap(True)
        self.status_label = QLabel(self)
        self.status_label.setProperty("tone", "caption")
        self.bar = QProgressBar(self)
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(BAR_HEIGHT)
        self.bar.setAccessibleName(collection.title)
        self.cancel_button = QPushButton(CANCEL_TEXT, self)
        self.cancel_button.setProperty("compact", True)
        self.cancel_button.clicked.connect(lambda: self.cancel_requested.emit(self.identifier))
        heading = QHBoxLayout()
        heading.setSpacing(8)
        heading.addWidget(self.title_label, 1)
        heading.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignTop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(heading)
        layout.addWidget(self.bar)
        layout.addWidget(self.status_label)
        self.show_collection(collection)

    def show_collection(self, collection: RunningCollection) -> None:
        self.status_label.setText(collection.status_text)
        self.bar.setAccessibleDescription(collection.status_text)
        self.cancel_button.setAccessibleName(collection.cancel_name)
        self.cancel_button.setEnabled(not collection.cancelling)


class CollectionProgressPanel(QFrame):
    cancel_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("collectionProgress")
        self.setAccessibleName(PANEL_ACCESSIBLE_NAME)
        self.setFixedWidth(PANEL_WIDTH)
        self.rows: dict[str, CollectionProgressRow] = {}
        self.rows_layout = QVBoxLayout(self)
        self.rows_layout.setContentsMargins(12, 10, 12, 10)
        self.rows_layout.setSpacing(12)
        self.hide()

    def show_collections(self, collections: tuple[RunningCollection, ...]) -> None:
        shown = {collection.identifier for collection in collections}
        for identifier in [identifier for identifier in self.rows if identifier not in shown]:
            row = self.rows.pop(identifier)
            self.rows_layout.removeWidget(row)
            row.hide()
            row.deleteLater()
        for collection in collections:
            known = self.rows.get(collection.identifier)
            if known is not None:
                known.show_collection(collection)
                continue
            added = CollectionProgressRow(collection, self)
            added.cancel_requested.connect(self.cancel_requested)
            self.rows[collection.identifier] = added
            self.rows_layout.addWidget(added)
            added.show()
        self.setVisible(bool(self.rows))
        self.fit()

    def fit(self) -> None:
        self.rows_layout.activate()
        self.resize(PANEL_WIDTH, self.rows_layout.totalHeightForWidth(PANEL_WIDTH))
