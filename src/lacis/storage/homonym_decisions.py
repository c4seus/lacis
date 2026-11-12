import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from lacis.storage.entities import EntityKind, kind_of, same_person_link


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
        return self.restore(RecordedDecision(first, second, decision, self.now()))

    def restore(self, recorded: RecordedDecision) -> RecordedDecision:
        first, second = ordered_people(recorded.first_person, recorded.second_person)
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO homonym_decision (first_person, second_person, decision, decided_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (first_person, second_person)
                DO UPDATE SET decision = excluded.decision, decided_at = excluded.decided_at
                """,
                (first, second, recorded.decision.value, recorded.decided_at.isoformat()),
            )
            if recorded.decision is HomonymDecision.SAME_PERSON:
                self.add_same_person_link(recorded)
            else:
                self.remove_same_person_link(first, second)
        return recorded

    def add_same_person_link(self, recorded: RecordedDecision) -> None:
        link = same_person_link(recorded.first_person, recorded.second_person)
        decided_at = recorded.decided_at.isoformat()
        self.connection.execute(
            """
            INSERT INTO link (identifier, kind, source, target, role,
                              first_collected_at, last_collected_at)
            VALUES (?, ?, ?, ?, '', ?, ?)
            ON CONFLICT (identifier) DO UPDATE SET last_collected_at = excluded.last_collected_at
            """,
            (link.identifier, link.kind.value, link.source, link.target, decided_at, decided_at),
        )

    def remove_same_person_link(self, first_person: str, second_person: str) -> None:
        link = same_person_link(first_person, second_person)
        self.connection.execute("DELETE FROM link WHERE identifier = ?", (link.identifier,))

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

    def withdraw(self, first_person: str, second_person: str) -> RecordedDecision:
        first, second = ordered_people(first_person, second_person)
        with self.connection:
            row = self.connection.execute(
                """
                DELETE FROM homonym_decision WHERE first_person = ? AND second_person = ?
                RETURNING first_person, second_person, decision, decided_at
                """,
                (first, second),
            ).fetchone()
            if row is None:
                raise HomonymDecisionNotFoundError
            self.remove_same_person_link(first, second)
        return decision_from_row(row)
