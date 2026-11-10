import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from investigation_builder import TODAY, InvestigationBuilder
from lacis.signals.configuration import load_configuration
from lacis.signals.engine import SignalEngine
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.rules.mass_domiciliation import MassDomiciliationRule
from lacis.signals.signal import Finding, Severity

RULE = MassDomiciliationRule()
ADDRESS = "5 rue de la Gare 31000 Toulouse"
RECENT = date(2025, 6, 1)
OLD = date(2015, 6, 1)
REAL_ESTATE = "68.20B"


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)[RULE.name]


def domiciled(
    builder: InvestigationBuilder,
    companies: list[tuple[date | None, str | None]],
    *,
    expanded: bool = False,
) -> str:
    address = builder.address(ADDRESS, expanded=expanded)
    for position, (creation_date, activity) in enumerate(companies):
        company = builder.company(f"SOCIETE {position:02d}", creation_date, activity)
        builder.registered_office(company, address)
    return address


def mixed_activities(count: int) -> list[str]:
    return [f"{10 + position}.11Z" for position in range(count)]


def findings(builder: InvestigationBuilder, settings: RuleSettings) -> list[Finding]:
    return RULE.evaluate(builder.context(), settings)


def test_the_rule_ships_with_its_default_thresholds(settings: RuleSettings) -> None:
    assert RULE in RULES
    assert settings.severity is Severity.LOW
    assert dict(settings.thresholds) == {
        "minimum_companies": 10,
        "recent_years": 2,
        "minimum_recent_share": 0.5,
        "minimum_same_activity_share": 0.5,
    }


def test_many_recent_companies_at_one_address_are_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activities = mixed_activities(10)
    ages = [RECENT] * 6 + [OLD] * 4
    address = domiciled(builder, list(zip(ages, activities, strict=True)))
    [finding] = findings(builder, settings)
    assert finding.subject == address
    assert finding.explanation == (
        "10 entreprises de l'enquête ont leur siège à cette adresse, dont 6 créées depuis moins "
        "de 2 ans ; l'adresse n'a pas encore été étendue et peut en compter d'autres."
    )
    assert len(finding.justifying_entities) == 10
    assert finding.severity is None
    assert finding.strength == pytest.approx(0.5 * (0.5 + 0.25 * 0.6 + 0.25 * 0.1))


def test_many_companies_with_the_same_activity_are_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activities = [REAL_ESTATE] * 5 + mixed_activities(5)
    domiciled(builder, [(OLD, activity) for activity in activities], expanded=True)
    [finding] = findings(builder, settings)
    assert finding.explanation == (
        "10 entreprises de l'enquête ont leur siège à cette adresse, "
        "dont 5 dans l'activité 68.20B."
    )


def test_recent_companies_with_the_same_activity_are_more_severe(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    domiciled(builder, [(RECENT, REAL_ESTATE)] * 10, expanded=True)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.MEDIUM
    assert finding.explanation == (
        "10 entreprises de l'enquête ont leur siège à cette adresse, dont 10 créées depuis "
        "moins de 2 ans et 10 dans l'activité 68.20B."
    )
    assert finding.strength == pytest.approx(0.5)


def test_twice_the_minimum_with_both_patterns_is_severe(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    domiciled(builder, [(RECENT, REAL_ESTATE)] * 20)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.HIGH
    assert finding.strength == pytest.approx(1.0)


def test_fewer_companies_than_the_minimum_are_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    domiciled(builder, [(RECENT, REAL_ESTATE)] * 9)
    assert findings(builder, settings) == []


def test_many_old_companies_of_various_activities_are_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activities = mixed_activities(12)
    ages = [OLD] * 8 + [RECENT] * 4
    domiciled(builder, list(zip(ages, activities, strict=True)))
    assert findings(builder, settings) == []


def test_unknown_dates_and_activities_count_as_neither_recent_nor_shared(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    domiciled(builder, [(None, None)] * 10)
    assert findings(builder, settings) == []


def test_a_company_created_on_the_cutoff_day_is_recent(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activities = mixed_activities(10)
    cutoff = date(TODAY.year - 2, TODAY.month, TODAY.day)
    domiciled(
        builder,
        [(cutoff if position < 5 else OLD, activities[position]) for position in range(10)],
    )
    [finding] = findings(builder, settings)
    assert "dont 5 créées depuis moins de 2 ans" in finding.explanation


def test_one_recent_company_is_written_in_the_singular(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    tuned = replace(
        settings, thresholds={**settings.thresholds, "minimum_companies": 2, "recent_years": 1}
    )
    domiciled(builder, [(date(2026, 1, 15), REAL_ESTATE), (OLD, REAL_ESTATE)], expanded=True)
    [finding] = findings(builder, tuned)
    assert finding.explanation == (
        "2 entreprises de l'enquête ont leur siège à cette adresse, dont 1 créée depuis moins "
        "de 1 an et 2 dans l'activité 68.20B."
    )


def test_thresholds_can_be_tuned(builder: InvestigationBuilder, settings: RuleSettings) -> None:
    domiciled(builder, [(OLD, activity) for activity in mixed_activities(4)], expanded=True)
    tuned = replace(
        settings,
        thresholds={
            **settings.thresholds,
            "minimum_companies": 4,
            "minimum_recent_share": 0,
        },
    )
    [finding] = findings(builder, tuned)
    assert finding.explanation == ("4 entreprises de l'enquête ont leur siège à cette adresse.")


def test_only_registered_offices_count(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    address = builder.address(ADDRESS)
    for position in range(10):
        builder.company(f"AILLEURS {position}", RECENT, REAL_ESTATE)
    other = builder.company("SIEGE", RECENT, REAL_ESTATE)
    builder.registered_office(other, address)
    assert findings(builder, settings) == []


def test_the_engine_gives_a_scored_signal_with_the_rule_severity(
    builder: InvestigationBuilder,
) -> None:
    activities = mixed_activities(10)
    domiciled(builder, [(RECENT, activities[position]) for position in range(10)])
    [signal] = SignalEngine.configured().signals(builder.context())
    assert signal.rule == "mass_domiciliation"
    assert signal.title == "Domiciliation de masse"
    assert signal.severity is Severity.LOW
    assert signal.score == 0.39
