import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class EntityNote:
    text: str
    created_at: datetime
    changed_at: datetime


def current_time() -> datetime:
    return datetime.now(UTC)


class NoteStore:
    def __init__(
        self, connection: sqlite3.Connection, now: Callable[[], datetime] = current_time
    ) -> None:
        self.connection = connection
        self.now = now

    def note(self, identifier: str) -> EntityNote | None:
        row = self.connection.execute(
            "SELECT text, created_at, changed_at FROM entity_note WHERE entity_identifier = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            return None
        text, created_at, changed_at = row
        return EntityNote(
            text, datetime.fromisoformat(created_at), datetime.fromisoformat(changed_at)
        )

    def noted(self) -> frozenset[str]:
        rows = self.connection.execute("SELECT entity_identifier FROM entity_note").fetchall()
        return frozenset(identifier for (identifier,) in rows)

    def save(self, identifier: str, text: str) -> EntityNote | None:
        with self.connection:
            if not text.strip():
                self.connection.execute(
                    "DELETE FROM entity_note WHERE entity_identifier = ?", (identifier,)
                )
                return None
            moment = self.now().isoformat()
            self.connection.execute(
                """
                INSERT INTO entity_note (entity_identifier, text, created_at, changed_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (entity_identifier) DO UPDATE SET
                    text = excluded.text,
                    changed_at = excluded.changed_at
                WHERE entity_note.text != excluded.text
                """,
                (identifier, text, moment, moment),
            )
        return self.note(identifier)
