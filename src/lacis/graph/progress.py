import threading
from collections.abc import Callable
from dataclasses import dataclass, replace

FIRST_PLURAL = 2


@dataclass(frozen=True)
class ExpansionProgress:
    requests_made: int = 0
    new_entities: int = 0

    @property
    def summary(self) -> str:
        requests = "requête" if self.requests_made < FIRST_PLURAL else "requêtes"
        entities = "nouvelle entité" if self.new_entities < FIRST_PLURAL else "nouvelles entités"
        return f"{self.requests_made} {requests}, {self.new_entities} {entities}"


class ProgressTracker:
    def __init__(self, report: Callable[[ExpansionProgress], None]) -> None:
        self.report = report
        self.progress = ExpansionProgress()
        self.lock = threading.Lock()

    def request_made(self) -> None:
        with self.lock:
            self.progress = replace(self.progress, requests_made=self.progress.requests_made + 1)
            progress = self.progress
        self.report(progress)

    def entities_found(self, count: int) -> None:
        with self.lock:
            self.progress = replace(self.progress, new_entities=self.progress.new_entities + count)
            progress = self.progress
        self.report(progress)
