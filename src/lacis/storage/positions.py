import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    x: float
    y: float
    moved_by_investigator: bool = False


class PositionStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def positions(self) -> dict[str, Position]:
        rows = self.connection.execute(
            "SELECT entity_identifier, x, y, moved_by_investigator FROM entity_position"
        ).fetchall()
        return {
            identifier: Position(x, y, bool(moved_by_investigator))
            for identifier, x, y, moved_by_investigator in rows
        }

    def save(self, positions: dict[str, Position]) -> None:
        with self.connection:
            self.connection.executemany(
                """
                INSERT INTO entity_position (entity_identifier, x, y, moved_by_investigator)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (entity_identifier) DO UPDATE SET
                    x = excluded.x,
                    y = excluded.y,
                    moved_by_investigator = excluded.moved_by_investigator
                """,
                [
                    (identifier, position.x, position.y, int(position.moved_by_investigator))
                    for identifier, position in positions.items()
                ],
            )

    def move(self, moved: dict[str, tuple[float, float]]) -> None:
        self.save({identifier: Position(x, y, True) for identifier, (x, y) in moved.items()})

    def forget_computed(self) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM entity_position WHERE moved_by_investigator = 0")
