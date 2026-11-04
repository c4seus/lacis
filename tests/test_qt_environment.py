from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot


def test_qt_widgets_run_without_a_display(qtbot: QtBot) -> None:
    label = QLabel("Lacis")
    qtbot.addWidget(label)
    label.show()
    assert label.isVisible()
