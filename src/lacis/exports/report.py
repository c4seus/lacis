import sqlite3
from dataclasses import dataclass
from datetime import datetime

from lacis import __version__
from lacis.details import FACTS
from lacis.exports.json_export import ExportScope
from lacis.graph.drawing import KIND_LABELS
from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE, PIVOT_KINDS
from lacis.signals.signal import Signal
from lacis.signals.store import SignalReport
from lacis.storage.collection_log import CollectionLog, RequestStatus
from lacis.storage.entities import Entity
from lacis.storage.expansion_log import ExpansionLog, RecordedExpansion
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import Investigation
from lacis.storage.notes import EntityNote, NoteStore
from lacis.storage.responses import ResponseSource, ResponseStore
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import EntityVerdict, Verdict, VerdictStore

VERDICT_ORDER = (Verdict.CONFIRMED, Verdict.SUSPECT, Verdict.TO_CHECK, Verdict.DISMISSED)


@dataclass(frozen=True)
class ReportedEntity:
    identifier: str
    label: str
    kind_label: str
    facts: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class Finding:
    entity: ReportedEntity
    verdict: EntityVerdict


@dataclass(frozen=True)
class ReportedNote:
    entity: ReportedEntity
    note: EntityNote


@dataclass(frozen=True)
class ReportedSignal:
    signal: Signal
    subject: str
    entities: tuple[str, ...]


@dataclass(frozen=True)
class SourceUse:
    source: ResponseSource
    requests: int
    failures: int
    responses: int
    first_collected_at: datetime | None
    last_collected_at: datetime | None


@dataclass(frozen=True)
class GraphSize:
    total_entities: int
    entities: int
    links: int
    expanded: int
    leads: int


@dataclass(frozen=True)
class ReportContent:
    investigation: Investigation
    produced_at: datetime
    filtered: bool
    size: GraphSize
    sources: tuple[SourceUse, ...]
    expansions: tuple[RecordedExpansion, ...]
    signals_computed_at: datetime | None
    findings: tuple[Finding, ...]
    signals: tuple[ReportedSignal, ...]
    notes: tuple[ReportedNote, ...]
    same_person_decisions: int
    version: str = __version__

    def findings_with(self, verdict: Verdict) -> tuple[Finding, ...]:
        return tuple(finding for finding in self.findings if finding.verdict.verdict is verdict)

    @property
    def without_verdict(self) -> int:
        return self.size.entities - len(self.findings)

    @property
    def failed_requests(self) -> int:
        return sum(use.failures for use in self.sources)

    @property
    def collection_dates(self) -> tuple[datetime, datetime] | None:
        firsts = [use.first_collected_at for use in self.sources if use.first_collected_at]
        lasts = [use.last_collected_at for use in self.sources if use.last_collected_at]
        if not firsts or not lasts:
            return None
        return min(firsts), max(lasts)


def label_order(entity: ReportedEntity) -> tuple[str, str]:
    return entity.label.casefold(), entity.identifier


def signal_order(reported: ReportedSignal) -> tuple[int, float, str]:
    return -reported.signal.severity.rank, -reported.signal.score, reported.subject.casefold()


class ReportBuilder:
    def __init__(
        self,
        connection: sqlite3.Connection,
        report: SignalReport | None,
        scope: ExportScope,
    ) -> None:
        self.connection = connection
        self.report = report
        self.scope = scope
        self.graph_store = GraphStore(connection)
        self.labels = {entity.identifier: entity.label for entity in self.graph_store.entities()}

    def content(self, investigation: Investigation, produced_at: datetime) -> ReportContent:
        entities = [
            entity for entity in self.graph_store.entities() if self.scope.keeps(entity.identifier)
        ]
        reported = sorted((self.reported(entity) for entity in entities), key=label_order)
        return ReportContent(
            investigation=investigation,
            produced_at=produced_at,
            filtered=self.scope.shown is not None,
            size=self.size(entities),
            sources=self.sources(),
            expansions=tuple(ExpansionLog(self.connection).expansions()),
            signals_computed_at=None if self.report is None else self.report.computed_at,
            findings=self.findings(reported),
            signals=self.signals(),
            notes=self.notes(reported),
            same_person_decisions=self.same_person_decisions(),
        )

    def reported(self, entity: Entity) -> ReportedEntity:
        tags = TagStore(self.connection).tags_of(entity.identifier)
        return ReportedEntity(
            entity.identifier,
            entity.label,
            KIND_LABELS[entity.kind],
            tuple(FACTS[entity.kind](entity.attributes)),
            tuple(tag.label for tag in tags),
        )

    def size(self, entities: list[Entity]) -> GraphSize:
        pivots = [entity for entity in entities if entity.kind in PIVOT_KINDS]
        expanded = sum(EXPANDED_AT_ATTRIBUTE in entity.attributes for entity in pivots)
        links = [
            link for link in self.graph_store.links() if self.scope.keeps(link.source, link.target)
        ]
        return GraphSize(
            len(self.labels), len(entities), len(links), expanded, len(pivots) - expanded
        )

    def sources(self) -> tuple[SourceUse, ...]:
        entries = CollectionLog(self.connection).entries()
        summaries = ResponseStore(self.connection).summaries()
        uses = []
        for source in ResponseSource:
            requests = [entry.request for entry in entries if entry.request.source is source]
            collected = [summary.collected_at for summary in summaries if summary.source is source]
            if not requests and not collected:
                continue
            failures = sum(request.status is RequestStatus.FAILED for request in requests)
            uses.append(
                SourceUse(
                    source,
                    len(requests),
                    failures,
                    len(collected),
                    min(collected, default=None),
                    max(collected, default=None),
                )
            )
        return tuple(uses)

    def findings(self, reported: list[ReportedEntity]) -> tuple[Finding, ...]:
        store = VerdictStore(self.connection)
        decided = [
            Finding(entity, verdict)
            for entity in reported
            if (verdict := store.verdict(entity.identifier)) is not None
        ]
        return tuple(
            sorted(decided, key=lambda finding: VERDICT_ORDER.index(finding.verdict.verdict))
        )

    def signals(self) -> tuple[ReportedSignal, ...]:
        if self.report is None:
            return ()
        reported = [
            ReportedSignal(
                signal,
                self.label_of(signal.subject),
                tuple(self.label_of(identifier) for identifier in signal.justifying_entities),
            )
            for signal in self.report.signals
            if self.scope.keeps(signal.subject)
        ]
        return tuple(sorted(reported, key=signal_order))

    def notes(self, reported: list[ReportedEntity]) -> tuple[ReportedNote, ...]:
        store = NoteStore(self.connection)
        return tuple(
            ReportedNote(entity, note)
            for entity in reported
            if (note := store.note(entity.identifier)) is not None
        )

    def same_person_decisions(self) -> int:
        return sum(
            decision.decision is HomonymDecision.SAME_PERSON
            and self.scope.keeps(decision.first_person, decision.second_person)
            for decision in HomonymDecisionStore(self.connection).decisions()
        )

    def label_of(self, identifier: str) -> str:
        return self.labels.get(identifier, identifier)
