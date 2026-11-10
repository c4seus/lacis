from lacis.graph.drawing import EdgeKind, GraphDrawing, GraphEdge, GraphNode
from lacis.signals.facts import counted
from lacis.storage.entities import EntityKind

CLOSED_WORDS = {EntityKind.COMPANY: "fermée", EntityKind.ESTABLISHMENT: "fermé"}
PARTIAL_WORDS = "connue comme dirigeante seulement"
EMPTY_GRAPH_TEXT = "Graphe vide"


def spoken_label(node: GraphNode) -> str:
    if node.kind is EntityKind.PERSON and "\n" in node.label:
        name, _, birth_month = node.label.partition("\n")
        return f"{name} ({birth_month})"
    return node.label.replace("\n", " ")


def edges_of(drawing: GraphDrawing, identifier: str) -> list[GraphEdge]:
    return [edge for edge in drawing.edges if edge.touches(identifier)]


def entity_summary(drawing: GraphDrawing, node: GraphNode) -> str:
    parts = [spoken_label(node), node.kind_label]
    if node.closed:
        parts.append(CLOSED_WORDS[node.kind])
    if node.partial:
        parts.append(PARTIAL_WORDS)
    parts.append(counted(len(edges_of(drawing, node.identifier)), "lien", "liens"))
    if node.severity is not None:
        parts.append(f"signal de sévérité {node.severity.label.lower()}")
    return ", ".join(parts)


def link_description(drawing: GraphDrawing, edge: GraphEdge, identifier: str) -> str:
    other = drawing.require_node(edge.other_end(identifier))
    other_label = spoken_label(other)
    if edge.kind is EdgeKind.IDENTITY:
        return f"{edge.label} que {other_label}"
    if edge.kind is EdgeKind.DIRECTS:
        if edge.source == identifier:
            return f"{edge.label} de {other_label}"
        return f"{edge.label} : {other_label}"
    return f"{other.kind_label} {other_label}"


def entity_description(drawing: GraphDrawing, identifier: str) -> str:
    node = drawing.node(identifier)
    if node is None:
        return ""
    links = [link_description(drawing, edge, identifier) for edge in edges_of(drawing, identifier)]
    summary = entity_summary(drawing, node)
    return f"{summary}. Liens : {' ; '.join(links)}." if links else f"{summary}."


def graph_summary(drawing: GraphDrawing) -> str:
    if not drawing.nodes:
        return EMPTY_GRAPH_TEXT
    entities = counted(len(drawing.nodes), "entité", "entités")
    links = counted(len(drawing.edges), "lien", "liens")
    flagged = sum(1 for node in drawing.nodes if node.severity is not None)
    signals = counted(flagged, "entité signalée", "entités signalées")
    return f"{entities}, {links}, {signals}"
