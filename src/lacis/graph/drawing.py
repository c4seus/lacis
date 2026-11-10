import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import fmean

from lacis.graph.leads import is_known_as_director_only
from lacis.signals.signal import Severity
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore

COLUMN_GAP = 320.0
MINIMUM_GAP = 170.0
DIRECTOR_ROW = 0
COMPANY_ROW = 1
ESTABLISHMENT_ROW = 2
ADDRESS_ROW = 3
ROW_HEIGHTS = {DIRECTOR_ROW: 0.0, COMPANY_ROW: 170.0, ESTABLISHMENT_ROW: 310.0, ADDRESS_ROW: 420.0}
ROW_ORDER = (COMPANY_ROW, DIRECTOR_ROW, ESTABLISHMENT_ROW, ADDRESS_ROW)


IDENTITY_LABEL = "même personne"


class EdgeKind(StrEnum):
    DIRECTS = "directs"
    STRUCTURE = "structure"
    IDENTITY = "identity"


class NodeShape(StrEnum):
    ROUNDED_SQUARE = "rounded_square"
    CIRCLE = "circle"
    DIAMOND = "diamond"
    SMALL_CIRCLE = "small_circle"
    HEXAGON = "hexagon"


SHAPES = {
    EntityKind.COMPANY: NodeShape.ROUNDED_SQUARE,
    EntityKind.PERSON: NodeShape.CIRCLE,
    EntityKind.ADDRESS: NodeShape.DIAMOND,
    EntityKind.ESTABLISHMENT: NodeShape.SMALL_CIRCLE,
    EntityKind.FOREIGN_COMPANY: NodeShape.HEXAGON,
}
NODE_SIZES = {
    EntityKind.COMPANY: 34.0,
    EntityKind.PERSON: 30.0,
    EntityKind.ADDRESS: 30.0,
    EntityKind.ESTABLISHMENT: 14.0,
    EntityKind.FOREIGN_COMPANY: 30.0,
}
KIND_LABELS = {
    EntityKind.COMPANY: "entreprise",
    EntityKind.PERSON: "personne",
    EntityKind.ADDRESS: "adresse",
    EntityKind.ESTABLISHMENT: "établissement",
    EntityKind.FOREIGN_COMPANY: "entreprise étrangère",
}


@dataclass(frozen=True)
class GraphNode:
    identifier: str
    kind: EntityKind
    label: str
    closed: bool
    partial: bool
    x: float
    y: float
    severity: Severity | None = None

    @property
    def shape(self) -> NodeShape:
        return SHAPES[self.kind]

    @property
    def size(self) -> float:
        return NODE_SIZES[self.kind]

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind]


@dataclass(frozen=True)
class GraphEdge:
    identifier: str
    kind: EdgeKind
    source: str
    target: str
    label: str

    @property
    def has_arrow(self) -> bool:
        return self.kind is EdgeKind.DIRECTS

    def touches(self, identifier: str) -> bool:
        return identifier in {self.source, self.target}

    def other_end(self, identifier: str) -> str:
        return self.target if self.source == identifier else self.source


@dataclass(frozen=True)
class GraphDrawing:
    nodes: tuple[GraphNode, ...] = ()
    edges: tuple[GraphEdge, ...] = ()

    def node(self, identifier: str) -> GraphNode | None:
        return next((node for node in self.nodes if node.identifier == identifier), None)


@dataclass
class Block:
    identifiers: list[str]
    desired: list[float]
    start: float = field(init=False)

    def __post_init__(self) -> None:
        self.place()

    def place(self) -> None:
        self.start = fmean(
            position - index * MINIMUM_GAP for index, position in enumerate(self.desired)
        )

    @property
    def end(self) -> float:
        return self.start + (len(self.identifiers) - 1) * MINIMUM_GAP

    def absorb(self, other: "Block") -> None:
        self.identifiers.extend(other.identifiers)
        self.desired.extend(other.desired)
        self.place()


def node_label(entity: Entity) -> str:
    if entity.kind is EntityKind.PERSON:
        birth_month = entity.attributes.get("birth_month")
        return f"{entity.label}\n{birth_month}" if birth_month else entity.label
    if entity.kind is EntityKind.ADDRESS:
        postcode = entity.attributes.get("postcode")
        separator = f" {postcode} "
        if postcode and separator in entity.label:
            street, _, city = entity.label.partition(separator)
            return f"{street}\n{postcode} {city}"
    return entity.label


def is_closed(entity: Entity) -> bool:
    if entity.kind is EntityKind.COMPANY:
        return entity.attributes.get("is_active") is False
    if entity.kind is EntityKind.ESTABLISHMENT:
        return bool(entity.attributes.get("closing_date"))
    return False


