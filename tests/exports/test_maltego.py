import csv
import sqlite3
from pathlib import Path

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.exports.graph_snapshot import graph_snapshot
from lacis.exports.json_export import ExportScope
from lacis.exports.maltego import maltego_rows, write_maltego_csv

TYPES = [
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
    "",
]


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


def filled(row: list[str]) -> list[tuple[int, str]]:
    return [(column, cell) for column, cell in enumerate(row[:-1]) if cell]


def test_the_first_row_gives_the_maltego_type_of_each_column(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    assert rows_of(builder, scenario)[0] == TYPES


def test_every_link_is_a_row_with_its_two_entities_and_its_label(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = rows_of(builder, scenario)[1:]
    assert len(rows) == len(builder.graph_store.links())
    assert all(len(filled(row)) == 2 for row in rows)
    assert ["", "DUPONT SERVICES", "Jean DUPONT", "", "", "", "", "", "", "", "Président"] in rows
    assert ["HOLDING DUPONT", "ACME PLOMBERIE", *[""] * 8, "Directeur général"] in rows
    same_person = next(row for row in rows if row[-1] == "Même personne")
    assert filled(same_person) == [(2, "Jean Pierre DUPONT"), (3, "Jean DUPONT")]


def test_an_entity_without_links_has_a_row_of_its_own(builder: InvestigationBuilder) -> None:
    builder.foreign_company("NORTH LTD")
    rows = maltego_rows(graph_snapshot(builder.connection, None, ExportScope()))
    assert rows[1:] == [[*[""] * 8, "NORTH LTD", "", ""]]


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
    assert rows[1][0] == 'SOCIÉTÉ "DU NORD", LILLE'
    assert '"SOCIÉTÉ ""DU NORD"", LILLE"'.encode() in text
