import sqlite3

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.descriptions import entity_description, entity_summary, graph_summary
from lacis.graph.drawing import GraphDrawing, graph_drawing


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


def summary_of(drawing: GraphDrawing, identifier: str) -> str:
    return entity_summary(drawing, drawing.require_node(identifier))


def test_a_summary_gives_the_entity_its_kind_and_its_number_of_links(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    assert summary_of(drawing, scenario.acme) == (
        "ACME PLOMBERIE, entreprise, 4 liens, signal de sévérité forte"
    )
    assert summary_of(drawing, scenario.dupont_services) == (
        "DUPONT SERVICES, entreprise, fermée, 2 liens, signal de sévérité forte"
    )
    assert summary_of(drawing, scenario.holding) == (
        "HOLDING DUPONT, entreprise, connue comme dirigeante seulement, 1 lien"
    )
    assert summary_of(drawing, scenario.dupont_office) == (
        "Siège — TOULOUSE, établissement, fermé, 2 liens"
    )
    assert summary_of(drawing, scenario.invest) == (
        "DUPONT INVEST LTD, entreprise étrangère, 1 lien"
    )
    assert summary_of(drawing, scenario.address) == (
        "12 RUE DES LILAS 31000 TOULOUSE, adresse, 2 liens"
    )


def test_a_description_lists_the_links_of_the_entity(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    assert entity_description(drawing, scenario.jean) == (
        "Jean DUPONT (1980-05), personne, 2 liens, signal de sévérité forte. "
        "Liens : Président de DUPONT SERVICES ; "
        "même personne que Jean Pierre DUPONT (1980-05)."
    )
    assert entity_description(drawing, scenario.dupont_services) == (
        "DUPONT SERVICES, entreprise, fermée, 2 liens, signal de sévérité forte. "
        "Liens : Président : Jean DUPONT (1980-05) ; établissement Siège — TOULOUSE."
    )


def test_a_lonely_or_unknown_entity_is_described_without_links(
    investigation_connection: sqlite3.Connection,
) -> None:
    builder = InvestigationBuilder(investigation_connection)
    lonely = builder.company("ACME PLOMBERIE")
    drawing = graph_drawing(investigation_connection)
    assert entity_description(drawing, lonely) == "ACME PLOMBERIE, entreprise, 0 lien."
    assert entity_description(drawing, "company:000000000") == ""


def test_the_graph_summary_counts_entities_links_and_flagged_entities(
    drawing: GraphDrawing,
) -> None:
    assert graph_summary(drawing) == "9 entités, 9 liens, 4 entités signalées"
    assert graph_summary(GraphDrawing()) == "Graphe vide"
