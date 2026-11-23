import sqlite3
from dataclasses import dataclass

from lacis.details import FACTS
from lacis.exports.json_export import ExportScope
from lacis.exports.obsidian_vault import NoteSubject, unique_names
from lacis.graph.drawing import KIND_LABELS, is_closed
from lacis.signals.signal import Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import VerdictStore

LINK_LABELS = {
    LinkKind.REGISTERED_OFFICE: "Siège social",
    LinkKind.LOCATED_AT: "Situé à",
    LinkKind.ESTABLISHMENT_OF: "Établissement de",
    LinkKind.SAME_PERSON: "Même personne",
}
RESERVED_NAME = ""


def one_line(label: str) -> str:
    return " ".join(label.split())


def link_label(link: Link) -> str:
    if link.kind is LinkKind.MANDATE:
        return link.role
    return LINK_LABELS[link.kind]


@dataclass(frozen=True)
class SnapshotNode:
    identifier: str
    label: str
    name: str
    kind: EntityKind
    facts: tuple[str, ...]
    verdict: str
    tags: tuple[str, ...]
    closed: bool
    signals: tuple[Signal, ...]
    first_collected_at: str

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind]

    @property
    def severity(self) -> str:
        if not self.signals:
            return ""
        return max(self.signals, key=lambda signal: signal.severity.rank).severity.label

    @property
    def score(self) -> float:
        return max((signal.score for signal in self.signals), default=0.0)


@dataclass(frozen=True)
class SnapshotEdge:
    identifier: str
    source: str
    target: str
    kind: LinkKind
    label: str


@dataclass(frozen=True)
class GraphSnapshot:
    nodes: tuple[SnapshotNode, ...]
    edges: tuple[SnapshotEdge, ...]

    def linked(self) -> set[str]:
        return {end for edge in self.edges for end in (edge.source, edge.target)}


def graph_snapshot(
    connection: sqlite3.Connection, report: SignalReport | None, scope: ExportScope
) -> GraphSnapshot:
    graph_store = GraphStore(connection)
    entities = [entity for entity in graph_store.entities() if scope.keeps(entity.identifier)]
    facts = {
        entity.identifier: tuple(FACTS[entity.kind](entity.attributes)) for entity in entities
    }
    subjects = [
        NoteSubject(entity.identifier, entity.label, distinction(entity, facts[entity.identifier]))
        for entity in entities
    ]
    names = unique_names(subjects, RESERVED_NAME, one_line)
    signals = report.signals if report else ()
    verdicts = VerdictStore(connection)
    tags = TagStore(connection)
    nodes = []
    for entity in entities:
        verdict = verdicts.verdict(entity.identifier)
        nodes.append(
            SnapshotNode(
                entity.identifier,
                entity.label,
                names[entity.identifier],
                entity.kind,
                facts[entity.identifier],
                verdict.verdict.label if verdict else "",
                tuple(tag.label for tag in tags.tags_of(entity.identifier)),
                is_closed(entity),
                tuple(signal for signal in signals if signal.subject == entity.identifier),
                entity.first_collected_at.isoformat(),
            )
        )
    edges = [
        SnapshotEdge(link.identifier, link.source, link.target, link.kind, link_label(link))
        for link in graph_store.links()
        if scope.keeps(link.source, link.target)
    ]
    return GraphSnapshot(tuple(nodes), tuple(edges))


def distinction(entity: Entity, facts: tuple[str, ...]) -> str:
    return facts[0] if facts else entity.identifier
