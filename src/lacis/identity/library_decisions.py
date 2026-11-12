from collections.abc import Iterator
from contextlib import contextmanager

from lacis.storage.homonym_decisions import (
    HomonymDecision,
    HomonymDecisionStore,
    RecordedDecision,
)
from lacis.storage.investigations import InvestigationLibrary


class LibraryDecisionStore:
    def __init__(self, library: InvestigationLibrary, name: str) -> None:
        self.library = library
        self.name = name

    @contextmanager
    def store(self) -> Iterator[HomonymDecisionStore]:
        with self.library.open(self.name) as opened:
            opened.connection.rollback()
            yield HomonymDecisionStore(opened.connection)

    def record(
        self, first_person: str, second_person: str, decision: HomonymDecision
    ) -> RecordedDecision:
        with self.store() as store:
            return store.record(first_person, second_person, decision)

    def restore(self, recorded: RecordedDecision) -> RecordedDecision:
        with self.store() as store:
            return store.restore(recorded)

    def withdraw(self, first_person: str, second_person: str) -> RecordedDecision:
        with self.store() as store:
            return store.withdraw(first_person, second_person)

    def decision_between(self, first_person: str, second_person: str) -> RecordedDecision | None:
        with self.store() as store:
            return store.decision_between(first_person, second_person)
