import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, date, datetime

from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine
from lacis.signals.store import SignalReport, SignalStore


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_day(moment: datetime) -> date:
    return moment.astimezone().date()


def configuration_fingerprint(engine: SignalEngine) -> str:
    described = {
        name: {
            "enabled": settings.enabled,
            "severity": settings.severity.value,
            "weight": settings.weight,
            "thresholds": dict(settings.thresholds),
        }
        for name, settings in engine.configuration.items()
    }
    text = json.dumps(described, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


class InvestigationSignals:
    def __init__(
        self,
        connection: sqlite3.Connection,
        engine: SignalEngine,
        now: Callable[[], datetime] = utc_now,
    ) -> None:
        self.connection = connection
        self.engine = engine
        self.now = now
        self.store = SignalStore(connection)
        self.configuration = configuration_fingerprint(engine)

    def is_current(self, report: SignalReport) -> bool:
        return (
            report.revision == self.store.revision()
            and report.computed_on == local_day(self.now())
            and report.configuration == self.configuration
        )

    def current(self) -> SignalReport:
        report = self.store.report()
        if report is not None and self.is_current(report):
            return report
        return self.recompute()

    def recompute(self) -> SignalReport:
        revision = self.store.revision()
        computed_at = self.now()
        today = local_day(computed_at)
        signals = self.engine.signals(InvestigationContext(self.connection, today))
        self.connection.commit()
        return self.store.save(
            SignalReport(tuple(signals), revision, today, self.configuration, computed_at)
        )