def spread(desired: dict[str, float]) -> dict[str, float]:
    blocks: list[Block] = []
    for identifier, position in sorted(desired.items(), key=lambda item: (item[1], item[0])):
        block = Block([identifier], [position])
        while blocks and blocks[-1].end + MINIMUM_GAP > block.start:
            previous = blocks.pop()
            previous.absorb(block)
            block = previous
        blocks.append(block)
    return {
        identifier: block.start + index * MINIMUM_GAP
        for block in blocks
        for index, identifier in enumerate(block.identifiers)
    }


def neighbour_positions(
    identifier: str, edges: Iterable[GraphEdge], placed: dict[str, float]
) -> list[float]:
    neighbours = (edge.other_end(identifier) for edge in edges if edge.touches(identifier))
    return [placed[neighbour] for neighbour in neighbours if neighbour in placed]


def row_of(entity: Entity, director_only: set[str]) -> int:
    if entity.kind is EntityKind.COMPANY:
        return DIRECTOR_ROW if entity.identifier in director_only else COMPANY_ROW
    if entity.kind is EntityKind.ESTABLISHMENT:
        return ESTABLISHMENT_ROW
    if entity.kind is EntityKind.ADDRESS:
        return ADDRESS_ROW
    return DIRECTOR_ROW


def layered_positions(
    entities: list[Entity], edges: list[GraphEdge], director_only: set[str]
) -> dict[str, tuple[float, float]]:
    rows: dict[int, list[Entity]] = {row: [] for row in ROW_ORDER}
    for entity in entities:
        rows[row_of(entity, director_only)].append(entity)
    placed: dict[str, float] = {}
    positions: dict[str, tuple[float, float]] = {}
    for row in ROW_ORDER:
        members = sorted(rows[row], key=lambda entity: (entity.label, entity.identifier))
        desired = {}
        for index, entity in enumerate(members):
            around = neighbour_positions(entity.identifier, edges, placed)
            desired[entity.identifier] = fmean(around) if around else index * COLUMN_GAP
        for identifier, position in spread(desired).items():
            placed[identifier] = position
            positions[identifier] = (position, ROW_HEIGHTS[row])
    return positions


def edge_kind(link: Link) -> EdgeKind:
    if link.kind is LinkKind.MANDATE:
        return EdgeKind.DIRECTS
    if link.kind is LinkKind.SAME_PERSON:
        return EdgeKind.IDENTITY
    return EdgeKind.STRUCTURE


def edge_label(link: Link) -> str:
    if link.kind is LinkKind.MANDATE:
        return link.role
    if link.kind is LinkKind.SAME_PERSON:
        return IDENTITY_LABEL
    return ""


def offices_reached_through_establishments(links: list[Link]) -> set[tuple[str, str]]:
    company_of_establishment = {
        link.source: link.target for link in links if link.kind is LinkKind.ESTABLISHMENT_OF
    }
    return {
        (company_of_establishment[link.source], link.target)
        for link in links
        if link.kind is LinkKind.LOCATED_AT and link.source in company_of_establishment
    }


def graph_edges(links: list[Link]) -> list[GraphEdge]:
    reached = offices_reached_through_establishments(links)
    return [
        GraphEdge(link.identifier, edge_kind(link), link.source, link.target, edge_label(link))
        for link in links
        if not (link.kind is LinkKind.REGISTERED_OFFICE and (link.source, link.target) in reached)
    ]


def flagged_entities(report: SignalReport | None) -> dict[str, Severity]:
    severities: dict[str, Severity] = {}
    for signal in report.signals if report is not None else ():
        for identifier in (signal.subject, *signal.justifying_entities):
            known = severities.get(identifier)
            if known is None or signal.severity.rank > known.rank:
                severities[identifier] = signal.severity
    return severities


def graph_drawing(
    connection: sqlite3.Connection, report: SignalReport | None = None
) -> GraphDrawing:
    graph_store = GraphStore(connection)
    entities = graph_store.entities()
    links = graph_store.links()
    director_only = {
        entity.identifier
        for entity in entities
        if entity.kind is EntityKind.COMPANY and is_known_as_director_only(graph_store, entity)
    }
    edges = graph_edges(links)
    layout_edges = [edge for edge in edges if edge.kind is not EdgeKind.IDENTITY]
    positions = layered_positions(entities, layout_edges, director_only)
    severities = flagged_entities(report)
    nodes = tuple(
        GraphNode(
            identifier=entity.identifier,
            kind=entity.kind,
            label=node_label(entity),
            closed=is_closed(entity),
            partial=entity.identifier in director_only,
            x=positions[entity.identifier][0],
            y=positions[entity.identifier][1],
            severity=severities.get(entity.identifier),
        )
        for entity in entities
    )
    return GraphDrawing(nodes, tuple(edges))
