import csv
from pathlib import Path

from lacis.exports.graph_snapshot import GraphSnapshot, SnapshotNode
from lacis.storage.entities import EntityKind

MALTEGO_TYPES = {
    EntityKind.COMPANY: "maltego.Company",
    EntityKind.PERSON: "maltego.Person",
    EntityKind.ADDRESS: "maltego.Location",
    EntityKind.ESTABLISHMENT: "maltego.Location",
    EntityKind.FOREIGN_COMPANY: "maltego.Company",
}
ENDS = (0, 1)
LINK_COLUMN_TYPE = ""


def entity_columns() -> list[tuple[EntityKind, int]]:
    return [(kind, end) for kind in MALTEGO_TYPES for end in ENDS]


def maltego_rows(snapshot: GraphSnapshot) -> list[list[str]]:
    columns = entity_columns()
    nodes = {node.identifier: node for node in snapshot.nodes}

    def row(*placed: tuple[SnapshotNode, int], link: str = "") -> list[str]:
        cells = [""] * len(columns)
        for node, end in placed:
            cells[columns.index((node.kind, end))] = node.name
        return [*cells, link]

    rows = [[*(MALTEGO_TYPES[kind] for kind, _end in columns), LINK_COLUMN_TYPE]]
    rows += [
        row((nodes[edge.source], 0), (nodes[edge.target], 1), link=edge.label)
        for edge in snapshot.edges
    ]
    linked = snapshot.linked()
    rows += [row((node, 0)) for node in snapshot.nodes if node.identifier not in linked]
    return rows


def write_maltego_csv(snapshot: GraphSnapshot, destination: Path) -> None:
    with destination.open("w", encoding="utf-8", newline="") as output:
        csv.writer(output, lineterminator="\n").writerows(maltego_rows(snapshot))
