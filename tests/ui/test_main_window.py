from pytestqt.qtbot import QtBot

from lacis.ui.main_window import DEFAULT_SIZE, MINIMUM_SIZE, MainWindow


def test_the_main_window_is_titled_lacis(qtbot: QtBot) -> None:
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    assert main_window.windowTitle() == "Lacis"


def test_the_main_window_opens_at_its_default_size(qtbot: QtBot) -> None:
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    assert main_window.size() == DEFAULT_SIZE


def test_the_main_window_cannot_be_smaller_than_1024_by_640(qtbot: QtBot) -> None:
    main_window = MainWindow()
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.resize(800, 480)
    assert main_window.minimumSize() == MINIMUM_SIZE
    assert main_window.width() >= 1024
    assert main_window.height() >= 640
