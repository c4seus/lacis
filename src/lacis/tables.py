import sqlite3
from collections import defaultdict
from dataclasses import dataclass

from lacis.details import BadgeTone
from lacis.graph.drawing import KIND_LABELS, is_closed
from lacis.signals.facts import counted
from lacis.signals.signal import Severity
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind, Link, LinkKind
from lacis.storage.graph_store import GraphStore

ACTIVE_COMPANY_TEXT = "Active"
CLOSED_COMPANY_TEXT = "Fermée"
PARTIAL_COMPANY_TEXT = "Partielle"
FOREIGN_COMPANY_TEXT = "Étranger"
OPEN_ESTABLISHMENT_TEXT = "Ouvert"
CLOSED_ESTABLISHMENT_TEXT = "Fermé"
NO_SCORE_TEXT = "\u2013"
SEVERITY_NAMES = {Severity.HIGH: "forte", Severity.MEDIUM: "moyenne", Severity.LOW: "faible"}


@dataclass(frozen=True)
class EntityStatus:
    text: str
    tone: BadgeTone


@dataclass(frozen=True)
class EntityRow:
    identifier: str
    kind: EntityKind
    label: str
    status: EntityStatus | None
    severity: Severity | None
    score: float | None
    links: int

    @property
    def kind_label(self) -> str:
        return KIND_LABELS[self.kind].capitalize()

    @property
    def status_text(self) -> str:
        return "" if self.status is None else self.status.text

    @property
    def flagged(self) -> bool:
        return self.severity is not None

    @property
    def written_score(self) -> str:
        if self.score is None:
            return NO_SCORE_TEXT
        return f"{self.score:.2f}".replace(".", ",")

    @property
    def spoken_score(self) -> str:
        if self.severity is None:
            return "aucun signal"
        return f"score {self.written_score}, gravité {SEVERITY_NAMES[self.severity]}"

    @property
    def sort_score(self) -> tuple[int, float]:
        if self.severity is None or self.score is None:
            return -1, -1.0
        return self.severity.rank, self.score


@dataclass(frozen=True)
class SignalMark:
    severity: Severity
    score: float

    @property
    def strength(self) -> tuple[int, float]:
        return self.severity.rank, self.score


def strongest_marks(report: SignalReport | None) -> dict[str, SignalMark]:
    marks: dict[str, SignalMark] = {}
    for signal in report.signals if report is not None else ():
        mark = SignalMark(signal.severity, signal.score)
        for identifier in (signal.subject, *signal.justifying_entities):
            known = marks.get(identifier)
            if known is None or mark.strength > known.strength:
                marks[identifier] = mark
    return marks


def director_only(entity: Entity, links: list[Link]) -> bool:
    return bool(links) and all(
        link.kind is LinkKind.MANDATE and link.source == entity.identifier for link in links
    )


def company_status(entity: Entity, links: list[Link]) -> EntityStatus | None:
    if entity.attributes.get("is_active") is True:
        return EntityStatus(ACTIVE_COMPANY_TEXT, BadgeTone.ACTIVE)
    if entity.attributes.get("is_active") is False:
        return EntityStatus(CLOSED_COMPANY_TEXT, BadgeTone.CLOSED)
    if director_only(entity, links):
        return EntityStatus(PARTIAL_COMPANY_TEXT, BadgeTone.OUTLINE)
    return None


def establishment_status(entity: Entity) -> EntityStatus | None:
    if is_closed(entity):
        return EntityStatus(CLOSED_ESTABLISHMENT_TEXT, BadgeTone.CLOSED)
    if entity.attributes.get("is_open") is True:
        return EntityStatus(OPEN_ESTABLISHMENT_TEXT, BadgeTone.ACTIVE)
    return None


def entity_status(entity: Entity, links: list[Link]) -> EntityStatus | None:
    if entity.kind is EntityKind.COMPANY:
        return company_status(entity, links)
    if entity.kind is EntityKind.ESTABLISHMENT:
        return establishment_status(entity)
    if entity.kind is EntityKind.FOREIGN_COMPANY:
        return EntityStatus(FOREIGN_COMPANY_TEXT, BadgeTone.OUTLINE)
    return None


def entity_rows(connection: sqlite3.Connection, report: SignalReport | None) -> list[EntityRow]:
    graph_store = GraphStore(connection)
    links_by_entity: dict[str, list[Link]] = defaultdict(list)
    for link in graph_store.links():
        links_by_entity[link.source].append(link)
        links_by_entity[link.target].append(link)
    marks = strongest_marks(report)
    rows = []
    for entity in graph_store.entities():
        links = links_by_entity[entity.identifier]
        mark = marks.get(entity.identifier)
        rows.append(
            EntityRow(
                entity.identifier,
                entity.kind,
                entity.label,
                entity_status(entity, links),
                None if mark is None else mark.severity,
                None if mark is None else mark.score,
                sum(1 for link in links if link.kind is not LinkKind.SAME_PERSON),
            )
        )
    return rows


def entities_summary(rows: tuple[EntityRow, ...]) -> str:
    flagged = sum(1 for row in rows if row.flagged)
    entities = counted(len(rows), "entité", "entités")
    return f"{entities} · {flagged} signalée{'s' if flagged > 1 else ''}"
