import sqlite3
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QImage, QPainter
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.graph.descriptions import entity_summary
from lacis.graph.drawing import graph_drawing
from lacis.graph.filters import GraphFilter
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore
from lacis.tables import entity_rows
from lacis.ui.data_table import SORT_ROLE
from lacis.ui.entity_table import EntityColumn, EntityTableModel
from lacis.ui.graph_legend import VerdictSwatch
from lacis.ui.graph_view import GraphScene, verdict_badge_area
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
ACME = "company:111111111"
DUPONT = "company:222222222"


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    builder = InvestigationBuilder(investigation_connection)
    builder.company("ACME PLOMBERIE", identifier=ACME)
    builder.company("DUPONT SERVICES", identifier=DUPONT)
    VerdictStore(builder.connection).save(ACME, Verdict.SUSPECT, "")
    return builder


def test_the_graph_shows_the_verdict_of_each_entity(
    qtbot: QtBot, builder: InvestigationBuilder, icon_factory: IconFactory
) -> None:
    drawing = graph_drawing(builder.connection)
    acme = drawing.require_node(ACME)
    assert acme.verdict is Verdict.SUSPECT
    assert drawing.require_node(DUPONT).verdict is None
    assert "verdict : suspect" in entity_summary(drawing, acme)
    scene = GraphScene(icon_factory.colours_provider)
    scene.show_drawing(drawing)
    item = scene.node_items[ACME]
    assert item.boundingRect().contains(verdict_badge_area(acme))
    image = QImage(400, 400, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    scene.render(painter)
    painter.end()
    for verdict in Verdict:
        swatch = VerdictSwatch(verdict, icon_factory.colours_provider)
        qtbot.addWidget(swatch)
        assert not swatch.grab().isNull()


@pytest.mark.parametrize("verdict", list(Verdict))
def test_the_graph_filter_keeps_the_entities_of_a_verdict(
    builder: InvestigationBuilder, verdict: Verdict
) -> None:
    VerdictStore(builder.connection).save(DUPONT, verdict, "")
    drawing = graph_drawing(builder.connection)
    shown = GraphFilter().showing_verdict(verdict).shown_identifiers(drawing)
    expected = {DUPONT} | ({ACME} if verdict is Verdict.SUSPECT else set())
    assert shown == expected
    assert GraphFilter().showing_verdict(verdict).is_active


def test_the_entities_table_shows_and_sorts_the_verdict(
    builder: InvestigationBuilder, icon_factory: IconFactory
) -> None:
    rows = tuple(entity_rows(builder.connection, None))
    model = EntityTableModel(icon_factory.colours_provider)
    model.show_rows(rows)
    spoken = Qt.ItemDataRole.AccessibleTextRole
    cells = {
        row.identifier: model.index(index, EntityColumn.VERDICT) for index, row in enumerate(rows)
    }
    assert cells[ACME].data() == "Suspect"
    assert cells[DUPONT].data() == ""
    assert cells[ACME].data(spoken) == "verdict Suspect"
    assert cells[DUPONT].data(spoken) == "sans verdict"
    assert cells[ACME].data(SORT_ROLE) == 1.0
    assert cells[DUPONT].data(SORT_ROLE) == -1.0


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.company("ACME PLOMBERIE", date(2021, 3, 1), identifier=ACME)
        builder.company("DUPONT SERVICES", date(2019, 4, 2), identifier=DUPONT)
        VerdictStore(opened.connection).save(ACME, Verdict.SUSPECT, "")
        VerdictStore(opened.connection).save(DUPONT, Verdict.DISMISSED, "")
        TagStore(opened.connection).add(ACME, "Client")
        TagStore(opened.connection).add(DUPONT, "Client")
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
    window.show()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    return window


def shown_everywhere(window: MainWindow) -> tuple[list[str], list[str], list[str]]:
    page = window.investigation_page
    graph = sorted(page.graph_area.filter_chip.graph_filter.shown_identifiers(page.drawing))
    queue = [row.entity.identifier for row in page.queue_column.review_list.rows]
    table = sorted(page.details_panel.entities_tab.shown_identifiers())
    return graph, queue, table


def test_the_graph_menu_filters_every_view_by_verdict(window: MainWindow) -> None:
    page = window.investigation_page
    chip = page.graph_area.filter_chip
    assert [action.text() for action in chip.verdict_menu.actions()] == [
        "Tous les verdicts",
        "À vérifier",
        "Suspect",
        "Écarté",
        "Confirmé",
    ]
    chip.verdict_actions[Verdict.SUSPECT].trigger()
    assert page.verdict is Verdict.SUSPECT
    assert shown_everywhere(window) == ([ACME], [ACME], [ACME])
    assert page.details_panel.entities_tab.verdict_box.currentText() == "Suspect"


def test_the_entities_tab_filters_every_view_by_verdict(window: MainWindow) -> None:
    page = window.investigation_page
    box = page.details_panel.entities_tab.verdict_box
    box.setCurrentIndex(box.findData(Verdict.DISMISSED.value))
    assert page.verdict is Verdict.DISMISSED
    assert shown_everywhere(window) == ([DUPONT], [DUPONT], [DUPONT])
    assert page.graph_area.filter_chip.verdict_actions[Verdict.DISMISSED].isChecked()


def test_a_tag_and_a_verdict_filter_together_and_clear_together(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_by_tag("client")
    page.filter_entities("client", Verdict.SUSPECT)
    review_list = page.queue_column.review_list
    assert review_list.entity_filter is not None
    assert review_list.entity_filter.description == "Tag : Client · Verdict : Suspect"
    assert shown_everywhere(window) == ([ACME], [ACME], [ACME])
    assert review_list.clear_filter_button is not None
    review_list.clear_filter_button.click()
    assert (page.tag, page.verdict) == (None, None)
    assert shown_everywhere(window) == ([ACME, DUPONT], [ACME, DUPONT], [ACME, DUPONT])
    assert page.details_panel.entities_tab.verdict_box.currentText() == "Tous les verdicts"
    assert page.graph_area.filter_chip.verdict_actions[None].isChecked()


def test_showing_everything_in_the_graph_clears_the_verdict(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_entities(None, Verdict.SUSPECT)
    page.graph_area.filter_chip.show_everything()
    assert page.verdict is None
    assert page.queue_column.review_list.entity_filter is None


def test_a_verdict_never_hides_a_fact_or_a_signal(window: MainWindow) -> None:
    page = window.investigation_page
    assert len(page.drawing.nodes) == 2
    assert page.graph_area.filter_chip.text() == "Filtres · tous les types"
