import sqlite3
from datetime import UTC, datetime

from lacis.storage.expansion_log import ExpansionLog, ExpansionOperation, RecordedExpansion

STARTED_AT = datetime(2026, 11, 12, 9, 30, tzinfo=UTC)


def test_recorded_expansions_are_read_in_the_order_they_started(
    investigation_connection: sqlite3.Connection,
) -> None:
    log = ExpansionLog(investigation_connection)
    later = RecordedExpansion(
        STARTED_AT.replace(hour=11),
        ExpansionOperation.EXPANDED,
        "company:111111111",
        "ACME PLOMBERIE",
        2,
        14,
        cap=200,
        cancelled=True,
        failures=1,
    )
    earlier = RecordedExpansion(
        STARTED_AT, ExpansionOperation.ADDED, "company:111111111", "ACME PLOMBERIE", 0, 1
    )
    log.record(later)
    log.record(earlier)
    assert log.expansions() == [earlier, later]


def test_an_investigation_starts_without_recorded_expansions(
    investigation_connection: sqlite3.Connection,
) -> None:
    assert ExpansionLog(investigation_connection).expansions() == []


def test_every_operation_has_a_label() -> None:
    assert [operation.label for operation in ExpansionOperation] == [
        "Ajout depuis la recherche",
        "Extension",
        "Actualisation",
    ]
