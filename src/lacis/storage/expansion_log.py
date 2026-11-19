import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

EXPANSION_LOG_COLUMNS = (
    "started_at, operation, entity_identifier, label, depth, new_entities, cap, cancelled, "
    "failures"
)


class ExpansionOperation(StrEnum):
    ADDED = "added"
    EXPANDED = "expanded"
    REFRESHED = "refreshed"

    @property
    def label(self) -> str:
        return OPERATION_LABELS[self]


OPERATION_LABELS = {
    ExpansionOperation.ADDED: "Ajout depuis la recherche",
    ExpansionOperation.EXPANDED: "Extension",
    ExpansionOperation.REFRESHED: "Actualisation",
}


@dataclass(frozen=True)
class RecordedExpansion:
    started_at: datetime
    operation: ExpansionOperation
    entity_identifier: str
    label: str
    depth: int
    new_entities: int
    cap: int | None = None
    cancelled: bool = False
    failures: int = 0


def expansion_from_row(
    row: tuple[str, str, str, str, int, int, int | None, int, int],
) -> RecordedExpansion:
    started_at, operation, identifier, label, depth, new_entities, cap, cancelled, failures = row
    return RecordedExpansion(
        datetime.fromisoformat(started_at),
        ExpansionOperation(operation),
        identifier,
        label,
        depth,
        new_entities,
        cap,
        bool(cancelled),
        failures,
    )


class ExpansionLog:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def record(self, expansion: RecordedExpansion) -> None:
        with self.connection:
            self.connection.execute(
                f"INSERT INTO expansion_log ({EXPANSION_LOG_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    expansion.started_at.isoformat(),
                    expansion.operation.value,
                    expansion.entity_identifier,
                    expansion.label,
                    expansion.depth,
                    expansion.new_entities,
                    expansion.cap,
                    expansion.cancelled,
                    expansion.failures,
                ),
            )

    def expansions(self) -> list[RecordedExpansion]:
        rows = self.connection.execute(
            f"SELECT {EXPANSION_LOG_COLUMNS} FROM expansion_log ORDER BY started_at, identifier"
        ).fetchall()
        return [expansion_from_row(row) for row in rows]
