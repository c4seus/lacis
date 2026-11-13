from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from lacis.signals.signal import Severity

TOML_TRUE = "true"
TOML_FALSE = "false"


class ThresholdKind(StrEnum):
    WHOLE_NUMBER = "whole_number"
    NUMBER = "number"
    SWITCH = "switch"
    TEXTS = "texts"
    CHOICE = "choice"


def shown_number(number: float) -> str:
    return f"{number:g}".replace(".", ",")


def quoted(text: str) -> str:
    return f"« {text} »"


def shown_value(value: object) -> str:
    if isinstance(value, bool):
        return TOML_TRUE if value else TOML_FALSE
    if isinstance(value, str):
        return quoted(value)
    if isinstance(value, list):
        return f"[{', '.join(shown_value(item) for item in value)}]"
    if isinstance(value, dict):
        return "une table"
    return str(value)


@dataclass(frozen=True)
class Threshold:
    name: str
    kind: ThresholdKind
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[str, ...] = ()

    def accepts(self, value: object) -> bool:
        match self.kind:
            case ThresholdKind.SWITCH:
                return isinstance(value, bool)
            case ThresholdKind.TEXTS:
                return isinstance(value, list) and all(isinstance(item, str) for item in value)
            case ThresholdKind.CHOICE:
                return value in self.choices
            case ThresholdKind.WHOLE_NUMBER:
                return (
                    isinstance(value, int)
                    and not isinstance(value, bool)
                    and self.within_bounds(value)
                )
            case _:
                return (
                    isinstance(value, int | float)
                    and not isinstance(value, bool)
                    and self.within_bounds(value)
                )

    def within_bounds(self, number: float) -> bool:
        above_minimum = self.minimum is None or number >= self.minimum
        below_maximum = self.maximum is None or number <= self.maximum
        return above_minimum and below_maximum

    def expected(self) -> str:
        match self.kind:
            case ThresholdKind.SWITCH:
                return f"{TOML_TRUE} ou {TOML_FALSE}"
            case ThresholdKind.TEXTS:
                return 'une liste de textes, par exemple ["Commissaire aux comptes"]'
            case ThresholdKind.CHOICE:
                *first_choices, last_choice = (quoted(choice) for choice in self.choices)
                return f"{', '.join(first_choices)} ou {last_choice}"
            case ThresholdKind.WHOLE_NUMBER:
                return f"un nombre entier{self.bounds_text()}"
            case _:
                return f"un nombre{self.bounds_text()}"

    def bounds_text(self) -> str:
        if self.minimum is not None and self.maximum is not None:
            return f" entre {shown_number(self.minimum)} et {shown_number(self.maximum)}"
        if self.minimum is not None:
            return f" d'au moins {shown_number(self.minimum)}"
        if self.maximum is not None:
            return f" d'au plus {shown_number(self.maximum)}"
        return ""


ENABLED = Threshold("enabled", ThresholdKind.SWITCH)
SEVERITY = Threshold(
    "severity", ThresholdKind.CHOICE, choices=tuple(severity.value for severity in Severity)
)
WEIGHT = Threshold("weight", ThresholdKind.NUMBER, minimum=0, maximum=1)
COMMON_SETTINGS = (ENABLED, SEVERITY, WEIGHT)


@dataclass(frozen=True)
class RuleSettings:
    enabled: bool
    severity: Severity
    weight: float
    thresholds: Mapping[str, object] = field(default_factory=dict)

    def whole_number(self, name: str) -> int:
        return cast(int, self.thresholds[name])

    def number(self, name: str) -> float:
        return float(cast(float, self.thresholds[name]))

    def switch(self, name: str) -> bool:
        return cast(bool, self.thresholds[name])

    def texts(self, name: str) -> tuple[str, ...]:
        return tuple(cast(list[str], self.thresholds[name]))
