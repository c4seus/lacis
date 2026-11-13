import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from lacis.graph.layout import (
    LayoutRequest,
    Pair,
    Point,
    initial_positions,
    lay_out,
    no_pause,
)
from lacis.graph.leads import is_known_as_director_only
from lacis.signals.signal import Severity
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.positions import Position, PositionStore

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
    placed: bool = True

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

    @property
    def needs_layout(self) -> bool:
        return any(not node.placed for node in self.nodes)

    def require_node(self, identifier: str) -> GraphNode:
        node = self.node(identifier)
        if node is None:
            raise KeyError(identifier)
        return node


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


@dataclass(frozen=True)
class GraphStructure:
    entities: list[Entity]
    edges: list[GraphEdge]
    director_only: set[str]

    @property
    def pairs(self) -> list[Pair]:
        return [(edge.source, edge.target) for edge in self.edges]

    @property
    def layered_pairs(self) -> list[Pair]:
        return [
            (edge.source, edge.target) for edge in self.edges if edge.kind is not EdgeKind.IDENTITY
        ]

    def initial_positions(self, known: dict[str, Point]) -> dict[str, Point]:
        return initial_positions(self.entities, self.layered_pairs, self.director_only, known)


def read_structure(connection: sqlite3.Connection) -> GraphStructure:
    graph_store = GraphStore(connection)
    entities = graph_store.entities()
    director_only = {
        entity.identifier
        for entity in entities
        if entity.kind is EntityKind.COMPANY and is_known_as_director_only(graph_store, entity)
    }
    return GraphStructure(entities, graph_edges(graph_store.links()), director_only)


def stored_points(connection: sqlite3.Connection) -> dict[str, Point]:
    return {
        identifier: (position.x, position.y)
        for identifier, position in PositionStore(connection).positions().items()
    }


def graph_drawing(
    connection: sqlite3.Connection, report: SignalReport | None = None
) -> GraphDrawing:
    structure = read_structure(connection)
    known = stored_points(connection)
    positions = structure.initial_positions(known)
    severities = flagged_entities(report)
    nodes = tuple(
        GraphNode(
            identifier=entity.identifier,
            kind=entity.kind,
            label=node_label(entity),
            closed=is_closed(entity),
            partial=entity.identifier in structure.director_only,
            x=positions[entity.identifier][0],
            y=positions[entity.identifier][1],
            severity=severities.get(entity.identifier),
            placed=entity.identifier in known,
        )
        for entity in structure.entities
    )
    return GraphDrawing(nodes, tuple(structure.edges))


def lay_out_investigation(
    connection: sqlite3.Connection, pause: Callable[[], None] = no_pause
) -> int:
    structure = read_structure(connection)
    known = stored_points(connection)
    connection.rollback()
    newcomers = {entity.identifier for entity in structure.entities} - set(known)
    if not newcomers:
        return 0
    request = LayoutRequest(
        structure.entities,
        structure.pairs,
        structure.layered_pairs,
        structure.director_only,
        known,
    )
    positions = lay_out(request, pause)
    PositionStore(connection).save(
        {identifier: Position(*positions[identifier]) for identifier in sorted(newcomers)}
    )
    return len(newcomers)


def lay_out_again(connection: sqlite3.Connection, pause: Callable[[], None] = no_pause) -> int:
    PositionStore(connection).forget_computed()
    return lay_out_investigation(connection, pause)
