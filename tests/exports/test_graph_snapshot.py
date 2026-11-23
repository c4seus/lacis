import sqlite3
from datetime import UTC, date, datetime

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.exports.graph_snapshot import GraphSnapshot, graph_snapshot
from lacis.exports.json_export import ExportScope
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import EntityKind, LinkKind
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    TagStore(builder.connection).add(scenario.acme, "réseau Dupont")
    TagStore(builder.connection).add(scenario.acme, "prioritaire")
    VerdictStore(builder.connection).save(scenario.acme, Verdict.SUSPECT, "Reprise.")
    return scenario


def two_signals(scenario: PlumbersScenario) -> SignalReport:
    phoenix = phoenix_report(scenario).signals[0]
    low = Signal(
        "mass_domiciliation",
        "Domiciliation de masse",
        scenario.dupont_services,
        Severity.LOW,
        0.95,
        "",
        (),
    )
    return SignalReport(
        (low, phoenix), 1, date(2026, 11, 10), "", datetime(2026, 11, 10, tzinfo=UTC)
    )


def snapshot_of(
    builder: InvestigationBuilder, scenario: PlumbersScenario, shown: frozenset[str] | None = None
) -> GraphSnapshot:
    return graph_snapshot(builder.connection, two_signals(scenario), ExportScope(shown))


def test_the_snapshot_keeps_every_entity_and_link(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    snapshot = snapshot_of(builder, scenario)
    assert len(snapshot.nodes) == len(builder.graph_store.entities())
    assert len(snapshot.edges) == len(builder.graph_store.links())
    assert snapshot.linked() == {node.identifier for node in snapshot.nodes}


def test_a_node_carries_its_facts_annotations_and_signals(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    nodes = {node.identifier: node for node in snapshot_of(builder, scenario).nodes}
    acme = nodes[scenario.acme]
    assert acme.kind is EntityKind.COMPANY
    assert acme.kind_label == "entreprise"
    assert acme.facts == ("SIREN 100 000 000", "Créée le 01/03/2021")
    assert acme.verdict == "Suspect"
    assert acme.tags == ("prioritaire", "réseau Dupont")
    assert not acme.closed
    assert acme.signals == ()
    assert acme.severity == ""
    assert acme.score == 0.0
    services = nodes[scenario.dupont_services]
    assert services.closed
    assert [signal.rule for signal in services.signals] == ["mass_domiciliation", "phoenix_scheme"]
    assert services.severity == "Forte"
    assert services.score == 0.95


def test_namesakes_get_distinct_names(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    names = [node.name for node in snapshot_of(builder, scenario).nodes]
    assert len(set(names)) == len(names)
    assert "Siège — TOULOUSE (SIRET 100 000 000 00015)" in names


def test_every_link_gets_a_label_read_from_its_source(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    labels = {(edge.kind, edge.label) for edge in snapshot_of(builder, scenario).edges}
    assert labels == {
        (LinkKind.MANDATE, "Président"),
        (LinkKind.MANDATE, "Directeur général"),
        (LinkKind.MANDATE, "Associé"),
        (LinkKind.REGISTERED_OFFICE, "Siège social"),
        (LinkKind.LOCATED_AT, "Situé à"),
        (LinkKind.ESTABLISHMENT_OF, "Établissement de"),
        (LinkKind.SAME_PERSON, "Même personne"),
    }


def test_the_filtered_view_keeps_the_entities_shown_and_their_links(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown = frozenset({scenario.acme, scenario.jean_pierre, scenario.invest})
    snapshot = snapshot_of(builder, scenario, shown)
    assert {node.identifier for node in snapshot.nodes} == shown
    assert {edge.label for edge in snapshot.edges} == {"Président", "Associé"}


def test_a_snapshot_without_signals_gives_no_score(builder: InvestigationBuilder) -> None:
    acme = builder.company("ACME PLOMBERIE")
    snapshot = graph_snapshot(builder.connection, None, ExportScope())
    assert [(node.identifier, node.signals, node.verdict) for node in snapshot.nodes] == [
        (acme, (), "")
    ]
    assert snapshot.linked() == set()


def test_names_keep_the_label_on_one_line(builder: InvestigationBuilder) -> None:
    builder.company("SOCIÉTÉ  A/B\nNORD")
    snapshot = graph_snapshot(builder.connection, None, ExportScope())
    assert [node.name for node in snapshot.nodes] == ["SOCIÉTÉ A/B NORD"]
