import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from lacis.storage.notes import current_time


class Verdict(StrEnum):
    TO_CHECK = "to_check"
    SUSPECT = "suspect"
    DISMISSED = "dismissed"
    CONFIRMED = "confirmed"

    @property
    def label(self) -> str:
        return VERDICT_LABELS[self]


VERDICT_LABELS = {
    Verdict.TO_CHECK: "À vérifier",
    Verdict.SUSPECT: "Suspect",
    Verdict.DISMISSED: "Écarté",
    Verdict.CONFIRMED: "Confirmé",
}


@dataclass(frozen=True)
class EntityVerdict:
    verdict: Verdict
    reason: str
    decided_at: datetime


class VerdictStore:
    def __init__(
        self, connection: sqlite3.Connection, now: Callable[[], datetime] = current_time
    ) -> None:
        self.connection = connection
        self.now = now

    def verdict(self, identifier: str) -> EntityVerdict | None:
        row = self.connection.execute(
            "SELECT verdict, reason, decided_at FROM entity_verdict WHERE entity_identifier = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            return None
        verdict, reason, decided_at = row
        return EntityVerdict(Verdict(verdict), reason, datetime.fromisoformat(decided_at))

    def verdicts(self) -> dict[str, Verdict]:
        rows = self.connection.execute(
            "SELECT entity_identifier, verdict FROM entity_verdict"
        ).fetchall()
        return {identifier: Verdict(verdict) for identifier, verdict in rows}

    def save(self, identifier: str, verdict: Verdict | None, reason: str) -> EntityVerdict | None:
        with self.connection:
            if verdict is None:
                self.connection.execute(
                    "DELETE FROM entity_verdict WHERE entity_identifier = ?", (identifier,)
                )
                return None
            self.connection.execute(
                """
                INSERT INTO entity_verdict (entity_identifier, verdict, reason, decided_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (entity_identifier) DO UPDATE SET
                    verdict = excluded.verdict,
                    reason = excluded.reason,
                    decided_at = excluded.decided_at
                WHERE entity_verdict.verdict != excluded.verdict
                    OR entity_verdict.reason != excluded.reason
                """,
                (identifier, verdict.value, reason.strip(), self.now().isoformat()),
            )
        return self.verdict(identifier)
