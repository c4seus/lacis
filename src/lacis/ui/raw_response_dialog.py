from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout, QWidget

TITLE = "Réponse brute n° {identifier}"
TEXT_ACCESSIBLE_NAME = "Contenu de la réponse"
DIALOG_SIZE = (720, 560)


class RawResponseDialog(QDialog):
    def __init__(self, identifier: int, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE.format(identifier=identifier))
        self.resize(*DIALOG_SIZE)
        self.text_view = QPlainTextEdit(self)
        self.text_view.setReadOnly(True)
        self.text_view.setPlainText(text)
        self.text_view.setAccessibleName(TEXT_ACCESSIBLE_NAME)
        self.text_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        fixed: QFont = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.text_view.setFont(fixed)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.text_view)
        layout.addWidget(buttons)
