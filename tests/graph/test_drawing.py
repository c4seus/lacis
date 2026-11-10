import sqlite3
from datetime import UTC, date, datetime
from itertools import pairwise

import pytest

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.drawing import (
    MINIMUM_GAP,
    ROW_HEIGHTS,
    EdgeKind,
    GraphDrawing,
    GraphEdge,
    GraphNode,
    NodeShape,
    flagged_entities,
    graph_drawing,
    spread,
)
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import EntityKind


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def drawn_node(drawing: GraphDrawing, identifier: str) -> GraphNode:
    node = drawing.node(identifier)
    assert node is not None
    return node


def test_an_empty_investigation_draws_nothing(
    investigation_connection: sqlite3.Connection,
) -> None:
    assert graph_drawing(investigation_connection) == GraphDrawing()


def test_each_entity_kind_has_its_shape_and_size(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    expected = {
        scenario.acme: (EntityKind.COMPANY, NodeShape.ROUNDED_SQUARE, 34.0, "entreprise"),
        scenario.jean: (EntityKind.PERSON, NodeShape.CIRCLE, 30.0, "personne"),
        scenario.address: (EntityKind.ADDRESS, NodeShape.DIAMOND, 30.0, "adresse"),
        scenario.acme_office: (
            EntityKind.ESTABLISHMENT,
            NodeShape.SMALL_CIRCLE,
            14.0,
            "établissement",
        ),
        scenario.invest: (
            EntityKind.FOREIGN_COMPANY,
            NodeShape.HEXAGON,
            30.0,
            "entreprise étrangère",
        ),
    }
    for identifier, (kind, shape, size, kind_label) in expected.items():
        node = drawn_node(drawing, identifier)
        assert (node.kind, node.shape, node.size, node.kind_label) == (
            kind,
            shape,
            size,
            kind_label,
        )
    assert len(drawing.nodes) == 9


def test_labels_put_the_birth_month_and_the_town_on_a_second_line(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    assert drawn_node(drawing, scenario.jean).label == "Jean DUPONT\n1980-05"
    assert drawn_node(drawing, scenario.address).label == "12 RUE DES LILAS\n31000 TOULOUSE"
    assert drawn_node(drawing, scenario.acme).label == "ACME PLOMBERIE"
    assert drawn_node(drawing, scenario.acme_office).label == "Siège — TOULOUSE"


def test_labels_stay_on_one_line_without_birth_month_or_postcode(
    builder: InvestigationBuilder,
) -> None:
    builder.connection.execute(
        "UPDATE entity SET attributes = '{}' WHERE identifier = ?",
        (builder.person("Marie", "MARTIN"),),
    )
    builder.connection.commit()
    builder.address("CHEMIN DU MOULIN TOULOUSE")
    builder.address("5 PLACE DU MARCHE 31000", postcode="31000")
    labels = {node.label for node in graph_drawing(builder.connection).nodes}
    assert labels == {"Marie MARTIN", "CHEMIN DU MOULIN TOULOUSE", "5 PLACE DU MARCHE 31000"}


def test_closed_companies_and_establishments_are_marked(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    closed = {node.identifier for node in drawing.nodes if node.closed}
    assert closed == {scenario.dupont_services, scenario.dupont_office}


def test_companies_known_only_as_directors_are_partial(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    partial = {node.identifier for node in drawing.nodes if node.partial}
    assert partial == {scenario.holding}


def test_entities_are_drawn_in_rows_from_directors_to_addresses(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    rows = {
        scenario.jean: 0,
        scenario.jean_pierre: 0,
        scenario.holding: 0,
        scenario.invest: 0,
        scenario.acme: 1,
        scenario.dupont_services: 1,
        scenario.acme_office: 2,
        scenario.dupont_office: 2,
        scenario.address: 3,
    }
    for identifier, row in rows.items():
        assert drawn_node(drawing, identifier).y == ROW_HEIGHTS[row]


def test_entities_sit_near_their_neighbours_without_overlapping(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    acme = drawn_node(drawing, scenario.acme)
    dupont_services = drawn_node(drawing, scenario.dupont_services)
    acme_office = drawn_node(drawing, scenario.acme_office)
    dupont_office = drawn_node(drawing, scenario.dupont_office)
    address = drawn_node(drawing, scenario.address)
    assert acme_office.x == acme.x
    assert dupont_office.x == dupont_services.x
    assert address.x == (acme.x + dupont_services.x) / 2
    for row_height in ROW_HEIGHTS.values():
        row = sorted(node.x for node in drawing.nodes if node.y == row_height)
        assert all(right - left >= MINIMUM_GAP for left, right in pairwise(row))


def test_unknown_identifiers_have_no_node(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    assert drawing.node("company:000000000") is None
    assert drawing.require_node(scenario.acme).label == "ACME PLOMBERIE"
    with pytest.raises(KeyError):
        drawing.require_node("company:000000000")


def test_crowded_positions_spread_around_their_centre() -> None:
    assert spread({"a": 0.0, "b": 0.0, "c": 0.0}) == {
        "a": -MINIMUM_GAP,
        "b": 0.0,
        "c": MINIMUM_GAP,
    }
    assert spread({"a": 0.0, "b": 500.0}) == {"a": 0.0, "b": 500.0}
    start = (0.0 - MINIMUM_GAP + 200.0 - 2 * MINIMUM_GAP) / 3
    assert spread({"a": 0.0, "b": 0.0, "c": 200.0}) == pytest.approx(
        {"a": start, "b": start + MINIMUM_GAP, "c": start + 2 * MINIMUM_GAP}
    )


def edges_between(drawing: GraphDrawing, first: str, second: str) -> list[GraphEdge]:
    return [edge for edge in drawing.edges if {edge.source, edge.target} == {first, second}]


def test_mandates_are_drawn_from_the_director_with_the_role(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    [mandate] = edges_between(drawing, scenario.holding, scenario.acme)
    assert (mandate.kind, mandate.source, mandate.target, mandate.label) == (
        EdgeKind.DIRECTS,
        scenario.holding,
        scenario.acme,
        "Directeur général",
    )
    assert mandate.has_arrow


def test_establishments_are_tied_to_their_company_and_address_without_label(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    for first, second in (
        (scenario.acme_office, scenario.acme),
        (scenario.acme_office, scenario.address),
    ):
        [edge] = edges_between(drawing, first, second)
        assert (edge.kind, edge.label, edge.has_arrow) == (EdgeKind.STRUCTURE, "", False)


def test_a_confirmed_homonym_is_drawn_as_the_same_person(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(builder.connection)
    [identity] = edges_between(drawing, scenario.jean, scenario.jean_pierre)
    assert (identity.kind, identity.label, identity.has_arrow) == (
        EdgeKind.IDENTITY,
        "même personne",
        False,
    )


def test_a_registered_office_reached_through_an_establishment_is_not_drawn_twice(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    other_address = builder.address("3 RUE DU PORT 31000 TOULOUSE", postcode="31000")
    builder.registered_office(scenario.holding, other_address)
    drawing = graph_drawing(builder.connection)
    assert edges_between(drawing, scenario.acme, scenario.address) == []
    [office] = edges_between(drawing, scenario.holding, other_address)
    assert office.kind is EdgeKind.STRUCTURE
    assert len(drawing.edges) == 10


def test_an_edge_knows_its_ends() -> None:
    edge = GraphEdge("link:1", EdgeKind.DIRECTS, "person:1", "company:1", "Gérant")
    assert edge.touches("person:1")
    assert not edge.touches("address:1")
    assert edge.other_end("person:1") == "company:1"
    assert edge.other_end("company:1") == "person:1"


def signal(subject: str, severity: Severity, *justifying_entities: str) -> Signal:
    return Signal(
        "phoenix_scheme", "Schéma phénix", subject, severity, 0.85, "", justifying_entities
    )


def report(*signals: Signal) -> SignalReport:
    return SignalReport(signals, 1, date(2026, 11, 10), "", datetime(2026, 11, 10, tzinfo=UTC))


def test_flagged_entities_keep_their_highest_severity() -> None:
    severities = flagged_entities(
        report(
            signal("company:1", Severity.LOW, "person:1"),
            signal("company:2", Severity.HIGH, "person:1", "company:1"),
            signal("company:1", Severity.MEDIUM),
        )
    )
    assert severities == {
        "company:1": Severity.HIGH,
        "company:2": Severity.HIGH,
        "person:1": Severity.HIGH,
    }
    assert flagged_entities(None) == {}
    assert flagged_entities(report()) == {}


def test_signal_subjects_and_their_evidence_are_flagged_in_the_drawing(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    drawing = graph_drawing(
        builder.connection,
        report(signal(scenario.dupont_services, Severity.HIGH, scenario.acme, scenario.jean)),
    )
    flagged = {node.identifier: node.severity for node in drawing.nodes if node.severity}
    assert flagged == {
        scenario.dupont_services: Severity.HIGH,
        scenario.acme: Severity.HIGH,
        scenario.jean: Severity.HIGH,
    }
    assert all(node.severity is None for node in graph_drawing(builder.connection).nodes)
