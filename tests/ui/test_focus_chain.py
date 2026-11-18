from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.storage.entities import EntityKind
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui.focus_chain import focusable_descendants, place_after
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"


def reachable(widget: QWidget) -> bool:
    tab_focus = widget.focusPolicy() & Qt.FocusPolicy.TabFocus
    return bool(tab_focus) and widget.isVisible() and widget.isEnabled()


def walk(start: QWidget, step: Callable[[QWidget], QWidget | None]) -> list[QWidget]:
    order = [start]
    widget = step(start)
    while widget is not None and widget is not start:
        if reachable(widget):
            order.append(widget)
        widget = step(widget)
    return order


def tab_order(start: QWidget) -> list[QWidget]:
    return walk(start, QWidget.nextInFocusChain)


def follows(order: list[QWidget], anchor: QWidget, widgets: list[QWidget]) -> bool:
    start = order.index(anchor) + 1
    return order[start : start + len(widgets)] == widgets


def test_widgets_added_to_a_container_follow_its_anchor(qtbot: QtBot) -> None:
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    first = QPushButton("Premier", root)
    container = QWidget(root)
    last = QPushButton("Dernier", root)
    for widget in (first, container, last):
        layout.addWidget(widget)
    inner = QVBoxLayout(container)
    added = [QPushButton(text, container) for text in ("Un", "Deux")]
    inner.addWidget(QLabel("Titre", container))
    for button in added:
        inner.addWidget(button)
    root.show()
    assert tab_order(first) == [first, last, *added]
    place_after(container, container)
    assert tab_order(first) == [first, *added, last]
    assert container.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert focusable_descendants(container) == added


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.mandate(
            builder.person("Jean", "DUPONT"),
            builder.company("SOCIETE", date(2024, 5, 2), identifier="company:111111111"),
        )
    return library


@pytest.fixture
def window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.resize(1440, 900)
    window.show()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    page = window.investigation_page
    company = next(
        node.identifier
        for node in page.graph_view.drawing.nodes
        if node.kind is EntityKind.COMPANY
    )
    page.show_entity(company, "")
    qtbot.waitUntil(page.details_panel.entity_sheet.expand_button.isVisible)
    return window


def queue_widgets(window: MainWindow) -> list[QWidget]:
    review_list = window.investigation_page.queue_column.review_list
    return [widget for widget in focusable_descendants(review_list.content) if widget.isVisible()]


def sheet_widgets(window: MainWindow) -> list[QWidget]:
    sheet = window.investigation_page.details_panel.entity_sheet
    return [widget for widget in focusable_descendants(sheet.content) if widget.isVisible()]


def test_the_rows_of_the_review_column_come_in_their_region(window: MainWindow) -> None:
    page = window.investigation_page
    review_list = page.queue_column.review_list
    order = tab_order(window.header_bar.search_field)
    rows = queue_widgets(window)
    assert review_list.rows[0] in rows
    assert follows(order, review_list, rows)
    assert order.index(rows[-1]) < order.index(page.graph_area.filter_chip)


def test_the_widgets_of_the_sheet_come_in_the_details_panel(window: MainWindow) -> None:
    sheet = window.investigation_page.details_panel.entity_sheet
    order = tab_order(window.header_bar.search_field)
    widgets = sheet_widgets(window)
    assert sheet.expand_button in widgets
    assert follows(order, sheet, widgets)
    assert order.index(window.investigation_page.graph_view) < order.index(sheet)
