from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from lacis import __version__
from lacis.collectors.http_client import SOURCE_NAMES
from lacis.design.tokens import LIGHT_THEME
from lacis.details import DECIDED_LINK_TEXT
from lacis.exports.graph_snapshot import GraphSnapshot, SnapshotEdge, SnapshotNode
from lacis.storage.investigations import Investigation
from lacis.storage.responses import ResponseSummary

GEXF_NAMESPACE = "http://gexf.net/1.3"
VIZ_NAMESPACE = "http://gexf.net/1.3/viz"
SCHEMA_INSTANCE_NAMESPACE = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = "http://gexf.net/1.3 http://gexf.net/1.3/gexf.xsd"
GEXF_VERSION = "1.3"
LIST_SEPARATOR = " ; "
NODE_ATTRIBUTES = (
    ("kind", "Type", "string"),
    ("identifier", "Identifiant", "string"),
    ("facts", "Faits", "string"),
    ("verdict", "Verdict", "string"),
    ("tags", "Tags", "string"),
    ("closed", "Fermée", "boolean"),
    ("signal_count", "Signaux", "integer"),
    ("signals", "Titres des signaux", "string"),
    ("severity", "Gravité", "string"),
    ("score", "Score", "double"),
    ("first_collected_at", "Première collecte", "string"),
)
PROVENANCE_ATTRIBUTES = (
    ("sources", "Sources", "string"),
    ("collected_at", "Dates de collecte", "string"),
    ("response_urls", "Adresses des réponses", "string"),
    ("fingerprints", "Empreintes SHA-256", "string"),
)
EDGE_ATTRIBUTES = (
    ("kind", "Type de lien", "string"),
    ("identifier", "Identifiant", "string"),
)

ElementTree.register_namespace("", GEXF_NAMESPACE)
ElementTree.register_namespace("viz", VIZ_NAMESPACE)
ElementTree.register_namespace("xsi", SCHEMA_INSTANCE_NAMESPACE)


def tag(name: str) -> str:
    return f"{{{GEXF_NAMESPACE}}}{name}"


def node_values(node: SnapshotNode) -> dict[str, str]:
    return {
        "kind": node.kind_label,
        "identifier": node.identifier,
        "facts": LIST_SEPARATOR.join(node.facts),
        "verdict": node.verdict,
        "tags": LIST_SEPARATOR.join(node.tags),
        "closed": "true" if node.closed else "false",
        "signal_count": str(len(node.signals)),
        "signals": LIST_SEPARATOR.join(signal.title for signal in node.signals),
        "severity": node.severity,
        "score": f"{node.score:.2f}",
        "first_collected_at": node.first_collected_at,
        **provenance_values(node.sources),
    }


def edge_values(edge: SnapshotEdge) -> dict[str, str]:
    values = {"kind": edge.kind.value, "identifier": edge.identifier}
    if edge.decided:
        return {**values, "sources": DECIDED_LINK_TEXT}
    return {**values, **provenance_values(edge.sources)}


def provenance_values(sources: tuple[ResponseSummary, ...]) -> dict[str, str]:
    return {
        "sources": LIST_SEPARATOR.join(SOURCE_NAMES[source.source] for source in sources),
        "collected_at": LIST_SEPARATOR.join(source.collected_at.isoformat() for source in sources),
        "response_urls": LIST_SEPARATOR.join(source.url for source in sources),
        "fingerprints": LIST_SEPARATOR.join(source.fingerprint for source in sources),
    }


def declare(
    graph: ElementTree.Element, kind: str, attributes: tuple[tuple[str, str, str], ...]
) -> None:
    declared = ElementTree.SubElement(graph, tag("attributes"), {"class": kind})
    for identifier, title, value_type in attributes:
        ElementTree.SubElement(
            declared, tag("attribute"), {"id": identifier, "title": title, "type": value_type}
        )


def add_values(element: ElementTree.Element, values: dict[str, str]) -> None:
    holder = ElementTree.SubElement(element, tag("attvalues"))
    for identifier, value in values.items():
        if value:
            ElementTree.SubElement(holder, tag("attvalue"), {"for": identifier, "value": value})


def gexf_document(
    snapshot: GraphSnapshot, investigation: Investigation, exported_at: datetime
) -> ElementTree.ElementTree:
    root = ElementTree.Element(
        tag("gexf"),
        {
            "version": GEXF_VERSION,
            f"{{{SCHEMA_INSTANCE_NAMESPACE}}}schemaLocation": SCHEMA_LOCATION,
        },
    )
    meta = ElementTree.SubElement(
        root, tag("meta"), {"lastmodifieddate": exported_at.date().isoformat()}
    )
    ElementTree.SubElement(meta, tag("creator")).text = f"Lacis {__version__}"
    ElementTree.SubElement(meta, tag("title")).text = investigation.name
    ElementTree.SubElement(meta, tag("description")).text = investigation.question
    graph = ElementTree.SubElement(
        root, tag("graph"), {"defaultedgetype": "directed", "mode": "static"}
    )
    declare(graph, "node", NODE_ATTRIBUTES + PROVENANCE_ATTRIBUTES)
    declare(graph, "edge", EDGE_ATTRIBUTES + PROVENANCE_ATTRIBUTES)
    colours = LIGHT_THEME.colours
    nodes = ElementTree.SubElement(graph, tag("nodes"))
    for node in snapshot.nodes:
        element = ElementTree.SubElement(
            nodes, tag("node"), {"id": node.identifier, "label": node.label}
        )
        add_values(element, node_values(node))
        colour = getattr(colours, node.kind.value).lstrip("#")
        ElementTree.SubElement(
            element,
            f"{{{VIZ_NAMESPACE}}}color",
            {
                "r": str(int(colour[0:2], 16)),
                "g": str(int(colour[2:4], 16)),
                "b": str(int(colour[4:6], 16)),
            },
        )
    edges = ElementTree.SubElement(graph, tag("edges"))
    for edge in snapshot.edges:
        element = ElementTree.SubElement(
            edges,
            tag("edge"),
            {
                "id": edge.identifier,
                "source": edge.source,
                "target": edge.target,
                "label": edge.label,
            },
        )
        add_values(element, edge_values(edge))
    tree = ElementTree.ElementTree(root)
    ElementTree.indent(tree)
    return tree


def write_gexf(
    snapshot: GraphSnapshot, investigation: Investigation, destination: Path, exported_at: datetime
) -> None:
    tree = gexf_document(snapshot, investigation, exported_at)
    with destination.open("wb") as output:
        tree.write(output, encoding="UTF-8", xml_declaration=True)
        output.write(b"\n")
