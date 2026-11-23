import json
import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis import __version__
from lacis.design.tokens import DARK_THEME, LIGHT_THEME
from lacis.details import written_moment
from lacis.exports.html_graph import (
    TEMPLATE_DIRECTORY,
    HtmlGraph,
    html_page,
    placed_drawing,
    write_html_graph,
)
from lacis.exports.json_export import ExportScope
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.notices import NoticeFamily
from lacis.storage.positions import Position, PositionStore
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore

EXPORTED_AT = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers ?",
    datetime(2026, 11, 13, 9, 0, tzinfo=UTC),
    Path("faux-plombiers-31"),
)
DATA_BLOCK = re.compile(
    r'<script type="application/json" id="lacis-data">(.*?)</script>', re.DOTALL
)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    connection = builder.connection
    VerdictStore(connection).save(scenario.acme, Verdict.SUSPECT, "Reprise d'activité.")
    TagStore(connection).add(scenario.acme, "réseau Dupont")
    NoteStore(connection).save(scenario.acme, "Même gérant.\n</script><b>gras</b>")
    builder.notice(scenario.dupont_services, NoticeFamily.INSOLVENCY, date(2022, 11, 3))
    return scenario


def page_of(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    destination: Path,
    shown: frozenset[str] | None = None,
) -> str:
    graph = HtmlGraph(builder.connection, phoenix_report(scenario), ExportScope(shown))
    write_html_graph(graph, INVESTIGATION, destination, EXPORTED_AT)
    return destination.read_text(encoding="utf-8")


def data_of(page: str) -> Any:
    found = DATA_BLOCK.search(page)
    assert found is not None
    return json.loads(found[1])


def node_of(data: Any, identifier: str) -> Any:
    return next(node for node in data["nodes"] if node["id"] == identifier)


