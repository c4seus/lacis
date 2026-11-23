import csv
import sqlite3
from pathlib import Path

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.exports.graph_snapshot import graph_snapshot
from lacis.exports.json_export import ExportScope
from lacis.exports.maltego import maltego_rows, write_maltego_csv

URL = "https://company_register.example"
ENTITY_TYPES = [
    "maltego.Company",
    "maltego.Company",
    "maltego.Person",
    "maltego.Person",
    "maltego.Location",
    "maltego.Location",
    "maltego.Location",
    "maltego.Location",
    "maltego.Company",
    "maltego.Company",
]
TYPES = [*(cell for entity_type in ENTITY_TYPES for cell in (entity_type, "")), "", ""]


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def rows_of(builder: InvestigationBuilder, scenario: PlumbersScenario) -> list[list[str]]:
    return maltego_rows(
        graph_snapshot(builder.connection, phoenix_report(scenario), ExportScope())
    )


def entities_in(row: list[str]) -> list[tuple[int, str, str]]:
    return [
        (column // 2, row[column], row[column + 1])
        for column in range(0, len(ENTITY_TYPES) * 2, 2)
        if row[column]
    ]


def test_the_first_row_types_each_entity_column_and_leaves_its_sources_untyped(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    assert rows_of(builder, scenario)[0] == TYPES


def test_every_link_is_a_row_with_its_two_entities_their_sources_and_its_role(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = rows_of(builder, scenario)[1:]
    assert len(rows) == len(builder.graph_store.links())
    assert all(len(entities_in(row)) == 2 for row in rows)
    president = next(row for row in rows if "Jean DUPONT" in row and row[-2] == "Président")
    assert entities_in(president) == [(1, "DUPONT SERVICES", URL), (2, "Jean DUPONT", URL)]
    assert president[-1] == URL
    holding = next(row for row in rows if row[-2] == "Directeur général")
    assert entities_in(holding) == [(0, "HOLDING DUPONT", URL), (1, "ACME PLOMBERIE", URL)]


def test_a_link_decided_by_the_investigator_says_so_as_its_source(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    same_person = next(row for row in rows_of(builder, scenario) if row[-2] == "Même personne")
    assert entities_in(same_person) == [
        (2, "Jean Pierre DUPONT", URL),
        (3, "Jean DUPONT", URL),
    ]
    assert same_person[-1] == "Décision de l'enquêteur"


def test_an_entity_without_links_has_a_row_of_its_own(builder: InvestigationBuilder) -> None:
    builder.foreign_company("NORTH LTD")
    rows = maltego_rows(graph_snapshot(builder.connection, None, ExportScope()))
    assert rows[1:] == [[*[""] * 16, "NORTH LTD", URL, "", "", "", ""]]


def test_the_csv_is_written_in_utf_8_with_quoted_cells(
    builder: InvestigationBuilder, tmp_path: Path
) -> None:
    builder.company('SOCIÉTÉ "DU NORD", LILLE')
    destination = tmp_path / "maltego.csv"
    write_maltego_csv(graph_snapshot(builder.connection, None, ExportScope()), destination)
    text = destination.read_bytes()
    assert b"\r" not in text
    with destination.open(encoding="utf-8", newline="") as source:
        rows = list(csv.reader(source))
    assert rows[0] == TYPES
    assert rows[1][:2] == ['SOCIÉTÉ "DU NORD", LILLE', URL]
    assert '"SOCIÉTÉ ""DU NORD"", LILLE"'.encode() in text
