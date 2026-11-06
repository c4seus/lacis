import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from lacis.storage.entities import EntityKind, kind_of


class HomonymDecision(StrEnum):
    SAME_PERSON = "même personne"
    DIFFERENT_PERSON = "personne différente"


class InvalidHomonymDecisionError(ValueError):
    pass


class HomonymDecisionNotFoundError(LookupError):
    def __init__(self) -> None:
        super().__init__("Aucune décision n'a été prise sur ces deux personnes.")


@dataclass(frozen=True)
class RecordedDecision:
    first_person: str
    second_person: str
    decision: HomonymDecision
    decided_at: datetime


def current_time() -> datetime:
    return datetime.now(UTC)


def ordered_people(first_person: str, second_person: str) -> tuple[str, str]:
    if first_person == second_person:
        raise InvalidHomonymDecisionError("A person cannot be compared with themselves")
    for person in (first_person, second_person):
        if kind_of(person) is not EntityKind.PERSON:
            raise InvalidHomonymDecisionError(f"{person} is not a person")
    first, second = sorted((first_person, second_person))
    return first, second


def decision_from_row(row: tuple[str, str, str, str]) -> RecordedDecision:
    first_person, second_person, decision, decided_at = row
    return RecordedDecision(
        first_person,
        second_person,
        HomonymDecision(decision),
        datetime.fromisoformat(decided_at),
    )


class HomonymDecisionStore:
    def __init__(
        self, connection: sqlite3.Connection, now: Callable[[], datetime] = current_time
    ) -> None:
        self.connection = connection
        self.now = now

    def record(
        self, first_person: str, second_person: str, decision: HomonymDecision
    ) -> RecordedDecision:
        first, second = ordered_people(first_person, second_person)
        recorded = RecordedDecision(first, second, decision, self.now())
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO homonym_decision (first_person, second_person, decision, decided_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (first_person, second_person)
                DO UPDATE SET decision = excluded.decision, decided_at = excluded.decided_at
                """,
                (first, second, decision.value, recorded.decided_at.isoformat()),
            )
        return recorded

    def decision_between(self, first_person: str, second_person: str) -> RecordedDecision | None:
        first, second = ordered_people(first_person, second_person)
        row = self.connection.execute(
            """
            SELECT first_person, second_person, decision, decided_at FROM homonym_decision
            WHERE first_person = ? AND second_person = ?
            """,
            (first, second),
        ).fetchone()
        return decision_from_row(row) if row is not None else None

    def decisions(self) -> list[RecordedDecision]:
        rows = self.connection.execute(
            """
            SELECT first_person, second_person, decision, decided_at FROM homonym_decision
            ORDER BY decided_at, first_person, second_person
            """
        ).fetchall()
        return [decision_from_row(row) for row in rows]

    def decided_pairs(self) -> set[tuple[str, str]]:
        rows = self.connection.execute(
            "SELECT first_person, second_person FROM homonym_decision"
        ).fetchall()
        return {(first, second) for first, second in rows}

    def undo(self, first_person: str, second_person: str) -> RecordedDecision:
        recorded = self.decision_between(first_person, second_person)
        if recorded is None:
            raise HomonymDecisionNotFoundError
        with self.connection:
            self.connection.execute(
                "DELETE FROM homonym_decision WHERE first_person = ? AND second_person = ?",
                (recorded.first_person, recorded.second_person),
            )
        return recorded
