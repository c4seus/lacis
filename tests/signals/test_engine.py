import sqlite3
from datetime import date

import pytest

from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.signal import Finding, Severity
from signal_rules import (
    ACME,
    DUPONT_SERVICES,
    JEAN_DUPONT,
    LILAS_ADDRESS,
    FixedRule,
    WellConnectedRule,
    fill_small_investigation,
    strong_finding,
)

TODAY = date(2026, 11, 10)
SETTINGS = {
    "well_connected": RuleSettings(
        enabled=True,
        severity=Severity.MEDIUM,
        weight=1.0,
        thresholds={"minimum_links": 2},
    ),
    "fixed": RuleSettings(enabled=True, severity=Severity.LOW, weight=0.5),
}


@pytest.fixture
def context(investigation_connection: sqlite3.Connection) -> InvestigationContext:
    fill_small_investigation(investigation_connection)
    return InvestigationContext(investigation_connection, TODAY)


def engine_of(*rules: WellConnectedRule | FixedRule, **changes: RuleSettings) -> SignalEngine:
    return SignalEngine(rules, {**SETTINGS, **changes})


def test_a_rule_receives_the_investigation_and_returns_signals(
    context: InvestigationContext,
) -> None:
    signal = engine_of(WellConnectedRule()).signals(context)[0]
    assert signal.rule == "well_connected"
    assert signal.title == "Entreprise très reliée"
    assert signal.subject in {ACME, DUPONT_SERVICES}
    assert signal.severity is Severity.MEDIUM
    assert signal.score == 0.5
    assert signal.explanation.endswith("est reliée à 2 entités.")


def test_justifying_entities_are_listed_once_in_their_order(
    context: InvestigationContext,
) -> None:
    signals = engine_of(WellConnectedRule()).signals(context)
    assert {signal.subject for signal in signals} == {ACME, DUPONT_SERVICES}
    for signal in signals:
        assert set(signal.justifying_entities) == {JEAN_DUPONT, LILAS_ADDRESS}
        assert len(signal.justifying_entities) == 2


def test_the_score_is_the_strength_weighted_and_kept_between_0_and_1(
    context: InvestigationContext,
) -> None:
    rule = FixedRule((strong_finding(ACME, 3.0), strong_finding(DUPONT_SERVICES, -1.0)))
    scores = {signal.subject: signal.score for signal in engine_of(rule).signals(context)}
    assert scores == {ACME: 0.5, DUPONT_SERVICES: 0.0}


def test_a_finding_may_raise_the_severity_of_its_rule(context: InvestigationContext) -> None:
    rule = FixedRule((strong_finding(ACME), Finding(DUPONT_SERVICES, 1.0, "Plus faible.")))
    severities = {signal.subject: signal.severity for signal in engine_of(rule).signals(context)}
    assert severities == {ACME: Severity.HIGH, DUPONT_SERVICES: Severity.LOW}


def test_signals_come_strongest_first_then_most_severe(context: InvestigationContext) -> None:
    rule = FixedRule(
        (
            Finding(LILAS_ADDRESS, 0.4, "Adresse."),
            Finding(DUPONT_SERVICES, 1.0, "Faible."),
            strong_finding(ACME, 1.0),
        )
    )
    signals = engine_of(rule, WellConnectedRule()).signals(context)
    assert [(signal.subject, signal.rule, signal.score) for signal in signals] == [
        (ACME, "fixed", 0.5),
        (ACME, "well_connected", 0.5),
        (DUPONT_SERVICES, "well_connected", 0.5),
        (DUPONT_SERVICES, "fixed", 0.5),
        (LILAS_ADDRESS, "fixed", 0.2),
    ]


def test_a_disabled_rule_gives_no_signal(context: InvestigationContext) -> None:
    disabled = RuleSettings(enabled=False, severity=Severity.MEDIUM, weight=1.0)
    engine = engine_of(
        WellConnectedRule(), FixedRule((strong_finding(ACME),)), well_connected=disabled
    )
    assert [signal.rule for signal in engine.signals(context)] == ["fixed"]


def test_thresholds_change_the_signals(context: InvestigationContext) -> None:
    stricter = RuleSettings(
        enabled=True, severity=Severity.MEDIUM, weight=1.0, thresholds={"minimum_links": 3}
    )
    assert engine_of(WellConnectedRule(), well_connected=stricter).signals(context) == []
