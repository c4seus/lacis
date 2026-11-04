import sqlite3
from collections.abc import Callable, Sequence

Migration = Callable[[sqlite3.Connection], None]


class NewerSchemaError(Exception):
    def __init__(self, version: int, supported_version: int) -> None:
        super().__init__(f"Schema version {version} is newer than {supported_version}")
        self.version = version
        self.supported_version = supported_version


def create_investigation_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE investigation (
            question TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


MIGRATIONS: tuple[Migration, ...] = (create_investigation_table,)


def schema_version(connection: sqlite3.Connection) -> int:
    version: int = connection.execute("PRAGMA user_version").fetchone()[0]
    return version


def migrate(connection: sqlite3.Connection, migrations: Sequence[Migration] = MIGRATIONS) -> None:
    version = schema_version(connection)
    if version > len(migrations):
        raise NewerSchemaError(version, len(migrations))
    for next_version, migration in enumerate(migrations[version:], start=version + 1):
        with connection:
            migration(connection)
            connection.execute(f"PRAGMA user_version = {next_version:d}")
