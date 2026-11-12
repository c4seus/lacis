import sqlite3

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.layout import Point
from lacis.graph.navigation import Direction, linked_towards, starting_entity


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


@pytest.fixture
def points(drawing: GraphDrawing) -> dict[str, Point]:
    return {node.identifier: (node.x, node.y) for node in drawing.nodes}


def everything(drawing: GraphDrawing) -> set[str]:
    return {node.identifier for node in drawing.nodes}


def test_the_arrows_follow_the_links_in_their_direction(
    drawing: GraphDrawing, points: dict[str, Point], scenario: PlumbersScenario
) -> None:
    shown = everything(drawing)
    assert linked_towards(drawing, points, scenario.acme, Direction.DOWN, shown) == (
        scenario.acme_office
    )
    assert linked_towards(drawing, points, scenario.acme_office, Direction.UP, shown) == (
        scenario.acme
    )
    assert linked_towards(drawing, points, scenario.acme_office, Direction.DOWN, shown) == (
        scenario.address
    )
    assert linked_towards(drawing, points, scenario.address, Direction.RIGHT, shown) == (
        scenario.dupont_office
    )
    assert linked_towards(drawing, points, scenario.jean_pierre, Direction.RIGHT, shown) == (
        scenario.jean
    )
    assert linked_towards(drawing, points, scenario.jean, Direction.LEFT, shown) == (
        scenario.jean_pierre
    )


def test_the_closest_link_in_the_direction_wins(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    points = {node.identifier: (0.0, 0.0) for node in drawing.nodes}
    points[scenario.holding] = (-200.0, -150.0)
    points[scenario.invest] = (-30.0, -300.0)
    points[scenario.jean_pierre] = (40.0, -150.0)
    points[scenario.acme_office] = (0.0, 200.0)
    shown = everything(drawing)
    assert linked_towards(drawing, points, scenario.acme, Direction.UP, shown) == (
        scenario.jean_pierre
    )
    assert linked_towards(drawing, points, scenario.acme, Direction.LEFT, shown) == (
        scenario.holding
    )


def test_no_link_in_the_direction_or_hidden_means_no_move(
    drawing: GraphDrawing, points: dict[str, Point], scenario: PlumbersScenario
) -> None:
    shown = everything(drawing)
    assert linked_towards(drawing, points, scenario.address, Direction.DOWN, shown) is None
    without_office = shown - {scenario.acme_office}
    assert linked_towards(drawing, points, scenario.acme, Direction.DOWN, without_office) is None


def test_the_first_arrow_starts_from_the_highest_flagged_entity(
    drawing: GraphDrawing, points: dict[str, Point], scenario: PlumbersScenario
) -> None:
    shown = everything(drawing)
    first = starting_entity(drawing, points, shown)
    assert first in {scenario.jean, scenario.jean_pierre}
    flagged = {scenario.jean, scenario.jean_pierre, scenario.acme, scenario.dupont_services}
    assert starting_entity(drawing, points, shown - flagged) in {
        scenario.holding,
        scenario.invest,
    }
    assert starting_entity(drawing, points, set()) is None


def test_an_entity_on_top_of_another_is_not_a_direction(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    points = {node.identifier: (0.0, 0.0) for node in drawing.nodes}
    assert (
        linked_towards(drawing, points, scenario.acme, Direction.UP, everything(drawing)) is None
    )
