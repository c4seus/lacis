import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from xml.etree import ElementTree

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis import __version__
from lacis.exports.gexf import GEXF_NAMESPACE, VIZ_NAMESPACE, write_gexf
from lacis.exports.graph_snapshot import graph_snapshot
from lacis.exports.json_export import ExportScope
from lacis.storage.investigations import Investigation
from lacis.storage.notices import NoticeFamily

EXPORTED_AT = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers ?",
    datetime(2026, 11, 13, 9, 0, tzinfo=UTC),
    Path("faux-plombiers-31"),
)
NAMESPACES = {"gexf": GEXF_NAMESPACE, "viz": VIZ_NAMESPACE}
FINGERPRINT = "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def written(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    destination: Path,
    shown: frozenset[str] | None = None,
) -> ElementTree.Element:
    snapshot = graph_snapshot(builder.connection, phoenix_report(scenario), ExportScope(shown))
    write_gexf(snapshot, INVESTIGATION, destination, EXPORTED_AT)
    return ElementTree.parse(destination).getroot()


def values_of(element: ElementTree.Element) -> dict[str, str]:
    return {
        value.attrib["for"]: value.attrib["value"]
        for value in element.iterfind("gexf:attvalues/gexf:attvalue", NAMESPACES)
    }


def test_the_file_is_a_gexf_1_3_document_about_the_investigation(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    destination = tmp_path / "graphe.gexf"
    root = written(builder, scenario, destination)
    assert root.tag == f"{{{GEXF_NAMESPACE}}}gexf"
    assert root.attrib["version"] == "1.3"
    assert root.findtext("gexf:meta/gexf:creator", namespaces=NAMESPACES) == f"Lacis {__version__}"
    assert root.findtext("gexf:meta/gexf:title", namespaces=NAMESPACES) == "faux-plombiers-31"
    assert root.findtext("gexf:meta/gexf:description", namespaces=NAMESPACES) == (
        "Qui se cache derrière les plombiers ?"
    )
    meta = root.find("gexf:meta", NAMESPACES)
    assert meta is not None
    assert meta.attrib["lastmodifieddate"] == "2026-11-23"
    text = destination.read_bytes()
    assert text.startswith(b"<?xml version='1.0' encoding='UTF-8'?>\n")
    assert b"\r" not in text


def test_every_attribute_is_declared_with_its_type(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    root = written(builder, scenario, tmp_path / "graphe.gexf")
    declared = {
        (attributes.attrib["class"], attribute.attrib["id"], attribute.attrib["type"])
        for attributes in root.iterfind("gexf:graph/gexf:attributes", NAMESPACES)
        for attribute in attributes.iterfind("gexf:attribute", NAMESPACES)
    }
    assert ("node", "kind", "string") in declared
    assert ("node", "signal_count", "integer") in declared
    assert ("node", "score", "double") in declared
    assert ("node", "closed", "boolean") in declared
    assert ("edge", "kind", "string") in declared
    used = {
        value.attrib["for"]
        for value in root.iterfind(".//gexf:node/gexf:attvalues/gexf:attvalue", NAMESPACES)
    }
    assert used <= {identifier for kind, identifier, _type in declared if kind == "node"}


def test_every_entity_is_a_node_with_its_kind_signals_score_and_colour(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    root = written(builder, scenario, tmp_path / "graphe.gexf")
    nodes = {node.attrib["id"]: node for node in root.iterfind(".//gexf:node", NAMESPACES)}
    assert len(nodes) == len(builder.graph_store.entities())
    services = nodes[scenario.dupont_services]
    assert services.attrib["label"] == "DUPONT SERVICES"
    assert values_of(services) == {
        "kind": "entreprise",
        "identifier": scenario.dupont_services,
        "facts": "SIREN 100 000 001 ; Créée le 01/06/2019 ; Fermée le 15/01/2023",
        "closed": "true",
        "signal_count": "1",
        "signals": "Schéma phénix",
        "severity": "Forte",
        "score": "0.85",
        "first_collected_at": "2026-11-02T23:11:00+00:00",
        "sources": "Recherche d'entreprises",
        "collected_at": "2026-11-02T23:11:00+00:00",
        "response_urls": "https://company_register.example",
        "fingerprints": FINGERPRINT,
    }
    colour = services.find("viz:color", NAMESPACES)
    assert colour is not None
    assert colour.attrib == {"r": "61", "g": "99", "b": "221"}


def test_every_link_is_an_edge_with_its_label_and_kind(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    root = written(builder, scenario, tmp_path / "graphe.gexf")
    edges = list(root.iterfind(".//gexf:edge", NAMESPACES))
    assert len(edges) == len(builder.graph_store.links())
    president = next(
        edge
        for edge in edges
        if edge.attrib["source"] == scenario.jean
        and edge.attrib["target"] == scenario.dupont_services
    )
    assert president.attrib["label"] == "Président"
    assert values_of(president)["kind"] == "mandate"


def test_the_filtered_view_writes_only_the_entities_shown(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    shown = frozenset({scenario.acme, scenario.jean_pierre})
    root = written(builder, scenario, tmp_path / "graphe.gexf", shown)
    assert {node.attrib["id"] for node in root.iterfind(".//gexf:node", NAMESPACES)} == shown
    assert len(list(root.iterfind(".//gexf:edge", NAMESPACES))) == 1


def test_every_node_and_edge_lists_the_responses_it_comes_from(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    root = written(builder, scenario, tmp_path / "graphe.gexf")
    elements = [
        *root.iterfind(".//gexf:node", NAMESPACES),
        *root.iterfind(".//gexf:edge", NAMESPACES),
    ]
    decided = [element for element in elements if values_of(element).get("kind") == "same_person"]
    assert [values_of(element)["sources"] for element in decided] == ["Décision de l'enquêteur"]
    for element in elements:
        if element in decided:
            continue
        values = values_of(element)
        assert values["sources"] == "Recherche d'entreprises"
        assert values["response_urls"] == "https://company_register.example"
        assert values["fingerprints"] == FINGERPRINT
        assert values["collected_at"] == "2026-11-02T23:11:00+00:00"
    declared = {
        (attributes.attrib["class"], attribute.attrib["id"])
        for attributes in root.iterfind("gexf:graph/gexf:attributes", NAMESPACES)
        for attribute in attributes.iterfind("gexf:attribute", NAMESPACES)
    }
    for kind in ("node", "edge"):
        for identifier in ("sources", "collected_at", "response_urls", "fingerprints"):
            assert (kind, identifier) in declared


def test_an_entity_with_several_responses_lists_them_in_the_same_order(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    builder.notice(scenario.dupont_services, NoticeFamily.INSOLVENCY, date(2022, 11, 3))
    root = written(builder, scenario, tmp_path / "graphe.gexf")
    services = next(
        node
        for node in root.iterfind(".//gexf:node", NAMESPACES)
        if node.attrib["id"] == scenario.dupont_services
    )
    values = values_of(services)
    sources = values["sources"].split(" ; ")
    assert len(sources) == len(values["response_urls"].split(" ; "))
    assert len(sources) == len(values["fingerprints"].split(" ; "))
    assert len(sources) == len(values["collected_at"].split(" ; "))
