import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from investigation_builder import InvestigationBuilder
from lacis.signals.configuration import load_configuration
from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine
from lacis.signals.recomputation import (
    InvestigationSignals,
    configuration_fingerprint,
    local_day,
)
from lacis.signals.rule_settings import RuleSettings, Threshold
from lacis.signals.rules import RULES
from lacis.signals.signal import Finding
from lacis.signals.store import SignalStore
from lacis.storage.entities import EntityKind
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary
from signal_rules import defaults_for

BURST_DATES = (date(2025, 1, 10), date(2025, 2, 1), date(2025, 3, 15))


class Clock:
    def __init__(self) -> None:
        self.moment = datetime(2026, 11, 10, 9, 9, tzinfo=UTC)

    def now(self) -> datetime:
        return self.moment


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def clock() -> Clock:
    return Clock()


def signals_of(
    builder: InvestigationBuilder, clock: Clock, engine: SignalEngine | None = None
) -> InvestigationSignals:
    return InvestigationSignals(builder.connection, engine or SignalEngine.configured(), clock.now)


def burst_by(builder: InvestigationBuilder, director: str, dates: tuple[date, ...]) -> None:
    for position, day in enumerate(dates):
        company = builder.company(f"SOCIETE {position}", day)
        builder.mandate(director, company)


def test_signals_are_computed_once_then_read_back(
    builder: InvestigationBuilder, clock: Clock
) -> None:
    burst_by(builder, builder.person("Paul", "MARTIN"), BURST_DATES)
    first = signals_of(builder, clock).current()
    assert [signal.rule for signal in first.signals] == ["creation_burst"]
    assert first.computed_at == clock.moment
    assert first.revision == SignalStore(builder.connection).revision()
    clock.moment = datetime(2026, 11, 10, 18, 0, tzinfo=UTC)
    assert signals_of(builder, clock).current() == first


def test_signals_never_show_a_state_older_than_the_last_change(
    builder: InvestigationBuilder, clock: Clock
) -> None:
    director = builder.person("Paul", "MARTIN")
    burst_by(builder, director, BURST_DATES[:2])
    assert signals_of(builder, clock).current().signals == ()
    builder.mandate(director, builder.company("SOCIETE C", BURST_DATES[2]))
    current = signals_of(builder, clock).current()
    assert [signal.rule for signal in current.signals] == ["creation_burst"]
    assert current.revision == SignalStore(builder.connection).revision()


def test_a_homonym_decision_makes_signals_stale(
    builder: InvestigationBuilder, clock: Clock
) -> None:
    jean = builder.person("Jean", "DUPONT")
    jean_pierre = builder.person("Jean Pierre", "DUPONT")
    burst_by(builder, jean, BURST_DATES[:2])
    builder.mandate(jean_pierre, builder.company("SOCIETE C", BURST_DATES[2]))
    signals = signals_of(builder, clock)
    assert signals.current().signals == ()
    builder.same_person(jean, jean_pierre)
    assert [signal.rule for signal in signals.current().signals] == ["creation_burst"]


def test_signals_are_recomputed_on_a_new_day(builder: InvestigationBuilder, clock: Clock) -> None:
    first = signals_of(builder, clock).current()
    clock.moment = datetime(2026, 11, 11, 9, 0, tzinfo=UTC)
    second = signals_of(builder, clock).current()
    assert second.computed_on == date(2026, 11, 11)
    assert second.computed_at != first.computed_at


def test_signals_are_recomputed_when_the_configuration_changes(
    builder: InvestigationBuilder, clock: Clock, tmp_path: Path
) -> None:
    burst_by(builder, builder.person("Paul", "MARTIN"), BURST_DATES)
    assert signals_of(builder, clock).current().signals != ()
    user_file = tmp_path / "signals.toml"
    user_file.write_text("[rules.creation_burst]\nenabled = false\n", encoding="utf-8")
    engine = SignalEngine(RULES, load_configuration(RULES, user_file))
    assert signals_of(builder, clock, engine).current().signals == ()


def test_a_forced_recomputation_stores_a_new_report(
    builder: InvestigationBuilder, clock: Clock
) -> None:
    signals = signals_of(builder, clock)
    signals.current()
    clock.moment = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    assert signals.recompute().computed_at == clock.moment


def test_the_configuration_fingerprint_follows_every_setting(tmp_path: Path) -> None:
    default = configuration_fingerprint(SignalEngine.configured())
    assert default == configuration_fingerprint(SignalEngine.configured())
    user_file = tmp_path / "signals.toml"
    user_file.write_text("[rules.phoenix_scheme]\nwindow_months = 13\n", encoding="utf-8")
    assert configuration_fingerprint(SignalEngine.configured(user_path=user_file)) != default


def test_the_day_of_a_computation_is_the_local_day() -> None:
    moment = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    assert local_day(moment) == moment.astimezone().date()


class ConcurrentWriter:
    def __init__(self, database: Path) -> None:
        self.database = database
        self.holding = threading.Event()
        self.failures: list[Exception] = []
        self.thread = threading.Thread(target=self.write)

    def write(self) -> None:
        connection = sqlite3.connect(self.database, timeout=10, autocommit=True)
        try:
            connection.execute("BEGIN IMMEDIATE")
            self.holding.set()
            connection.execute("UPDATE investigation SET question = 'Autre question'")
            connection.execute("COMMIT")
        except sqlite3.Error as failure:
            self.failures.append(failure)
        finally:
            connection.close()


@dataclass(frozen=True)
class WriterMeanwhileRule:
    writer: ConcurrentWriter
    name: str = "fixed"
    title: str = "Règle fixe"
    thresholds: tuple[Threshold, ...] = ()

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        context.entities_of(EntityKind.COMPANY)
        self.writer.thread.start()
        assert self.writer.holding.wait(10)
        return []


def test_saving_signals_waits_for_a_writer_instead_of_failing(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "")
    writer = ConcurrentWriter(library.directory_of("faux-plombiers-31") / DATABASE_FILE_NAME)
    rule = WriterMeanwhileRule(writer)
    engine = SignalEngine((rule,), load_configuration((rule,), None, defaults_for(["fixed"])))
    with library.open("faux-plombiers-31") as opened:
        report = InvestigationSignals(opened.connection, engine).recompute()
    writer.thread.join(10)
    assert report.signals == ()
    assert writer.failures == []
