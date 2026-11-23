import html
import json
import re
import sqlite3
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path

from lacis import __version__
from lacis.design.tokens import DARK_THEME, FONT_FAMILIES, LIGHT_THEME, Colours
from lacis.details import EntityDetails, entity_details, written_moment
from lacis.exports.json_export import ExportScope, Plain
from lacis.graph.drawing import GraphDrawing, GraphNode, graph_drawing, read_structure
from lacis.graph.layout import LayoutRequest, lay_out
from lacis.product import RESOURCE_DIRECTORY
from lacis.signals.store import SignalReport
from lacis.storage.investigations import Investigation

TEMPLATE_DIRECTORY = RESOURCE_DIRECTORY / "export"
PLACEHOLDER = re.compile(r"\{\{(title|style|themes|script|data)\}\}")
THEME_SWITCH = ':root[data-theme="dark"]'
AUTOMATIC_DARK = ':root:not([data-theme="light"])'


def colour_variables(colours: Colours) -> str:
    return "".join(
        f"--{name.replace('_', '-')}:{value};" for name, value in asdict(colours).items()
    )


def theme_style() -> str:
    fonts = ", ".join(f'"{family}"' if " " in family else family for family in FONT_FAMILIES)
    light = colour_variables(LIGHT_THEME.colours)
    dark = colour_variables(DARK_THEME.colours)
    return (
        f":root{{--font:{fonts};{light}color-scheme:light;}}"
        f"@media (prefers-color-scheme: dark){{{AUTOMATIC_DARK}{{{dark}color-scheme:dark;}}}}"
        f"{THEME_SWITCH}{{{dark}color-scheme:dark;}}"
    )


def placed_drawing(connection: sqlite3.Connection, report: SignalReport | None) -> GraphDrawing:
    drawing = graph_drawing(connection, report)
    if not drawing.needs_layout:
        return drawing
    structure = read_structure(connection)
    known = {node.identifier: (node.x, node.y) for node in drawing.nodes if node.placed}
    request = LayoutRequest(
        structure.entities,
        structure.pairs,
        structure.layered_pairs,
        structure.director_only,
        known,
    )
    positions = lay_out(request)
    nodes = tuple(
        replace(node, x=positions[node.identifier][0], y=positions[node.identifier][1])
        for node in drawing.nodes
    )
    return GraphDrawing(nodes, drawing.edges)


def safe_json(value: Plain) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


class HtmlGraph:
    def __init__(
        self,
        connection: sqlite3.Connection,
        report: SignalReport | None,
        scope: ExportScope,
    ) -> None:
        self.connection = connection
        self.report = report
        self.scope = scope

    def data(self, investigation: Investigation, exported_at: datetime) -> Plain:
        drawing = placed_drawing(self.connection, self.report)
        nodes = [
            (node, details)
            for node in drawing.nodes
            if self.scope.keeps(node.identifier)
            and (details := entity_details(self.connection, node.identifier, self.report))
        ]
        edges = [edge for edge in drawing.edges if self.scope.keeps(edge.source, edge.target)]
        return {
            "investigation": {
                "name": investigation.name,
                "question": investigation.question,
                "exported": written_moment(exported_at),
                "version": __version__,
                "filtered": self.scope.shown is not None,
            },
            "nodes": [self.node(node, details) for node, details in nodes],
            "edges": [
                {
                    "source": edge.source,
                    "target": edge.target,
                    "kind": edge.kind.value,
                    "label": edge.label,
                }
                for edge in edges
            ],
        }

    def node(self, node: GraphNode, details: EntityDetails) -> Plain:
        return {
            "id": node.identifier,
            "label": node.label,
            "kind": node.kind.value,
            "kindLabel": node.kind_label,
            "shape": node.shape.value,
            "size": node.size,
            "x": round(node.x, 1),
            "y": round(node.y, 1),
            "closed": node.closed,
            "severity": node.severity.value if node.severity else "",
            **self.details(details),
        }

    def details(self, details: EntityDetails) -> dict[str, Plain]:
        verdict = details.verdict
        return {
            "name": details.name,
            "facts": list(details.facts),
            "verdict": (
                {"label": verdict.verdict.label, "reason": verdict.reason} if verdict else None
            ),
            "tags": [tag.label for tag in details.tags],
            "note": details.note.text if details.note else "",
            "links": [
                {
                    "id": line.reference.identifier,
                    "role": line.role,
                    "label": line.reference.label,
                    "closed": line.closed,
                }
                for line in details.links
                if self.scope.keeps(line.reference.identifier)
            ],
            "signals": [
                {
                    "title": signal.title,
                    "severity": signal.severity.label,
                    "level": signal.severity.value,
                    "score": signal.score_value,
                    "explanation": signal.explanation,
                }
                for signal in details.signals
            ],
            "notices": [
                {
                    "date": notice.written_date,
                    "family": notice.family_label,
                    "summary": notice.summary,
                    "url": notice.url,
                }
                for notice in details.notices
            ],
            "sources": [
                {"name": source.source_name, "date": source.written_date, "url": source.url}
                for source in details.sources
            ],
        }


def template(name: str) -> str:
    return (TEMPLATE_DIRECTORY / name).read_text(encoding="utf-8")


def html_page(data: Plain, title: str) -> str:
    values = {
        "title": html.escape(title),
        "style": template("graph.css"),
        "themes": theme_style(),
        "script": template("graph.js"),
        "data": safe_json(data),
    }
    return PLACEHOLDER.sub(lambda found: values[found[1]], template("graph.html"))


def write_html_graph(
    graph: HtmlGraph, investigation: Investigation, destination: Path, exported_at: datetime
) -> None:
    page = html_page(graph.data(investigation, exported_at), f"Lacis : {investigation.name}")
    destination.write_text(page, encoding="utf-8", newline="\n")
