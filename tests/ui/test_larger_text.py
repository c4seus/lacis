from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QRect, QSettings, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QApplication,
    QLabel,
    QScrollArea,
    QWidget,
)
from pytestqt.qtbot import QtBot

from graph_scenario import plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.notices import NoticeFamily
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
SMALL_SCREEN = QSize(1280, 800)
TOLERANCE = 1
SETTLING_ROUNDS = 5


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, QUESTION)
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        scenario = plumbers_scenario(builder)
        builder.notice(
            scenario.dupont_services,
            NoticeFamily.INSOLVENCY,
            date(2022, 12, 5),
            "Jugement de clôture pour insuffisance d'actif",
        )
        for position in range(2):
            company = builder.company(f"MARTIN RENOVATION {position}")
            builder.mandate(builder.person("Paul", "MARTIN"), company, "Président")
    return library


@pytest.fixture(params=[100, 200], ids=["100 %", "200 %"])
def text_size(request: pytest.FixtureRequest, theme_controller: ThemeController) -> Iterator[int]:
    theme_controller.set_text_size(request.param)
    yield request.param
    theme_controller.set_text_size(100)


@pytest.fixture
def main_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    text_size: int,
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller, library=library)
    qtbot.addWidget(main_window)
    main_window.resize(SMALL_SCREEN)
    main_window.show()
    qtbot.waitExposed(main_window)
    return main_window


def scrolls(widget: QWidget, window: QWidget) -> bool:
    parent = widget.parentWidget()
    while parent is not None and parent is not window:
        if isinstance(parent, QAbstractScrollArea) and widget is not parent.viewport():
            return True
        parent = parent.parentWidget()
    return False


def shown(window: QWidget) -> list[QWidget]:
    return [widget for widget in window.findChildren(QWidget) if widget.isVisible()]


def cut_text(widget: QWidget) -> str | None:
    size = widget.size()
    if isinstance(widget, QLabel) and widget.text():
        if widget.wordWrap():
            needed = QSize(widget.minimumSizeHint().width(), widget.heightForWidth(size.width()))
        else:
            needed = widget.minimumSizeHint()
    elif isinstance(widget, QAbstractButton) and widget.text():
        needed = QSize(widget.sizeHint().width(), 0)
    else:
        return None
    if size.width() + TOLERANCE < needed.width() or size.height() + TOLERANCE < needed.height():
        return f"{widget.text()!r} is {size.toTuple()} but needs {needed.toTuple()}"
    return None


def layout_problems(window: QWidget) -> list[str]:
    problems = [problem for widget in shown(window) if (problem := cut_text(widget))]
    for area in window.findChildren(QScrollArea):
        content = area.widget()
        width = content.width() if content is not None and area.isVisible() else 0
        if width > area.viewport().width() + TOLERANCE:
            problems.append(f"{area.objectName()} is wider than its view")
    for widget in shown(window):
        if widget.focusPolicy() & Qt.FocusPolicy.TabFocus and not scrolls(widget, window):
            place = QRect(widget.mapTo(window, widget.rect().topLeft()), widget.size())
            if not window.rect().contains(place):
                problems.append(f"{widget.accessibleName()!r} is out of the window")
    return problems


def settle() -> None:
    for _round in range(SETTLING_ROUNDS):
        QApplication.processEvents()


def open_the_plumbers(main_window: MainWindow) -> None:
    main_window.open_investigation(INVESTIGATION_NAME)
    settle()


def select(main_window: MainWindow, label: str) -> None:
    page = main_window.investigation_page
    identifier = next(
        node.identifier for node in page.graph_view.drawing.nodes if node.label == label
    )
    page.show_entity(identifier, label)
    sheet = page.details_panel.entity_sheet
    for row in sheet.link_rows:
        row.provenance_button.setChecked(True)
    settle()


def test_the_home_screen_keeps_every_text_whole(main_window: MainWindow) -> None:
    assert layout_problems(main_window) == []
    main_window.home_screen.start_creation()
    settle()
    assert layout_problems(main_window) == []


def test_the_investigation_keeps_every_text_whole(main_window: MainWindow) -> None:
    open_the_plumbers(main_window)
    assert layout_problems(main_window) == []
    select(main_window, "DUPONT SERVICES")
    assert main_window.investigation_page.details_panel.entity_sheet.link_rows
    assert layout_problems(main_window) == []
    select(main_window, "Jean Pierre DUPONT\n1980-05")
    assert layout_problems(main_window) == []


def test_the_investigation_fits_a_small_screen(main_window: MainWindow) -> None:
    open_the_plumbers(main_window)
    assert main_window.size() == SMALL_SCREEN
    assert main_window.minimumSizeHint().width() <= SMALL_SCREEN.width()
    assert main_window.minimumSizeHint().height() <= SMALL_SCREEN.height()


def test_the_text_size_can_change_while_an_investigation_is_open(
    main_window: MainWindow, theme_controller: ThemeController, text_size: int
) -> None:
    open_the_plumbers(main_window)
    select(main_window, "DUPONT SERVICES")
    theme_controller.set_text_size(300 - text_size)
    settle()
    assert layout_problems(main_window) == []
