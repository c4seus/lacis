from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Self

from lacis.signals.configuration import USER_CONFIGURATION_FILE_NAME, load_configuration
from lacis.signals.context import InvestigationContext
from lacis.signals.rule import Rule
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.signal import Finding, Signal
from lacis.storage.locations import configuration_directory

SCORE_DECIMALS = 2


def user_configuration_path() -> Path:
    return configuration_directory() / USER_CONFIGURATION_FILE_NAME


def signal_of(rule: Rule, settings: RuleSettings, finding: Finding) -> Signal:
    strength = min(max(finding.strength, 0.0), 1.0)
    return Signal(
        rule=rule.name,
        title=rule.title,
        subject=finding.subject,
        severity=finding.severity or settings.severity,
        score=round(strength * settings.weight, SCORE_DECIMALS),
        explanation=finding.explanation,
        justifying_entities=tuple(dict.fromkeys(finding.justifying_entities)),
    )


class SignalEngine:
    def __init__(self, rules: Sequence[Rule], configuration: Mapping[str, RuleSettings]) -> None:
        self.rules = tuple(rules)
        self.configuration = configuration

    @classmethod
    def configured(cls, rules: Sequence[Rule] = RULES, user_path: Path | None = None) -> Self:
        path = user_path if user_path is not None else user_configuration_path()
        return cls(rules, load_configuration(rules, path))

    def signals(self, context: InvestigationContext) -> list[Signal]:
        signals: list[Signal] = []
        for rule in self.rules:
            settings = self.configuration[rule.name]
            if not settings.enabled:
                continue
            signals.extend(
                signal_of(rule, settings, finding) for finding in rule.evaluate(context, settings)
            )
        return sorted(
            signals,
            key=lambda signal: (
                -signal.score,
                -signal.severity.rank,
                signal.subject,
                signal.rule,
            ),
        )
