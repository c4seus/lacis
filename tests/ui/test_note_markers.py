import sqlite3

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.graph.descriptions import entity_summary
from lacis.graph.drawing import graph_drawing
from lacis.storage.notes import NoteStore
from lacis.tables import entity_rows
from lacis.ui.data_table import SORT_ROLE
from lacis.ui.entity_table import EntityColumn, EntityTableModel
from lacis.ui.graph_legend import NoteSwatch
from lacis.ui.graph_view import GraphScene, note_marker_area


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def noted(builder: InvestigationBuilder) -> tuple[str, str]:
    acme = builder.company("ACME PLOMBERIE")
    dupont = builder.company("DUPONT SERVICES", identifier="company:222222222")
    NoteStore(builder.connection).save(acme, "Gérant de paille ?")
    return acme, dupont


def test_the_graph_knows_which_entities_have_a_note(
    builder: InvestigationBuilder, noted: tuple[str, str]
) -> None:
    acme, dupont = noted
    drawing = graph_drawing(builder.connection)
    assert drawing.require_node(acme).noted
    assert not drawing.require_node(dupont).noted
    assert entity_summary(drawing, drawing.require_node(acme)).endswith(", avec une note")
    assert "note" not in entity_summary(drawing, drawing.require_node(dupont))


def test_a_noted_entity_carries_its_marker_in_the_graph(
    qtbot: QtBot,
    builder: InvestigationBuilder,
    icon_factory: IconFactory,
    noted: tuple[str, str],
) -> None:
    acme, _ = noted
    scene = GraphScene(icon_factory.colours_provider)
    drawing = graph_drawing(builder.connection)
    scene.show_drawing(drawing)
    item = scene.node_items[acme]
    assert item.boundingRect().contains(note_marker_area(item.node))
    assert "avec une note" in item.toolTip()
    image = QImage(400, 400, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    scene.render(painter)
    painter.end()


def test_the_entities_table_shows_which_entities_have_a_note(
    builder: InvestigationBuilder, icon_factory: IconFactory, noted: tuple[str, str]
) -> None:
    acme, _ = noted
    rows = tuple(entity_rows(builder.connection, None))
    assert {row.identifier: row.noted for row in rows}[acme]
    model = EntityTableModel(icon_factory.colours_provider)
    model.show_rows(rows)
    spoken = Qt.ItemDataRole.AccessibleTextRole
    cells = {
        row.identifier: model.index(index, EntityColumn.NOTE) for index, row in enumerate(rows)
    }
    assert [cell.data() for cell in cells.values()] == ["Oui", ""]
    assert [cell.data(spoken) for cell in cells.values()] == ["avec une note", "sans note"]
    assert [cell.data(SORT_ROLE) for cell in cells.values()] == [1.0, 0.0]


def test_the_legend_draws_the_note_marker(qtbot: QtBot, icon_factory: IconFactory) -> None:
    swatch = NoteSwatch(icon_factory.colours_provider)
    qtbot.addWidget(swatch)
    assert not swatch.grab().isNull()
