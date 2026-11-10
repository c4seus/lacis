import sqlite3
from datetime import UTC, date, datetime

import pytest

from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport, SignalStore

COMPUTED_AT = datetime(2026, 11, 10, 8, 30, tzinfo=UTC)
SIGNALS = (
    Signal(
        "phoenix_scheme",
        "Schéma phénix",
        "company:111111111",
        Severity.HIGH,
        0.85,
        "DUPONT SERVICES a fermé le 15/01/2023 après une liquidation judiciaire.",
        ("company:222222222", "person:d28d226afd51317d"),
    ),
    Signal(
        "creation_burst",
        "Rafale de créations",
        "address:65cba5d5a7e6f4f8",
        Severity.MEDIUM,
        0.42,
        "3 entreprises créées à cette adresse.",
        (),
    ),
)


@pytest.fixture
def store(investigation_connection: sqlite3.Connection) -> SignalStore:
    return SignalStore(investigation_connection)


def report(revision: int, signals: tuple[Signal, ...] = SIGNALS) -> SignalReport:
    return SignalReport(signals, revision, date(2026, 11, 10), "configuration", COMPUTED_AT)


def test_no_report_is_stored_before_the_first_computation(store: SignalStore) -> None:
    assert store.report() is None
    assert store.revision() == 0


def test_a_report_is_read_back_in_order(store: SignalStore) -> None:
    saved = store.save(report(4))
    assert store.report() == saved == report(4)


def test_a_new_report_replaces_the_previous_one(store: SignalStore) -> None:
    store.save(report(4))
    store.save(report(7, SIGNALS[1:]))
    assert store.report() == report(7, SIGNALS[1:])
