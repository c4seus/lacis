from dataclasses import dataclass, replace

from lacis.graph.drawing import GraphDrawing, GraphNode
from lacis.signals.facts import counted
from lacis.storage.entities import EntityKind

KIND_FILTER_LABELS = {
    EntityKind.COMPANY: "Entreprises",
    EntityKind.PERSON: "Personnes",
    EntityKind.ADDRESS: "Adresses",
    EntityKind.ESTABLISHMENT: "Établissements",
    EntityKind.FOREIGN_COMPANY: "Entreprises étrangères",
}
FLAGGED_ONLY_LABEL = "Entités signalées seulement"
NOTHING_HIDDEN_TEXT = "tous les types"


@dataclass(frozen=True)
class GraphFilter:
    hidden_kinds: frozenset[EntityKind] = frozenset()
    flagged_only: bool = False

    @property
    def is_active(self) -> bool:
        return bool(self.hidden_kinds) or self.flagged_only

    def shows(self, node: GraphNode) -> bool:
        if node.kind in self.hidden_kinds:
            return False
        return node.severity is not None or not self.flagged_only

    def showing_kind(self, kind: EntityKind, shown: bool) -> "GraphFilter":
        hidden_kinds = self.hidden_kinds - {kind} if shown else self.hidden_kinds | {kind}
        return replace(self, hidden_kinds=hidden_kinds)

    def showing_flagged_only(self, flagged_only: bool) -> "GraphFilter":
        return replace(self, flagged_only=flagged_only)

    def shown_identifiers(self, drawing: GraphDrawing) -> set[str]:
        return {node.identifier for node in drawing.nodes if self.shows(node)}

    def hidden_count(self, drawing: GraphDrawing) -> int:
        return len(drawing.nodes) - len(self.shown_identifiers(drawing))

    def summary(self, drawing: GraphDrawing) -> str:
        if not self.is_active:
            return NOTHING_HIDDEN_TEXT
        return counted(self.hidden_count(drawing), "entité masquée", "entités masquées")


def kind_choice_label(kind: EntityKind, drawing: GraphDrawing) -> str:
    count = sum(1 for node in drawing.nodes if node.kind is kind)
    return f"{KIND_FILTER_LABELS[kind]} ({count})"


def flagged_choice_label(drawing: GraphDrawing) -> str:
    count = sum(1 for node in drawing.nodes if node.severity is not None)
    return f"{FLAGGED_ONLY_LABEL} ({count})"
