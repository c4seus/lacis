import sqlite3
from pathlib import Path

import pytest

from lacis.storage.errors import NewerInvestigationError
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.schema import (
    MIGRATIONS,
    NewerSchemaError,
    create_investigation_table,
    migrate,
    schema_version,
)


def add_note_table(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE note (text TEXT NOT NULL)")


def fail_after_creating_a_table(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE half_done (value TEXT)")
    raise RuntimeError("migration failed")


def table_names(database_path: Path) -> set[str]:
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {name for (name,) in rows}
    finally:
        connection.close()


def stored_version(database_path: Path) -> int:
    connection = sqlite3.connect(database_path)
    try:
        return schema_version(connection)
    finally:
        connection.close()


def test_a_new_investigation_has_the_current_schema_version(tmp_path: Path) -> None:
    investigation = InvestigationLibrary(tmp_path).create("faux-plombiers-31", "")
    assert stored_version(investigation.database_path) == len(MIGRATIONS)


def test_an_empty_database_gets_every_migration(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "empty.sqlite3", autocommit=False)
    try:
        migrate(connection, [create_investigation_table, add_note_table])
        assert schema_version(connection) == 2
    finally:
        connection.close()
    assert {"investigation", "note"} <= table_names(tmp_path / "empty.sqlite3")


def test_an_older_investigation_opens_after_migration(tmp_path: Path) -> None:
    InvestigationLibrary(tmp_path, migrations=[create_investigation_table]).create(
        "ancienne", "Une question"
    )
    newer_library = InvestigationLibrary(
        tmp_path, migrations=[create_investigation_table, add_note_table]
    )
    with newer_library.open("ancienne") as opened:
        assert opened.investigation.question == "Une question"
        assert schema_version(opened.connection) == 2
    assert "note" in table_names(tmp_path / "ancienne" / "investigation.sqlite3")


def test_an_investigation_of_a_newer_version_is_refused_with_a_clear_message(
    tmp_path: Path,
) -> None:
    InvestigationLibrary(tmp_path, migrations=[create_investigation_table, add_note_table]).create(
        "future", ""
    )
    older_library = InvestigationLibrary(tmp_path, migrations=[create_investigation_table])
    with pytest.raises(NewerInvestigationError) as refusal:
        older_library.open("future")
    assert str(refusal.value) == (
        "L'enquête « future » a été enregistrée par une version plus récente de Lacis "
        "(format 2, alors que cette version lit jusqu'au format 1). "
        "Mettez Lacis à jour pour l'ouvrir."
    )
    assert stored_version(tmp_path / "future" / "investigation.sqlite3") == 2


def test_migrating_a_newer_database_is_refused(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "future.sqlite3", autocommit=True)
    try:
        connection.execute("PRAGMA user_version = 5")
        with pytest.raises(NewerSchemaError) as refusal:
            migrate(connection, [create_investigation_table])
    finally:
        connection.close()
    assert (refusal.value.version, refusal.value.supported_version) == (5, 1)


def test_a_failing_migration_leaves_the_investigation_as_it_was(tmp_path: Path) -> None:
    InvestigationLibrary(tmp_path, migrations=[create_investigation_table]).create("fragile", "")
    failing_library = InvestigationLibrary(
        tmp_path, migrations=[create_investigation_table, fail_after_creating_a_table]
    )
    with pytest.raises(RuntimeError, match="migration failed"):
        failing_library.open("fragile")
    database_path = tmp_path / "fragile" / "investigation.sqlite3"
    assert stored_version(database_path) == 1
    assert "half_done" not in table_names(database_path)
