import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from lacis.signals.signal import Severity, Signal

SIGNAL_COLUMNS = "rule, title, subject, severity, score, explanation, justifying_entities"
COMPUTATION_COLUMNS = "revision, computed_on, configuration, computed_at"


@dataclass(frozen=True)
class SignalReport:
    signals: tuple[Signal, ...]
    revision: int
    computed_on: date
    configuration: str
    computed_at: datetime


def signal_from_row(row: tuple[str, str, str, str, float, str, str]) -> Signal:
    rule, title, subject, severity, score, explanation, justifying_entities = row
    return Signal(
        rule=rule,
        title=title,
        subject=subject,
        severity=Severity(severity),
        score=score,
        explanation=explanation,
        justifying_entities=tuple(json.loads(justifying_entities)),
    )


class SignalStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def revision(self) -> int:
        revision: int = self.connection.execute("SELECT revision FROM investigation").fetchone()[0]
        return revision

    def report(self) -> SignalReport | None:
        computation = self.connection.execute(
            f"SELECT {COMPUTATION_COLUMNS} FROM signal_computation"
        ).fetchone()
        if computation is None:
            return None
        revision, computed_on, configuration, computed_at = computation
        rows = self.connection.execute(
            f"SELECT {SIGNAL_COLUMNS} FROM signal ORDER BY position"
        ).fetchall()
        return SignalReport(
            tuple(signal_from_row(row) for row in rows),
            revision,
            date.fromisoformat(computed_on),
            configuration,
            datetime.fromisoformat(computed_at),
        )

    def save(self, report: SignalReport) -> SignalReport:
        with self.connection:
            self.connection.execute("DELETE FROM signal")
            self.connection.execute("DELETE FROM signal_computation")
            self.connection.executemany(
                f"INSERT INTO signal (position, {SIGNAL_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        position,
                        signal.rule,
                        signal.title,
                        signal.subject,
                        signal.severity.value,
                        signal.score,
                        signal.explanation,
                        json.dumps(list(signal.justifying_entities)),
                    )
                    for position, signal in enumerate(report.signals)
                ],
            )
            self.connection.execute(
                f"INSERT INTO signal_computation ({COMPUTATION_COLUMNS}) VALUES (?, ?, ?, ?)",
                (
                    report.revision,
                    report.computed_on.isoformat(),
                    report.configuration,
                    report.computed_at.isoformat(),
                ),
            )
        return report
