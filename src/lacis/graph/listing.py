import unicodedata
from dataclasses import dataclass

from lacis.graph.descriptions import edges_of, entity_summary, link_description, spoken_label
from lacis.graph.drawing import GraphDrawing, GraphNode
from lacis.graph.filters import KIND_FILTER_LABELS, GraphFilter
from lacis.signals.facts import counted
from lacis.storage.entities import EntityKind


@dataclass(frozen=True)
class ListedLink:
    identifier: str
    target: str
    target_kind: EntityKind
    description: str


@dataclass(frozen=True)
class ListedEntity:
    identifier: str
    kind: EntityKind
    label: str
    summary: str
    links: tuple[ListedLink, ...]


@dataclass(frozen=True)
class ListedKind:
    kind: EntityKind
    entities: tuple[ListedEntity, ...]

    @property
    def title(self) -> str:
        return f"{KIND_FILTER_LABELS[self.kind]} ({len(self.entities)})"

    @property
    def summary(self) -> str:
        entities = counted(len(self.entities), "entité", "entités")
        return f"{KIND_FILTER_LABELS[self.kind]}, {entities}"


def sortable(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def shown_drawing(drawing: GraphDrawing, graph_filter: GraphFilter) -> GraphDrawing:
    shown = graph_filter.shown_identifiers(drawing)
    return GraphDrawing(
        tuple(node for node in drawing.nodes if node.identifier in shown),
        tuple(edge for edge in drawing.edges if {edge.source, edge.target} <= shown),
    )


def listed_entity(drawing: GraphDrawing, node: GraphNode) -> ListedEntity:
    links = sorted(
        (
            ListedLink(
                edge.identifier,
                edge.other_end(node.identifier),
                drawing.require_node(edge.other_end(node.identifier)).kind,
                link_description(drawing, edge, node.identifier),
            )
            for edge in edges_of(drawing, node.identifier)
        ),
        key=lambda link: sortable(link.description),
    )
    return ListedEntity(
        node.identifier,
        node.kind,
        spoken_label(node),
        entity_summary(drawing, node),
        tuple(links),
    )


def graph_listing(drawing: GraphDrawing, graph_filter: GraphFilter) -> tuple[ListedKind, ...]:
    shown = shown_drawing(drawing, graph_filter)
    listing = []
    for kind in KIND_FILTER_LABELS:
        nodes = sorted(
            (node for node in shown.nodes if node.kind is kind),
            key=lambda node: sortable(spoken_label(node)),
        )
        if nodes:
            listing.append(ListedKind(kind, tuple(listed_entity(shown, node) for node in nodes)))
    return tuple(listing)
