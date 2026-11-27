import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from graph_scenario import plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.exports.formats import (
    EXPORT_FORMATS,
    GEXF_FORMAT,
    HTML_GRAPH_FORMAT,
    JSON_FORMAT,
    MALTEGO_FORMAT,
    MARKDOWN_REPORT_FORMAT,
    OBSIDIAN_FORMAT,
    PDF_REPORT_FORMAT,
    ExportFormat,
    export_format,
)
from lacis.exports.json_export import FORMAT_NAME, ExportScope
from lacis.storage.investigations import InvestigationLibrary

EXPORTED_AT = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)


def test_every_format_has_a_key_a_menu_entry_and_an_extension() -> None:
    assert [candidate.key for candidate in EXPORT_FORMATS] == [
        "markdown_report",
        "pdf_report",
        "json",
        "obsidian",
        "gexf",
        "maltego",
        "html_graph",
    ]
    assert [candidate.menu_text for candidate in EXPORT_FORMATS] == [
        "&Rapport Markdown…",
        "Rapport &PDF…",
        "&JSON…",
        "&Obsidian…",
        "&Gephi…",
        "&Maltego…",
        "Format &HTML…",
    ]
    assert [candidate.extension for candidate in EXPORT_FORMATS] == [
        ".md",
        ".pdf",
        ".json",
        "",
        ".gexf",
        ".csv",
        ".html",
    ]
    assert [candidate.folder for candidate in EXPORT_FORMATS] == [
        False,
        False,
        False,
        True,
        False,
        False,
        False,
    ]
    assert export_format("obsidian") is OBSIDIAN_FORMAT
    assert export_format("json") is JSON_FORMAT
    assert export_format("markdown_report") is MARKDOWN_REPORT_FORMAT
    assert export_format("pdf_report") is PDF_REPORT_FORMAT


def test_the_json_format_writes_the_investigation_opened(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    destination = tmp_path / "faux-plombiers-31.json"
    with library.open("faux-plombiers-31") as opened:
        scenario = plumbers_scenario(InvestigationBuilder(opened.connection))
        JSON_FORMAT.write(opened, None, ExportScope(), destination, EXPORTED_AT)
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert document["format"] == FORMAT_NAME
    assert document["investigation"]["name"] == "faux-plombiers-31"
    assert document["exported_at"] == "2026-11-19T10:00:00+00:00"
    assert scenario.acme in {entity["identifier"] for entity in document["entities"]}
    assert document["signals"] == []


def test_the_markdown_report_format_writes_the_report_of_the_investigation(
    tmp_path: Path,
) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    destination = tmp_path / "rapport.md"
    with library.open("faux-plombiers-31") as opened:
        plumbers_scenario(InvestigationBuilder(opened.connection))
        MARKDOWN_REPORT_FORMAT.write(opened, None, ExportScope(), destination, EXPORTED_AT)
    text = destination.read_text(encoding="utf-8")
    assert text.startswith("# Rapport d'enquête : faux-plombiers-31\n")
    assert "**Question :** Qui se cache derrière les plombiers ?" in text
    assert "Il couvre toute l'enquête : 9 entités" in text


def test_the_obsidian_format_writes_a_vault_folder(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    destination = tmp_path / "coffre"
    with library.open("faux-plombiers-31") as opened:
        plumbers_scenario(InvestigationBuilder(opened.connection))
        OBSIDIAN_FORMAT.write(opened, None, ExportScope(), destination, EXPORTED_AT)
    index = destination / "Enquête faux-plombiers-31.md"
    assert "**Question :** Qui se cache derrière les plombiers ?" in index.read_text("utf-8")
    assert (destination / "Entreprises" / "ACME PLOMBERIE.md").is_file()


@pytest.mark.parametrize(
    ("export", "file_name", "expected"),
    [
        (GEXF_FORMAT, "graphe.gexf", "<title>faux-plombiers-31</title>"),
        (MALTEGO_FORMAT, "maltego.csv", "maltego.Company,,maltego.Company,,maltego.Person"),
        (HTML_GRAPH_FORMAT, "graphe.html", "<title>Lacis : faux-plombiers-31</title>"),
    ],
)
def test_the_graph_formats_write_the_graph_of_the_investigation(
    tmp_path: Path, export: ExportFormat, file_name: str, expected: str
) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    destination = tmp_path / file_name
    with library.open("faux-plombiers-31") as opened:
        plumbers_scenario(InvestigationBuilder(opened.connection))
        export.write(opened, None, ExportScope(), destination, EXPORTED_AT)
    text = destination.read_text(encoding="utf-8")
    assert expected in text
    assert "ACME PLOMBERIE" in text
