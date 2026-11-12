import sqlite3
from datetime import UTC, datetime

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.details import BadgeTone
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import Attributes, Entity, EntityKind, Link, LinkKind
from lacis.tables import (
    NO_SCORE_TEXT,
    EntityRow,
    EntityStatus,
    entities_summary,
    entity_rows,
    entity_status,
    strongest_marks,
)

REQUESTED_AT = datetime(2026, 11, 2, 8, 9, 31, tzinfo=UTC)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def rows_by_identifier(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> dict[str, EntityRow]:
    rows = entity_rows(builder.connection, phoenix_report(scenario))
    return {row.identifier: row for row in rows}


def test_each_entity_has_its_kind_status_score_and_links(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = rows_by_identifier(builder, scenario)
    assert len(rows) == 9
    dupont = rows[scenario.dupont_services]
    assert dupont.label == "DUPONT SERVICES"
    assert dupont.kind_label == "Entreprise"
    assert dupont.status == EntityStatus("Fermée", BadgeTone.CLOSED)
    assert dupont.status_text == "Fermée"
    assert dupont.severity is Severity.HIGH
    assert dupont.written_score == "0,85"
    assert dupont.spoken_score == "score 0,85, gravité forte"
    assert dupont.flagged
    assert dupont.links == 3
    assert rows[scenario.acme].status_text == "Active"
    assert rows[scenario.acme].links == 5
    assert rows[scenario.jean].links == 1
    assert rows[scenario.jean].flagged
    assert rows[scenario.invest].status_text == "Étranger"
    assert rows[scenario.dupont_office].status_text == "Fermé"
    assert rows[scenario.acme_office].status is None
    address = rows[scenario.address]
    assert address.status_text == ""
    assert address.links == 4
    assert not address.flagged
    assert address.written_score == NO_SCORE_TEXT
    assert address.spoken_score == "aucun signal"
    assert address.sort_score == (-1, -1.0)
    assert dupont.sort_score == (Severity.HIGH.rank, 0.85)


def test_without_signals_no_entity_is_flagged(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = entity_rows(builder.connection, None)
    assert not any(row.flagged for row in rows)
    assert entities_summary(tuple(rows)) == "9 entités · 0 signalée"


def test_an_entity_keeps_its_strongest_signal(scenario: PlumbersScenario) -> None:
    weak = Signal("rule", "Faible", scenario.acme, Severity.LOW, 0.95, "", ())
    strong = Signal("rule", "Forte", scenario.acme, Severity.HIGH, 0.4, "", ())
    medium = Signal("rule", "Moyenne", scenario.acme, Severity.MEDIUM, 0.6, "", ())
    report = SignalReport((weak, strong, medium), 1, REQUESTED_AT.date(), "", REQUESTED_AT)
    mark = strongest_marks(report)[scenario.acme]
    assert (mark.severity, mark.score) == (Severity.HIGH, 0.4)
    assert (
        entities_summary((EntityRow("a", EntityKind.PERSON, "A", None, Severity.LOW, 0.2, 0),))
        == "1 entité · 1 signalée"
    )
    assert (
        entities_summary(
            tuple(
                EntityRow(name, EntityKind.PERSON, name, None, Severity.LOW, 0.2, 0)
                for name in "ab"
            )
        )
        == "2 entités · 2 signalées"
    )


def entity(kind: EntityKind, attributes: Attributes) -> Entity:
    return Entity(f"{kind.value}:1", kind, "X", attributes, REQUESTED_AT, REQUESTED_AT)


def mandate_from(company: Entity) -> Link:
    return Link(
        "link:1",
        LinkKind.MANDATE,
        company.identifier,
        "person:1",
        "Gérant",
        REQUESTED_AT,
        REQUESTED_AT,
    )


def test_a_company_known_only_as_director_is_partial() -> None:
    company = entity(EntityKind.COMPANY, {})
    assert entity_status(company, [mandate_from(company)]) == EntityStatus(
        "Partielle", BadgeTone.OUTLINE
    )
    assert entity_status(company, []) is None
    assert entity_status(entity(EntityKind.ESTABLISHMENT, {"is_open": True}), []) == (
        EntityStatus("Ouvert", BadgeTone.ACTIVE)
    )
