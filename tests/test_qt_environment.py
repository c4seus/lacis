from PySide6.QtWidgets import QApplication, QLabel
from pytestqt.qtbot import QtBot


def test_qt_widgets_run_without_a_display(qtbot: QtBot) -> None:
    label = QLabel("Lacis")
    qtbot.addWidget(label)
    label.show()
    assert label.isVisible()


def test_tests_run_on_a_full_hd_offscreen_screen(qapp: QApplication) -> None:
    screen_size = qapp.primaryScreen().size()
    assert (screen_size.width(), screen_size.height()) == (1920, 1080)
