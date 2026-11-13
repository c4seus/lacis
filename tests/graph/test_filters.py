import sqlite3

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.filters import GraphFilter, flagged_choice_label, kind_choice_label
from lacis.storage.entities import EntityKind


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


def test_the_default_filter_shows_everything(drawing: GraphDrawing) -> None:
    graph_filter = GraphFilter()
    assert not graph_filter.is_active
    assert graph_filter.shown_identifiers(drawing) == {node.identifier for node in drawing.nodes}
    assert graph_filter.hidden_count(drawing) == 0
    assert graph_filter.summary(drawing) == "tous les types"


def test_hiding_kinds_counts_the_hidden_entities(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    graph_filter = GraphFilter().showing_kind(EntityKind.ESTABLISHMENT, False)
    graph_filter = graph_filter.showing_kind(EntityKind.ADDRESS, False)
    assert graph_filter.is_active
    assert graph_filter.hidden_kinds == {EntityKind.ESTABLISHMENT, EntityKind.ADDRESS}
    assert scenario.address not in graph_filter.shown_identifiers(drawing)
    assert graph_filter.summary(drawing) == "3 entités masquées"
    shown_again = graph_filter.showing_kind(EntityKind.ADDRESS, True)
    assert shown_again.summary(drawing) == "2 entités masquées"
    assert shown_again.showing_kind(EntityKind.ESTABLISHMENT, True) == GraphFilter()


def test_flagged_entities_only_hides_the_others(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    graph_filter = GraphFilter().showing_flagged_only(True)
    assert graph_filter.shown_identifiers(drawing) == {
        scenario.dupont_services,
        scenario.acme,
        scenario.jean,
        scenario.jean_pierre,
    }
    assert graph_filter.summary(drawing) == "5 entités masquées"
    one_left = graph_filter.showing_kind(EntityKind.COMPANY, False)
    assert one_left.summary(drawing) == "7 entités masquées"
    assert not graph_filter.showing_flagged_only(False).is_active


def test_choices_tell_how_many_entities_they_cover(drawing: GraphDrawing) -> None:
    assert kind_choice_label(EntityKind.COMPANY, drawing) == "Entreprises (3)"
    assert kind_choice_label(EntityKind.FOREIGN_COMPANY, drawing) == ("Entreprises étrangères (1)")
    assert flagged_choice_label(drawing) == "Entités signalées seulement (4)"
    assert GraphFilter().showing_kind(EntityKind.PERSON, False).summary(drawing) == (
        "2 entités masquées"
    )
