from typing import Protocol

from lacis.signals.context import InvestigationContext
from lacis.signals.rule_settings import RuleSettings, Threshold
from lacis.signals.signal import Finding


class Rule(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def title(self) -> str: ...

    @property
    def thresholds(self) -> tuple[Threshold, ...]: ...

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]: ...
