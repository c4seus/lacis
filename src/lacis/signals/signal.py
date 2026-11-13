from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

    @property
    def label(self) -> str:
        return SEVERITY_LABELS[self]

    @property
    def rank(self) -> int:
        return list(Severity).index(self)


SEVERITY_LABELS = {Severity.LOW: "Faible", Severity.MEDIUM: "Moyenne", Severity.HIGH: "Forte"}


@dataclass(frozen=True)
class Finding:
    subject: str
    strength: float
    explanation: str
    justifying_entities: tuple[str, ...] = ()
    severity: Severity | None = None


@dataclass(frozen=True)
class Signal:
    rule: str
    title: str
    subject: str
    severity: Severity
    score: float
    explanation: str
    justifying_entities: tuple[str, ...]
