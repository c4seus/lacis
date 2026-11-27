import importlib
import re
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, StreamObject

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.tokens import LIGHT_THEME
from lacis.details import written_moment
from lacis.exports import pdf_report
from lacis.exports.json_export import ExportScope
from lacis.exports.pdf_report import (
    UNAVAILABLE_TEXT,
    PdfUnavailableError,
    css_string,
    report_html,
    write_pdf_report,
)
from lacis.exports.report import ReportBuilder, ReportContent
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.verdicts import Verdict, VerdictStore

PRODUCED_AT = datetime(2026, 11, 26, 9, 30, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers du 12 rue des Lilas ?",
    datetime(2026, 11, 13, 9, 0, tzinfo=UTC),
    Path("faux-plombiers-31"),
)
SECTIONS = (
    "Rapport d'enquête : faux-plombiers-31",
    "Synthèse",
    "Méthode",
    "Constats",
    "Signaux",
    "Notes",
    "Réserves",
    "Annexe : preuves",
)
FONT_FILE_KEYS = {"/FontFile", "/FontFile2", "/FontFile3"}


def weasyprint_available() -> bool:
    try:
        importlib.import_module("weasyprint")
    except (ImportError, OSError):
        return False
    return True


needs_weasyprint = pytest.mark.skipif(
    not weasyprint_available(), reason="WeasyPrint or Pango is not installed"
)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    VerdictStore(builder.connection).save(scenario.acme, Verdict.SUSPECT, "Reprise d'activité.")
    VerdictStore(builder.connection).save(scenario.dupont_services, Verdict.CONFIRMED, "")
    NoteStore(builder.connection).save(
        scenario.acme,
        "Même gérant que **DUPONT SERVICES**.\n\n"
        '![logo](https://example.org/logo.png) <img src="https://example.org/pixel.png">'
        "<script>alert(1)</script>",
    )
    return scenario


def content_of(builder: InvestigationBuilder, scenario: PlumbersScenario) -> ReportContent:
    report_builder = ReportBuilder(builder.connection, phoenix_report(scenario), ExportScope())
    return report_builder.content(INVESTIGATION, PRODUCED_AT)


def dictionary(value: Any) -> DictionaryObject:
    found = value.get_object()
    assert isinstance(found, DictionaryObject)
    return found


def embedded_font_programs(pdf: PdfReader) -> list[bytes]:
    programs = []
    for page in pdf.pages:
        for font in dictionary(dictionary(page["/Resources"])["/Font"]).values():
            descendants = dictionary(font)["/DescendantFonts"].get_object()
            assert isinstance(descendants, ArrayObject)
            descriptor = dictionary(dictionary(descendants[0])["/FontDescriptor"])
            for key in FONT_FILE_KEYS & descriptor.keys():
                program = descriptor[key].get_object()
                assert isinstance(program, StreamObject)
                programs.append(program.get_data())
    return programs


def font_named(program: bytes, name: str) -> bool:
    return name.encode("utf-16-be") in program


def structure_tags(node: Any) -> Iterator[str]:
    found = node.get_object() if hasattr(node, "get_object") else node
    if isinstance(found, ArrayObject):
        for child in found:
            yield from structure_tags(child)
    elif isinstance(found, DictionaryObject):
        if "/S" in found:
            yield str(found["/S"])
        if "/K" in found:
            yield from structure_tags(found["/K"])


@pytest.fixture
def pdf(builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path) -> PdfReader:
    destination = tmp_path / "rapport.pdf"
    write_pdf_report(content_of(builder, scenario), destination)
    return PdfReader(destination)


@needs_weasyprint
def test_the_pdf_is_tagged_for_screen_readers(pdf: PdfReader) -> None:
    catalog = pdf.root_object
    assert dictionary(catalog["/MarkInfo"])["/Marked"]
    assert str(catalog["/Lang"]) == "fr"
    assert pdf.metadata is not None
    assert pdf.metadata.title == "Rapport d'enquête : faux-plombiers-31"
    tags = set(structure_tags(catalog["/StructTreeRoot"]))
    assert {"/Document", "/H1", "/H2", "/H3", "/P", "/L", "/LI", "/Table", "/TH", "/TD"} <= tags
    assert "/BlockQuote" in tags


