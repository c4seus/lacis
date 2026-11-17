import sqlite3
from dataclasses import replace

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.filters import GraphFilter
from lacis.storage.entities import EntityKind
from lacis.ui.data_table import IDENTIFIER_ROLE
from lacis.ui.graph_list import (
    LIST_ACCESSIBLE_NAME,
    GraphList,
    entity_key,
    is_entity,
    kind_key,
    link_key,
)

ENTITY_ROWS = (
    "Entreprises (3)",
    "  ACME PLOMBERIE",
    "  DUPONT SERVICES",
    "  HOLDING DUPONT",
    "Personnes (2)",
    "  Jean DUPONT (1980-05)",
    "  Jean Pierre DUPONT (1980-05)",
    "Adresses (1)",
    "  12 RUE DES LILAS 31000 TOULOUSE",
    "Établissements (2)",
    "  Siège — TOULOUSE",
    "  Siège — TOULOUSE",
    "Entreprises étrangères (1)",
    "  DUPONT INVEST LTD",
)


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


@pytest.fixture
def graph_list(qtbot: QtBot, icon_factory: IconFactory, drawing: GraphDrawing) -> GraphList:
    graph_list = GraphList(icon_factory.colours_provider)
    qtbot.addWidget(graph_list)
    graph_list.resize(500, 700)
    graph_list.show()
    qtbot.waitExposed(graph_list)
    graph_list.show_drawing(drawing)
    return graph_list


def shown_rows(graph_list: GraphList) -> list[str]:
    rows = []
    index = graph_list.model().index(0, 0)
    while index.isValid():
        depth = 0
        parent = index.parent()
        while parent.isValid():
            depth += 1
            parent = parent.parent()
        rows.append(f"{'  ' * depth}{index.data()}")
        index = graph_list.indexBelow(index)
    return rows


def index_of(graph_list: GraphList, key: str) -> QModelIndex:
    return graph_list.list_model.index_of(key)


def first_child(index: QModelIndex) -> QModelIndex:
    return index.model().index(0, 0, index)


def spoken(graph_list: GraphList, key: str) -> str:
    return str(index_of(graph_list, key).data(Qt.ItemDataRole.AccessibleTextRole))


def press(graph_list: GraphList, key: Qt.Key) -> None:
    QTest.keyClick(graph_list, key)


def test_the_list_groups_the_entities_by_kind_with_their_links_folded(
    graph_list: GraphList,
) -> None:
    assert graph_list.accessibleName() == LIST_ACCESSIBLE_NAME
    assert graph_list.isHeaderHidden()
    assert shown_rows(graph_list) == list(ENTITY_ROWS)


def test_every_entity_and_every_link_is_in_the_list(
    graph_list: GraphList, drawing: GraphDrawing
) -> None:
    graph_list.expandAll()
    keys = graph_list.list_model.items
    for node in drawing.nodes:
        assert entity_key(node.identifier) in keys
    for edge in drawing.edges:
        assert link_key(edge.source, edge.identifier) in keys
        assert link_key(edge.target, edge.identifier) in keys
    rows = len(ENTITY_ROWS) + 2 * len(drawing.edges)
    assert len(shown_rows(graph_list)) == rows


