import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path

from lacis import __version__
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind, Link
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecisionStore
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.notices import CompanyNotice, NoticeStore
from lacis.storage.responses import ResponseStore, ResponseSummary
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import VerdictStore

SCHEMA_URL = "https://c4seus.github.io/lacis/schemas/investigation-1.schema.json"
FORMAT_NAME = "lacis-investigation"
FORMAT_VERSION = 1
WHOLE_INVESTIGATION = "investigation"
FILTERED_VIEW = "filtered_view"

type Plain = str | int | float | bool | list["Plain"] | dict[str, "Plain"] | None


def plain(value: object) -> Plain:
    if isinstance(value, Enum):
        return plain(value.value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [plain(item) for item in value]
    if value is None or isinstance(value, str | int | float | bool):
        return value
    raise TypeError(type(value).__name__)


@dataclass(frozen=True)
class ExportScope:
    shown: frozenset[str] | None = None

    @property
    def name(self) -> str:
        return WHOLE_INVESTIGATION if self.shown is None else FILTERED_VIEW

    def keeps(self, *identifiers: str) -> bool:
        return self.shown is None or all(item in self.shown for item in identifiers)


class Provenance:
    def __init__(self) -> None:
        self.responses: dict[int, ResponseSummary] = {}

    def cite(self, summaries: Iterable[ResponseSummary]) -> list[Plain]:
        cited: list[Plain] = []
        for summary in summaries:
            self.responses[summary.identifier] = summary
            cited.append(summary.identifier)
        return cited

    def listed(self) -> list[Plain]:
        return [
            {
                "identifier": summary.identifier,
                "source": plain(summary.source),
                "url": summary.url,
                "parameters": plain(summary.parameters),
                "collected_at": plain(summary.collected_at),
                "fingerprint": summary.fingerprint,
            }
            for _identifier, summary in sorted(self.responses.items())
        ]


class InvestigationExport:
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
        self.provenance = Provenance()
        self.response_store = ResponseStore(connection)

    def document(self, investigation: Investigation, exported_at: datetime) -> dict[str, Plain]:
        entities = [
            entity for entity in self.graph_store.entities() if self.scope.keeps(entity.identifier)
        ]
        links = [
            link for link in self.graph_store.links() if self.scope.keeps(link.source, link.target)
        ]
        return {
            "$schema": SCHEMA_URL,
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "lacis_version": __version__,
            "exported_at": plain(exported_at),
            "investigation": {
                "name": investigation.name,
                "question": investigation.question,
                "created_at": plain(investigation.created_at),
            },
            "scope": self.scope.name,
            "entities": [self.entity(entity) for entity in entities],
            "links": [self.link(link) for link in links],
            "signals": self.signals(),
            "homonym_decisions": self.decisions(),
            "responses": self.provenance.listed(),
        }

    def entity(self, entity: Entity) -> Plain:
        note = NoteStore(self.connection).note(entity.identifier)
        verdict = VerdictStore(self.connection).verdict(entity.identifier)
        tags = TagStore(self.connection).tags_of(entity.identifier)
        return {
            "identifier": entity.identifier,
            "kind": plain(entity.kind),
            "label": entity.label,
            "attributes": plain(entity.attributes),
            "first_collected_at": plain(entity.first_collected_at),
            "last_collected_at": plain(entity.last_collected_at),
            "tags": [tag.label for tag in tags],
            "note": None
            if note is None
            else {
                "text": note.text,
                "created_at": plain(note.created_at),
                "changed_at": plain(note.changed_at),
            },
            "verdict": None
            if verdict is None
            else {
                "verdict": plain(verdict.verdict),
                "label": verdict.verdict.label,
                "reason": verdict.reason,
                "decided_at": plain(verdict.decided_at),
            },
            "notices": self.notices(entity),
            "provenance": self.provenance.cite(
                self.graph_store.sources_of_entity(entity.identifier)
            ),
        }

    def notices(self, entity: Entity) -> list[Plain]:
        if entity.kind is not EntityKind.COMPANY:
            return []
        families = NoticeStore(self.connection).notices_of_company(entity.identifier)
        return [
            self.notice(company_notice)
            for notices in families.values()
            for company_notice in notices
        ]

    def notice(self, company_notice: CompanyNotice) -> Plain:
        notice = company_notice.notice
        transfer = notice.office_transfer
        return {
            "identifier": notice.identifier,
            "family": plain(notice.family),
            "role": plain(company_notice.role),
            "published_on": plain(notice.published_on),
            "court": notice.court,
            "judgment": notice.judgment,
            "summary": notice.summary,
            "withdrawn_at": plain(notice.withdrawn_at),
            "office_transfer": None
            if transfer is None
            else {
                "country": transfer.country,
                "effective_on": plain(transfer.effective_on),
                "effective_date_stated": transfer.effective_date_stated,
            },
            "provenance": self.provenance.cite(
                [self.response_store.summary(notice.response_identifier)]
            ),
        }

    def link(self, link: Link) -> Plain:
        return {
            "identifier": link.identifier,
            "kind": plain(link.kind),
            "source": link.source,
            "target": link.target,
            "role": link.role,
            "first_collected_at": plain(link.first_collected_at),
            "last_collected_at": plain(link.last_collected_at),
            "provenance": self.provenance.cite(self.graph_store.sources_of_link(link.identifier)),
        }

    def signals(self) -> list[Plain]:
        if self.report is None:
            return []
        return [
            {
                "rule": signal.rule,
                "title": signal.title,
                "subject": signal.subject,
                "severity": plain(signal.severity),
                "score": signal.score,
                "explanation": signal.explanation,
                "entities": list(signal.justifying_entities),
            }
            for signal in self.report.signals
            if self.scope.keeps(signal.subject)
        ]

    def decisions(self) -> list[Plain]:
        return [
            {
                "first_person": decision.first_person,
                "second_person": decision.second_person,
                "decision": plain(decision.decision),
                "decided_at": plain(decision.decided_at),
            }
            for decision in HomonymDecisionStore(self.connection).decisions()
            if self.scope.keeps(decision.first_person, decision.second_person)
        ]


def write_json(document: dict[str, Plain], destination: Path) -> None:
    text = json.dumps(document, ensure_ascii=False, indent=2)
    destination.write_text(f"{text}\n", encoding="utf-8")
