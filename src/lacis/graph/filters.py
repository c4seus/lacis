from dataclasses import dataclass, replace

from lacis.graph.drawing import GraphDrawing, GraphNode
from lacis.signals.facts import counted
from lacis.storage.entities import EntityKind
from lacis.storage.verdicts import Verdict

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
    tag: str | None = None
    verdict: Verdict | None = None

    @property
    def is_active(self) -> bool:
        annotated = self.tag is not None or self.verdict is not None
        return bool(self.hidden_kinds) or self.flagged_only or annotated

    def shows(self, node: GraphNode) -> bool:
        if node.kind in self.hidden_kinds:
            return False
        if self.tag is not None and self.tag not in node.tags:
            return False
        if self.verdict is not None and node.verdict is not self.verdict:
            return False
        return node.severity is not None or not self.flagged_only

    def showing_kind(self, kind: EntityKind, shown: bool) -> "GraphFilter":
        hidden_kinds = self.hidden_kinds - {kind} if shown else self.hidden_kinds | {kind}
        return replace(self, hidden_kinds=hidden_kinds)

    def showing_flagged_only(self, flagged_only: bool) -> "GraphFilter":
        return replace(self, flagged_only=flagged_only)

    def showing_tag(self, tag: str | None) -> "GraphFilter":
        return replace(self, tag=tag)

    def showing_verdict(self, verdict: Verdict | None) -> "GraphFilter":
        return replace(self, verdict=verdict)

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
