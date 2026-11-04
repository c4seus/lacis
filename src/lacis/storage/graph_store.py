import json
import sqlite3
from datetime import datetime

from lacis.storage.entities import Attributes, CollectedEntity, Entity, EntityKind

ENTITY_COLUMNS = "identifier, kind, label, attributes, first_collected_at, last_collected_at"


def encode_attributes(attributes: Attributes) -> str:
    return json.dumps(attributes, ensure_ascii=False, sort_keys=True)


def entity_from_row(row: tuple[str, str, str, str, str, str]) -> Entity:
    identifier, kind, label, attributes, first_collected_at, last_collected_at = row
    return Entity(
        identifier=identifier,
        kind=EntityKind(kind),
        label=label,
        attributes=json.loads(attributes),
        first_collected_at=datetime.fromisoformat(first_collected_at),
        last_collected_at=datetime.fromisoformat(last_collected_at),
    )


class GraphStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_entity(self, collected_entity: CollectedEntity, collected_at: datetime) -> Entity:
        with self.connection:
            self.connection.execute(
                f"INSERT INTO entity ({ENTITY_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    collected_entity.identifier,
                    collected_entity.kind.value,
                    collected_entity.label,
                    encode_attributes(collected_entity.attributes),
                    collected_at.isoformat(),
                    collected_at.isoformat(),
                ),
            )
        return self.require_entity(collected_entity.identifier)

    def entity(self, identifier: str) -> Entity | None:
        row = self.connection.execute(
            f"SELECT {ENTITY_COLUMNS} FROM entity WHERE identifier = ?", (identifier,)
        ).fetchone()
        return entity_from_row(row) if row is not None else None

    def require_entity(self, identifier: str) -> Entity:
        entity = self.entity(identifier)
        if entity is None:
            raise KeyError(identifier)
        return entity

    def entities(self, kind: EntityKind | None = None) -> list[Entity]:
        if kind is None:
            rows = self.connection.execute(
                f"SELECT {ENTITY_COLUMNS} FROM entity ORDER BY identifier"
            ).fetchall()
        else:
            rows = self.connection.execute(
                f"SELECT {ENTITY_COLUMNS} FROM entity WHERE kind = ? ORDER BY identifier",
                (kind.value,),
            ).fetchall()
        return [entity_from_row(row) for row in rows]
