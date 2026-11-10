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


def create_entity_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE entity (
            identifier TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            label TEXT NOT NULL,
            attributes TEXT NOT NULL,
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX entity_by_kind ON entity (kind)")


def create_link_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE link (
            identifier TEXT PRIMARY KEY,
            kind TEXT NOT NULL,
            source TEXT NOT NULL REFERENCES entity (identifier),
            target TEXT NOT NULL REFERENCES entity (identifier),
            role TEXT NOT NULL,
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX link_by_source ON link (source)")
    connection.execute("CREATE INDEX link_by_target ON link (target)")


def create_response_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE response (
            identifier INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            url TEXT NOT NULL,
            parameters TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            fingerprint TEXT NOT NULL,
            body BLOB NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX response_by_url ON response (url, collected_at)")


def create_provenance_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE entity_source (
            entity_identifier TEXT NOT NULL REFERENCES entity (identifier),
            response_identifier INTEGER NOT NULL REFERENCES response (identifier),
            PRIMARY KEY (entity_identifier, response_identifier)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE link_source (
            link_identifier TEXT NOT NULL REFERENCES link (identifier),
            response_identifier INTEGER NOT NULL REFERENCES response (identifier),
            PRIMARY KEY (link_identifier, response_identifier)
        )
        """
    )


def create_notice_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE notice (
            identifier TEXT PRIMARY KEY,
            family TEXT NOT NULL,
            published_on TEXT NOT NULL,
            court TEXT NOT NULL,
            judgment TEXT NOT NULL,
            summary TEXT NOT NULL,
            response_identifier INTEGER NOT NULL REFERENCES response (identifier),
            first_collected_at TEXT NOT NULL,
            last_collected_at TEXT NOT NULL
        )
        """
    )


def create_notice_company_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE notice_company (
            notice_identifier TEXT NOT NULL REFERENCES notice (identifier),
            company_identifier TEXT NOT NULL REFERENCES entity (identifier),
            role TEXT NOT NULL,
            PRIMARY KEY (notice_identifier, company_identifier)
        )
        """
    )
    connection.execute(
        "CREATE INDEX notice_company_by_company ON notice_company (company_identifier)"
    )


def add_notice_withdrawal(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE notice ADD COLUMN withdrawn_at TEXT")


def add_notice_office_transfer(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE notice ADD COLUMN office_transfer_country TEXT")
    connection.execute("ALTER TABLE notice ADD COLUMN office_transfer_effective_on TEXT")
    connection.execute("ALTER TABLE notice ADD COLUMN office_transfer_date_stated INTEGER")


REVISED_TABLES = ("entity", "link", "notice", "notice_company", "homonym_decision")
REVISING_EVENTS = ("INSERT", "UPDATE", "DELETE")


def track_revisions_and_signals(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE investigation ADD COLUMN revision INTEGER NOT NULL DEFAULT 0")
    for table in REVISED_TABLES:
        for event in REVISING_EVENTS:
            connection.execute(
                f"""
                CREATE TRIGGER revise_after_{table}_{event.lower()}
                AFTER {event} ON {table}
                BEGIN
                    UPDATE investigation SET revision = revision + 1;
                END
                """
            )
    connection.execute(
        """
        CREATE TABLE signal_computation (
            revision INTEGER NOT NULL,
            computed_on TEXT NOT NULL,
            configuration TEXT NOT NULL,
            computed_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE signal (
            position INTEGER PRIMARY KEY,
            rule TEXT NOT NULL,
            title TEXT NOT NULL,
            subject TEXT NOT NULL,
            severity TEXT NOT NULL,
            score REAL NOT NULL,
            explanation TEXT NOT NULL,
            justifying_entities TEXT NOT NULL
        )
        """
    )


def create_collection_log_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE collection_log (
            identifier INTEGER PRIMARY KEY AUTOINCREMENT,
            requested_at TEXT NOT NULL,
            source TEXT NOT NULL,
            endpoint TEXT NOT NULL,
            http_status INTEGER,
            duration_milliseconds INTEGER NOT NULL,
            served_from_cache INTEGER NOT NULL,
            error TEXT NOT NULL,
            response_identifier INTEGER REFERENCES response (identifier)
        )
        """
    )
    connection.execute(
        "CREATE INDEX collection_log_by_date ON collection_log (requested_at, identifier)"
    )


def create_homonym_decision_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE homonym_decision (
            first_person TEXT NOT NULL REFERENCES entity (identifier) ON DELETE CASCADE,
            second_person TEXT NOT NULL REFERENCES entity (identifier) ON DELETE CASCADE,
            decision TEXT NOT NULL,
            decided_at TEXT NOT NULL,
            PRIMARY KEY (first_person, second_person),
            CHECK (first_person < second_person)
        )
        """
    )


MIGRATIONS: tuple[Migration, ...] = (
    create_investigation_table,
    create_entity_table,
    create_link_table,
    create_response_table,
    create_provenance_tables,
    create_notice_table,
    create_notice_company_table,
    add_notice_withdrawal,
    create_collection_log_table,
    create_homonym_decision_table,
    add_notice_office_transfer,
    track_revisions_and_signals,
)


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