def test_the_page_loads_nothing_from_outside_the_file(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    page = page_of(builder, scenario, tmp_path / "graphe.html")
    assert "default-src 'none'" in page
    assert '<meta name="referrer" content="no-referrer">' in page
    outside_data = DATA_BLOCK.sub("", page)
    assert re.findall(r"""\b(?:src|href)\s*=\s*["'](?!#)""", outside_data) == []
    assert "<link" not in outside_data
    assert "@import" not in outside_data
    assert "url(" not in outside_data.replace("url(#arrow)", "")
    assert "fetch(" not in outside_data
    assert "XMLHttpRequest" not in outside_data
    assert "{{" not in outside_data


def test_the_page_inlines_its_style_script_and_themes(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    page = page_of(builder, scenario, tmp_path / "graphe.html")
    assert (TEMPLATE_DIRECTORY / "graph.css").read_text(encoding="utf-8") in page
    assert (TEMPLATE_DIRECTORY / "graph.js").read_text(encoding="utf-8") in page
    assert f"--background:{LIGHT_THEME.colours.background};" in page
    assert f"--background:{DARK_THEME.colours.background};" in page
    assert '@media (prefers-color-scheme: dark){:root:not([data-theme="light"])' in page
    assert ':root[data-theme="dark"]{' in page
    assert '--font:Inter, "Segoe UI",' in page
    assert "<title>Lacis : faux-plombiers-31</title>" in page
    assert b"\r" not in (tmp_path / "graphe.html").read_bytes()


def test_the_page_carries_the_investigation_and_its_graph(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    data = data_of(page_of(builder, scenario, tmp_path / "graphe.html"))
    assert data["investigation"] == {
        "name": "faux-plombiers-31",
        "question": "Qui se cache derrière les plombiers ?",
        "exported": written_moment(EXPORTED_AT),
        "version": __version__,
        "filtered": False,
    }
    assert len(data["nodes"]) == len(builder.graph_store.entities())
    identifiers = {node["id"] for node in data["nodes"]}
    assert data["edges"]
    for edge in data["edges"]:
        assert {edge["source"], edge["target"]} <= identifiers
        assert edge["kind"] in {"directs", "structure", "identity"}
    assert {"kind": "directs", "label": "Président"}.items() <= next(
        edge for edge in data["edges"] if edge["source"] == scenario.jean
    ).items()


def test_each_node_carries_its_drawing_and_its_details(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    data = data_of(page_of(builder, scenario, tmp_path / "graphe.html"))
    acme = node_of(data, scenario.acme)
    assert acme["label"] == "ACME PLOMBERIE"
    assert (acme["kind"], acme["kindLabel"], acme["shape"], acme["size"]) == (
        "company",
        "entreprise",
        "rounded_square",
        34.0,
    )
    assert isinstance(acme["x"], float)
    assert isinstance(acme["y"], float)
    assert acme["facts"] == ["SIREN 100 000 000", "Créée le 01/03/2021"]
    assert acme["verdict"] == {"label": "Suspect", "reason": "Reprise d'activité."}
    assert acme["tags"] == ["réseau Dupont"]
    assert acme["note"] == "Même gérant.\n</script><b>gras</b>"
    assert {"id": scenario.jean_pierre, "role": "Président", "closed": False}.items() <= next(
        link for link in acme["links"] if link["id"] == scenario.jean_pierre
    ).items()
    assert [signal["title"] for signal in acme["signals"]] == ["Schéma phénix"]
    assert acme["signals"][0]["level"] == "high"
    assert acme["sources"][0]["name"] == "Recherche d'entreprises"
    services = node_of(data, scenario.dupont_services)
    assert services["closed"]
    assert services["severity"] == "high"
    assert services["notices"][0]["family"] == "Procédure collective"
    assert services["notices"][0]["url"].startswith("https://")
    assert node_of(data, scenario.holding)["verdict"] is None


def test_text_from_the_investigation_cannot_break_out_of_the_data(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    page = page_of(builder, scenario, tmp_path / "graphe.html")
    assert page.count("</script>") == 2
    assert "\\u003c/script>\\u003cb>gras\\u003c/b>" in page


def test_placeholders_in_the_investigation_are_kept_as_written() -> None:
    page = html_page({"label": "{{style}}"}, "{{script}} <b>")
    assert "<title>{{script}} &lt;b&gt;</title>" in page
    assert '{"label":"{{style}}"}' in page


def test_the_filtered_view_keeps_only_the_entities_shown(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    shown = frozenset({scenario.acme, scenario.jean_pierre})
    data = data_of(page_of(builder, scenario, tmp_path / "graphe.html", shown))
    assert {node["id"] for node in data["nodes"]} == shown
    assert [(edge["source"], edge["target"]) for edge in data["edges"]] == [
        (scenario.jean_pierre, scenario.acme)
    ]
    assert [link["id"] for link in node_of(data, scenario.acme)["links"]] == [scenario.jean_pierre]
    assert data["investigation"]["filtered"]


def test_stored_positions_are_kept_and_others_are_laid_out_without_being_saved(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    store = PositionStore(builder.connection)
    store.save({scenario.acme: Position(120.0, -40.0, moved_by_investigator=True)})
    drawing = placed_drawing(builder.connection, None)
    acme = drawing.require_node(scenario.acme)
    assert (acme.x, acme.y) == (120.0, -40.0)
    assert len({(node.x, node.y) for node in drawing.nodes}) == len(drawing.nodes)
    assert list(store.positions()) == [scenario.acme]


def test_a_laid_out_investigation_keeps_its_drawing(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    PositionStore(builder.connection).save(
        {
            entity.identifier: Position(float(number * 100), 0.0)
            for number, entity in enumerate(builder.graph_store.entities())
        }
    )
    drawing = placed_drawing(builder.connection, None)
    assert sorted(node.x for node in drawing.nodes) == [
        float(number * 100) for number in range(len(drawing.nodes))
    ]
