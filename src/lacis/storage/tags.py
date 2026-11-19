import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Tag:
    key: str
    label: str


def written_tag(text: str) -> str:
    return " ".join(text.split())


def tag_key(text: str) -> str:
    return written_tag(text).casefold()


class TagStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def tags(self) -> tuple[Tag, ...]:
        rows = self.connection.execute(
            "SELECT DISTINCT tag_key, label FROM entity_tag ORDER BY tag_key"
        ).fetchall()
        return tuple(Tag(key, label) for key, label in rows)

    def tags_of(self, identifier: str) -> tuple[Tag, ...]:
        rows = self.connection.execute(
            "SELECT tag_key, label FROM entity_tag WHERE entity_identifier = ? ORDER BY tag_key",
            (identifier,),
        ).fetchall()
        return tuple(Tag(key, label) for key, label in rows)

    def tagged(self) -> dict[str, frozenset[str]]:
        rows = self.connection.execute(
            "SELECT entity_identifier, tag_key FROM entity_tag"
        ).fetchall()
        keys: dict[str, set[str]] = {}
        for identifier, key in rows:
            keys.setdefault(identifier, set()).add(key)
        return {identifier: frozenset(found) for identifier, found in keys.items()}

    def add(self, identifier: str, text: str) -> Tag | None:
        key = tag_key(text)
        if not key:
            return None
        known = self.connection.execute(
            "SELECT label FROM entity_tag WHERE tag_key = ? LIMIT 1", (key,)
        ).fetchone()
        tag = Tag(key, written_tag(text) if known is None else known[0])
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO entity_tag (entity_identifier, tag_key, label) VALUES (?, ?, ?)
                ON CONFLICT (entity_identifier, tag_key) DO NOTHING
                """,
                (identifier, tag.key, tag.label),
            )
        return tag

    def remove(self, identifier: str, key: str) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM entity_tag WHERE entity_identifier = ? AND tag_key = ?",
                (identifier, key),
            )
