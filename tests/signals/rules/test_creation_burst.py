import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from investigation_builder import InvestigationBuilder
from lacis.signals.configuration import load_configuration
from lacis.signals.engine import SignalEngine
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.rules.creation_burst import (
    BurstLimits,
    CreationBurstRule,
    burst_strength,
    densest_burst,
    department_of,
)
from lacis.signals.signal import Finding, Severity

RULE = CreationBurstRule()
PLUMBING = "43.22A"
BURST_DATES = (date(2025, 1, 10), date(2025, 2, 1), date(2025, 3, 15))
SPREAD_DATES = (date(2024, 1, 10), date(2024, 6, 1), date(2025, 3, 15))


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)[RULE.name]


@pytest.fixture
def without_activity(settings: RuleSettings) -> RuleSettings:
    return replace(
        settings, thresholds={**settings.thresholds, "by_activity_and_department": False}
    )


def findings(builder: InvestigationBuilder, settings: RuleSettings) -> list[Finding]:
    return RULE.evaluate(builder.context(), settings)


def created(
    builder: InvestigationBuilder,
    dates: tuple[date, ...],
    activity: str | None = None,
    prefix: str = "SOCIETE",
) -> list[str]:
    return [
        builder.company(f"{prefix} {chr(ord('A') + position)}", day, activity)
        for position, day in enumerate(dates)
    ]


def directed_by(builder: InvestigationBuilder, director: str, companies: list[str]) -> None:
    for company in companies:
        builder.mandate(director, company)


def test_the_rule_ships_with_its_default_thresholds(settings: RuleSettings) -> None:
    assert RULE in RULES
    assert settings.severity is Severity.LOW
    assert settings.whole_number("minimum_companies") == 3
    assert settings.whole_number("window_days") == 90
    assert settings.switch("by_activity_and_department")
    assert settings.whole_number("activity_minimum_companies") == 5
    assert settings.whole_number("activity_window_days") == 30


def test_a_director_creating_companies_in_a_burst_is_flagged(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    companies = created(builder, BURST_DATES)
    directed_by(builder, director, companies)
    [finding] = findings(builder, without_activity)
    assert finding.subject == director
    assert finding.justifying_entities == tuple(companies)
    assert finding.severity is Severity.MEDIUM
    assert finding.explanation == (
        "3 entreprises créées en 65 jours, du 10/01/2025 au 15/03/2025, sous la direction de "
        "Paul MARTIN : SOCIETE A, SOCIETE B, SOCIETE C."
    )


def test_creations_spread_over_time_are_not_flagged(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed_by(builder, director, created(builder, SPREAD_DATES))
    directed_by(builder, director, [builder.company("SANS DATE")])
    assert findings(builder, without_activity) == []


def test_two_creations_are_not_a_burst(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed_by(builder, director, created(builder, BURST_DATES[:2]))
    assert findings(builder, without_activity) == []


def test_creations_on_the_same_day_say_so(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed_by(builder, director, created(builder, (date(2025, 5, 2),) * 3))
    [finding] = findings(builder, without_activity)
    assert finding.explanation.startswith(
        "3 entreprises créées le même jour, le 02/05/2025, sous la direction de Paul MARTIN"
    )


def test_twice_the_minimum_is_more_severe(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed_by(builder, director, created(builder, BURST_DATES * 2))
    [finding] = findings(builder, without_activity)
    assert finding.severity is Severity.HIGH


def test_a_company_directing_new_companies_is_flagged(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    holding = builder.company("HOLDING MARTIN", date(2015, 1, 1))
    directed_by(builder, holding, created(builder, BURST_DATES))
    [finding] = findings(builder, without_activity)
    assert finding.subject == holding
    assert "sous la direction de HOLDING MARTIN" in finding.explanation


def test_auditors_are_not_directors_of_a_burst(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    auditor = builder.person("Claire", "AUDIT")
    for company in created(builder, BURST_DATES):
        builder.mandate(auditor, company, "Commissaire aux comptes")
    assert findings(builder, without_activity) == []


def test_companies_created_together_at_one_address_are_flagged(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    address = builder.address("5 rue de la Gare 31000 Toulouse", postcode="31000")
    companies = created(builder, BURST_DATES)
    for company in companies:
        builder.registered_office(company, address)
    [finding] = findings(builder, without_activity)
    assert finding.subject == address
    assert finding.explanation.endswith("à cette adresse : SOCIETE A, SOCIETE B, SOCIETE C.")


def activity_burst(builder: InvestigationBuilder, count: int, postcode: str = "31000") -> None:
    dates = tuple(date(2025, 3, 1 + 5 * (position % 6)) for position in range(count))
    for position, company in enumerate(created(builder, dates, PLUMBING)):
        address = builder.address(f"{position} rue Haute {postcode} Ville", postcode=postcode)
        builder.registered_office(company, address)


def test_creations_in_one_activity_and_department_are_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activity_burst(builder, 5)
    [finding] = findings(builder, settings)
    assert finding.severity is None
    assert finding.explanation.startswith(
        "5 entreprises créées en 21 jours, du 01/03/2025 au 21/03/2025, dans l'activité "
        "43.22A du département 31 : "
    )
    assert len(finding.justifying_entities) == 4


def test_twice_as_many_creations_in_one_activity_are_more_severe(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activity_burst(builder, 10)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.MEDIUM


def test_the_activity_burst_can_be_switched_off(
    builder: InvestigationBuilder, without_activity: RuleSettings
) -> None:
    activity_burst(builder, 5)
    assert findings(builder, without_activity) == []


def test_creations_in_several_departments_are_not_an_activity_burst(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    activity_burst(builder, 3, "31000")
    activity_burst(builder, 2, "69001")
    unknown = builder.company("SANS ADRESSE", date(2025, 3, 2), PLUMBING)
    builder.registered_office(unknown, builder.address("Lieu-dit sans code"))
    assert findings(builder, settings) == []


@pytest.mark.parametrize(
    ("postcode", "department"),
    [
        ("31000", "31"),
        ("20090", "2A"),
        ("20200", "2B"),
        ("97400", "974"),
        ("1000", None),
        ("BRUXELLES", None),
        (None, None),
    ],
)
def test_departments_come_from_postcodes(postcode: str | None, department: str | None) -> None:
    assert department_of(postcode) == department


def test_the_densest_window_is_kept(builder: InvestigationBuilder) -> None:
    dates = (date(2025, 1, 1), date(2025, 5, 1), date(2025, 5, 2), date(2025, 5, 3))
    created(builder, dates)
    companies = list(builder.context().entities.values())
    burst = densest_burst(companies, BurstLimits(3, 90))
    assert burst is not None
    assert (burst.first, burst.last, burst.count) == (date(2025, 5, 1), date(2025, 5, 3), 3)
    assert burst_strength(burst, BurstLimits(3, 90)) == pytest.approx(
        0.5 * (0.7 + 0.3 * (1 - 3 / 91))
    )


def test_the_engine_gives_the_signal_with_its_title(builder: InvestigationBuilder) -> None:
    director = builder.person("Paul", "MARTIN")
    directed_by(builder, director, created(builder, BURST_DATES))
    [signal] = SignalEngine.configured().signals(builder.context())
    assert signal.title == "Rafale de créations"
    assert signal.severity is Severity.MEDIUM
