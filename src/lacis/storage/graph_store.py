import json
import sqlite3
from datetime import datetime

from lacis.storage.entities import (
    Attributes,
    CollectedEntity,
    CollectedLink,
    Entity,
    EntityKind,
    Link,
    LinkKind,
)

ENTITY_COLUMNS = "identifier, kind, label, attributes, first_collected_at, last_collected_at"
LINK_COLUMNS = "identifier, kind, source, target, role, first_collected_at, last_collected_at"


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


def link_from_row(row: tuple[str, str, str, str, str, str, str]) -> Link:
    identifier, kind, source, target, role, first_collected_at, last_collected_at = row
    return Link(
        identifier=identifier,
        kind=LinkKind(kind),
        source=source,
        target=target,
        role=role,
        first_collected_at=datetime.fromisoformat(first_collected_at),
        last_collected_at=datetime.fromisoformat(last_collected_at),
    )


class GraphStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_entity(self, collected_entity: CollectedEntity, collected_at: datetime) -> Entity:
        with self.connection:
            existing = self.entity(collected_entity.identifier)
            if existing is None:
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
            else:
                self.update_entity(existing, collected_entity, collected_at)
        return self.require_entity(collected_entity.identifier)

    def update_entity(
        self, existing: Entity, collected_entity: CollectedEntity, collected_at: datetime
    ) -> None:
        is_newer = collected_at >= existing.last_collected_at
        label = collected_entity.label if is_newer else existing.label
        attributes = (
            {**existing.attributes, **collected_entity.attributes}
            if is_newer
            else {**collected_entity.attributes, **existing.attributes}
        )
        self.connection.execute(
            """
            UPDATE entity
            SET label = ?, attributes = ?, first_collected_at = ?, last_collected_at = ?
            WHERE identifier = ?
            """,
            (
                label,
                encode_attributes(attributes),
                min(existing.first_collected_at, collected_at).isoformat(),
                max(existing.last_collected_at, collected_at).isoformat(),
                existing.identifier,
            ),
        )

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

    def save_link(self, collected_link: CollectedLink, collected_at: datetime) -> Link:
        with self.connection:
            existing = self.link(collected_link.identifier)
            if existing is None:
                self.connection.execute(
                    f"INSERT INTO link ({LINK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        collected_link.identifier,
                        collected_link.kind.value,
                        collected_link.source,
                        collected_link.target,
                        collected_link.role,
                        collected_at.isoformat(),
                        collected_at.isoformat(),
                    ),
                )
            else:
                self.connection.execute(
                    """
                    UPDATE link SET first_collected_at = ?, last_collected_at = ?
                    WHERE identifier = ?
                    """,
                    (
                        min(existing.first_collected_at, collected_at).isoformat(),
                        max(existing.last_collected_at, collected_at).isoformat(),
                        existing.identifier,
                    ),
                )
        return self.require_link(collected_link.identifier)

    def link(self, identifier: str) -> Link | None:
        row = self.connection.execute(
            f"SELECT {LINK_COLUMNS} FROM link WHERE identifier = ?", (identifier,)
        ).fetchone()
        return link_from_row(row) if row is not None else None

    def require_link(self, identifier: str) -> Link:
        link = self.link(identifier)
        if link is None:
            raise KeyError(identifier)
        return link

    def links(self) -> list[Link]:
        rows = self.connection.execute(
            f"SELECT {LINK_COLUMNS} FROM link ORDER BY identifier"
        ).fetchall()
        return [link_from_row(row) for row in rows]

    def links_of(self, entity_identifier: str) -> list[Link]:
        rows = self.connection.execute(
            f"SELECT {LINK_COLUMNS} FROM link WHERE source = ? OR target = ? ORDER BY identifier",
            (entity_identifier, entity_identifier),
        ).fetchall()
        return [link_from_row(row) for row in rows]
