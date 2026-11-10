import sqlite3
from datetime import date
from pathlib import Path

import pytest

from lacis.signals.configuration import SignalConfigurationError, load_configuration
from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine, user_configuration_path
from lacis.signals.rules import RULES
from lacis.signals.signal import Finding, Severity
from signal_rules import (
    ACME,
    DUPONT_SERVICES,
    JEAN_DUPONT,
    LILAS_ADDRESS,
    FixedRule,
    WellConnectedRule,
    defaults_for,
    fill_small_investigation,
    strong_finding,
)

TODAY = date(2026, 11, 10)


@pytest.fixture
def context(investigation_connection: sqlite3.Connection) -> InvestigationContext:
    fill_small_investigation(investigation_connection)
    return InvestigationContext(investigation_connection, TODAY)


def engine_of(
    *rules: WellConnectedRule | FixedRule, user_path: Path | None = None
) -> SignalEngine:
    defaults = defaults_for([rule.name for rule in rules])
    return SignalEngine(rules, load_configuration(rules, user_path, defaults))


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


def test_a_disabled_rule_gives_no_signal(context: InvestigationContext, tmp_path: Path) -> None:
    user_file = tmp_path / "signals.toml"
    user_file.write_text("[rules.well_connected]\nenabled = false\n", encoding="utf-8")
    engine = engine_of(
        WellConnectedRule(), FixedRule((strong_finding(ACME),)), user_path=user_file
    )
    assert [signal.rule for signal in engine.signals(context)] == ["fixed"]


def test_a_tuned_threshold_changes_the_signals(
    context: InvestigationContext, tmp_path: Path
) -> None:
    user_file = tmp_path / "signals.toml"
    user_file.write_text("[rules.well_connected]\nminimum_links = 3\n", encoding="utf-8")
    assert engine_of(WellConnectedRule(), user_path=user_file).signals(context) == []


def test_the_configured_engine_reads_the_user_file_of_the_configuration_directory(
    isolated_configuration_directory: Path, context: InvestigationContext
) -> None:
    assert user_configuration_path() == isolated_configuration_directory / "signals.toml"
    engine = SignalEngine.configured()
    assert engine.rules == RULES
    assert engine.signals(context) == []
    isolated_configuration_directory.mkdir(parents=True)
    user_configuration_path().write_text("[rules.inconnue]\n", encoding="utf-8")
    with pytest.raises(SignalConfigurationError):
        SignalEngine.configured()


def test_an_engine_can_be_configured_with_other_rules_and_file(tmp_path: Path) -> None:
    with pytest.raises(SignalConfigurationError):
        SignalEngine.configured((WellConnectedRule(),), tmp_path / "absent.toml")
