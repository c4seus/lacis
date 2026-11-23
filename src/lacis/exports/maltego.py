import csv
from pathlib import Path

from lacis.details import DECIDED_LINK_TEXT
from lacis.exports.graph_snapshot import GraphSnapshot, SnapshotNode
from lacis.storage.entities import EntityKind
from lacis.storage.responses import ResponseSummary

MALTEGO_TYPES = {
    EntityKind.COMPANY: "maltego.Company",
    EntityKind.PERSON: "maltego.Person",
    EntityKind.ADDRESS: "maltego.Location",
    EntityKind.ESTABLISHMENT: "maltego.Location",
    EntityKind.FOREIGN_COMPANY: "maltego.Company",
}
ENDS = (0, 1)
UNTYPED = ""
LIST_SEPARATOR = " ; "


def entity_columns() -> list[tuple[EntityKind, int]]:
    return [(kind, end) for kind in MALTEGO_TYPES for end in ENDS]


def response_urls(sources: tuple[ResponseSummary, ...]) -> str:
    return LIST_SEPARATOR.join(source.url for source in sources)


def maltego_rows(snapshot: GraphSnapshot) -> list[list[str]]:
    columns = entity_columns()
    nodes = {node.identifier: node for node in snapshot.nodes}

    def row(
        *placed: tuple[SnapshotNode, int], link: str = "", link_sources: str = ""
    ) -> list[str]:
        cells = [""] * (2 * len(columns))
        for node, end in placed:
            position = 2 * columns.index((node.kind, end))
            cells[position] = node.name
            cells[position + 1] = response_urls(node.sources)
        return [*cells, link, link_sources]

    types = [cell for kind, _end in columns for cell in (MALTEGO_TYPES[kind], UNTYPED)]
    rows = [[*types, UNTYPED, UNTYPED]]
    rows += [
        row(
            (nodes[edge.source], 0),
            (nodes[edge.target], 1),
            link=edge.label,
            link_sources=DECIDED_LINK_TEXT if edge.decided else response_urls(edge.sources),
        )
        for edge in snapshot.edges
    ]
    linked = snapshot.linked()
    rows += [row((node, 0)) for node in snapshot.nodes if node.identifier not in linked]
    return rows


def write_maltego_csv(snapshot: GraphSnapshot, destination: Path) -> None:
    with destination.open("w", encoding="utf-8", newline="") as output:
        csv.writer(output, lineterminator="\n").writerows(maltego_rows(snapshot))
