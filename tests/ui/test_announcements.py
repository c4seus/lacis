from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from lacis.ui.announcements import POLITE, announce


def test_an_announcement_reaches_the_accessibility_layer(qtbot: QtBot) -> None:
    widget = QWidget()
    qtbot.addWidget(widget)
    announce(widget, "Le nom de l'enquête est obligatoire.")
    announce(widget, "3 résultats dans le registre national.", POLITE)