def test_each_row_is_spoken_with_its_kind_and_its_number_of_links(
    graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    assert spoken(graph_list, kind_key(EntityKind.COMPANY)) == "Entreprises, 3 entités"
    assert spoken(graph_list, entity_key(scenario.holding)) == (
        "HOLDING DUPONT, entreprise, connue comme dirigeante seulement, 1 lien"
    )
    link = first_child(index_of(graph_list, entity_key(scenario.holding)))
    assert link.data(Qt.ItemDataRole.AccessibleTextRole) == "Directeur général de ACME PLOMBERIE"
    assert link.data(Qt.ItemDataRole.ToolTipRole) == "Directeur général de ACME PLOMBERIE"
    assert link.data(IDENTIFIER_ROLE) == scenario.acme
    assert is_entity(index_of(graph_list, entity_key(scenario.holding)))
    assert not is_entity(link)
    assert not is_entity(QModelIndex())


def test_each_row_shows_the_icon_of_the_kind_it_leads_to(
    graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    group = index_of(graph_list, kind_key(EntityKind.PERSON))
    link = first_child(index_of(graph_list, entity_key(scenario.holding)))
    company_icon = graph_list.list_model.kind_icons.icon(EntityKind.COMPANY)
    person_icon = graph_list.list_model.kind_icons.icon(EntityKind.PERSON)
    assert group.data(Qt.ItemDataRole.DecorationRole).cacheKey() == person_icon.cacheKey()
    assert link.data(Qt.ItemDataRole.DecorationRole).cacheKey() == company_icon.cacheKey()


def test_the_list_describes_the_graph_and_its_filter(graph_list: GraphList) -> None:
    assert graph_list.accessibleDescription() == "9 entités, 9 liens, 4 entités signalées"
    graph_list.apply_filter(GraphFilter(flagged_only=True))
    assert graph_list.accessibleDescription() == (
        "9 entités, 9 liens, 4 entités signalées, 5 entités masquées"
    )


def test_the_list_follows_the_filters_of_the_graph(graph_list: GraphList) -> None:
    graph_list.apply_filter(GraphFilter(flagged_only=True))
    assert shown_rows(graph_list) == [
        "Entreprises (2)",
        "  ACME PLOMBERIE",
        "  DUPONT SERVICES",
        "Personnes (2)",
        "  Jean DUPONT (1980-05)",
        "  Jean Pierre DUPONT (1980-05)",
    ]


def test_the_arrow_keys_walk_through_the_entities_and_open_their_links(
    graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    graph_list.setFocus()
    graph_list.setCurrentIndex(index_of(graph_list, entity_key(scenario.holding)))
    press(graph_list, Qt.Key.Key_Right)
    press(graph_list, Qt.Key.Key_Down)
    assert graph_list.currentIndex().data() == "Directeur général de ACME PLOMBERIE"
    press(graph_list, Qt.Key.Key_Down)
    assert graph_list.currentIndex().data() == "Personnes (2)"
    press(graph_list, Qt.Key.Key_Down)
    assert graph_list.currentIndex().data(IDENTIFIER_ROLE) == scenario.jean


def test_moving_to_an_entity_chooses_it_but_not_a_group_or_a_link(
    qtbot: QtBot, graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    chosen: list[str] = []
    graph_list.entity_chosen.connect(chosen.append)
    graph_list.setFocus()
    graph_list.setCurrentIndex(index_of(graph_list, kind_key(EntityKind.COMPANY)))
    press(graph_list, Qt.Key.Key_Down)
    graph_list.expand(graph_list.currentIndex())
    press(graph_list, Qt.Key.Key_Down)
    assert chosen == [scenario.acme]


def test_activating_a_link_chooses_the_entity_it_leads_to(
    graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    chosen: list[str] = []
    graph_list.entity_chosen.connect(chosen.append)
    holding = index_of(graph_list, entity_key(scenario.holding))
    graph_list.expand(holding)
    graph_list.setFocus()
    graph_list.setCurrentIndex(first_child(holding))
    chosen.clear()
    press(graph_list, Qt.Key.Key_Return)
    graph_list.activated.emit(index_of(graph_list, kind_key(EntityKind.COMPANY)))
    assert chosen == [scenario.acme]


def test_an_entity_chosen_elsewhere_is_selected_in_the_list(
    graph_list: GraphList, scenario: PlumbersScenario
) -> None:
    chosen: list[str] = []
    graph_list.entity_chosen.connect(chosen.append)
    graph_list.collapse(index_of(graph_list, kind_key(EntityKind.ADDRESS)))
    graph_list.mark_selected(scenario.address)
    assert graph_list.currentIndex() == index_of(graph_list, entity_key(scenario.address))
    assert graph_list.selected_identifier() == scenario.address
    assert graph_list.isExpanded(index_of(graph_list, kind_key(EntityKind.ADDRESS)))
    graph_list.mark_selected(scenario.address)
    graph_list.mark_selected(None)
    assert graph_list.selected_identifier() is None
    graph_list.mark_selected("company:999999999")
    assert graph_list.selected_identifier() is None
    assert chosen == []


def test_a_new_drawing_keeps_the_folds_and_the_current_row(
    graph_list: GraphList, drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    graph_list.collapse(index_of(graph_list, kind_key(EntityKind.ADDRESS)))
    graph_list.expand(index_of(graph_list, entity_key(scenario.holding)))
    graph_list.expand(index_of(graph_list, entity_key(scenario.jean)))
    graph_list.collapse(index_of(graph_list, entity_key(scenario.jean)))
    graph_list.setCurrentIndex(first_child(index_of(graph_list, entity_key(scenario.holding))))
    chosen: list[str] = []
    graph_list.entity_chosen.connect(chosen.append)
    kept = tuple(edge for edge in drawing.edges if not edge.touches(scenario.invest))
    graph_list.show_drawing(replace(drawing, edges=kept))
    assert spoken(graph_list, entity_key(scenario.invest)) == (
        "DUPONT INVEST LTD, entreprise étrangère, 0 lien"
    )
    assert not graph_list.isExpanded(index_of(graph_list, kind_key(EntityKind.ADDRESS)))
    assert graph_list.isExpanded(index_of(graph_list, kind_key(EntityKind.PERSON)))
    assert graph_list.isExpanded(index_of(graph_list, entity_key(scenario.holding)))
    assert not graph_list.isExpanded(index_of(graph_list, entity_key(scenario.jean)))
    assert graph_list.currentIndex().data() == "Directeur général de ACME PLOMBERIE"
    assert chosen == []


def test_an_unchanged_drawing_leaves_the_list_alone(
    graph_list: GraphList, drawing: GraphDrawing
) -> None:
    items = graph_list.list_model.items
    graph_list.show_drawing(replace(drawing))
    assert graph_list.list_model.items is items


def test_an_empty_graph_empties_the_list(graph_list: GraphList) -> None:
    graph_list.show_drawing(GraphDrawing())
    assert shown_rows(graph_list) == []
    assert graph_list.accessibleDescription() == "Graphe vide"
