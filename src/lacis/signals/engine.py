from collections.abc import Mapping, Sequence

from lacis.signals.context import InvestigationContext
from lacis.signals.rule import Rule
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.signal import Finding, Signal

SCORE_DECIMALS = 2


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