@needs_weasyprint
def test_every_page_gives_the_investigation_the_date_and_its_number(pdf: PdfReader) -> None:
    pages = [page.extract_text() for page in pdf.pages]
    assert len(pages) >= 2
    for number, text in enumerate(pages, start=1):
        assert "faux-plombiers-31" in text
        assert f"Produit le {written_moment(PRODUCED_AT)}" in text
        assert f"Page {number} sur {len(pages)}" in text


@needs_weasyprint
def test_the_pdf_has_every_section_of_the_report_in_order(pdf: PdfReader) -> None:
    lines = [line.strip() for page in pdf.pages for line in page.extract_text().splitlines()]
    position = -1
    for section in SECTIONS:
        position = lines.index(section, position + 1)
    assert "Preuves : R1" in lines


@needs_weasyprint
def test_the_pdf_uses_the_fonts_of_lacis(pdf: PdfReader) -> None:
    programs = embedded_font_programs(pdf)
    assert any(font_named(program, "Inter Regular") for program in programs)
    assert any(font_named(program, "Inter SemiBold") for program in programs)


@needs_weasyprint
def test_a_longer_investigation_gives_more_pages(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    short = tmp_path / "court.pdf"
    write_pdf_report(content_of(builder, scenario), short)
    for number in range(60):
        company = builder.company(f"PLOMBERIE {number:02}")
        VerdictStore(builder.connection).save(company, Verdict.TO_CHECK, "Même adresse.")
    longer = tmp_path / "long.pdf"
    write_pdf_report(content_of(builder, scenario), longer)
    assert len(PdfReader(longer).pages) > len(PdfReader(short).pages)


def test_the_page_carries_the_style_fonts_and_colours_of_lacis(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    page = report_html(content_of(builder, scenario))
    assert page.startswith('<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">')
    assert "<title>Rapport d&#x27;enquête : faux-plombiers-31</title>" in page
    assert page.count("src:url(data:font/ttf;base64,") == 3
    assert f"--accent:{LIGHT_THEME.colours.accent};" in page
    assert '@top-left{content:"faux-plombiers-31";' in page
    assert f'@top-right{{content:"Produit le {written_moment(PRODUCED_AT)}";' in page
    assert '@bottom-right{content:"Page " counter(page) " sur " counter(pages);' in page
    assert "<h1>Rapport d'enquête : faux-plombiers-31</h1>" in page


def test_the_page_keeps_the_anchors_of_the_appendix(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    page = report_html(content_of(builder, scenario))
    assert '<a href="#preuve-1">R1</a>' in page
    assert '<a id="preuve-1"></a><strong>R1</strong>' in page
    assert "⟦" not in page


def test_notes_cannot_load_anything_or_run_a_script(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    page = report_html(content_of(builder, scenario))
    assert "<img" not in page
    assert "<script" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert re.findall(r"<[^>]*\ssrc=", page) == []
    assert "&lt;img src=" in page


def test_texts_in_the_margins_are_valid_css_strings() -> None:
    assert css_string('Dupont "&" fils\\\nSAS') == '"Dupont \\"&\\" fils\\\\ SAS"'


def test_the_pdf_cannot_be_written_without_weasyprint(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_library() -> ModuleType:
        raise OSError("cannot load library 'libgobject-2.0-0'")

    monkeypatch.setattr(pdf_report, "weasyprint_module", missing_library)
    destination = tmp_path / "rapport.pdf"
    with pytest.raises(PdfUnavailableError, match=UNAVAILABLE_TEXT):
        write_pdf_report(content_of(builder, scenario), destination)
    assert not destination.exists()
