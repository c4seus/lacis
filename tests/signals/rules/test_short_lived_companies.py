import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from investigation_builder import InvestigationBuilder
from lacis.signals.configuration import load_configuration
from lacis.signals.engine import SignalEngine
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.rules.short_lived_companies import ShortLivedCompaniesRule
from lacis.signals.signal import Finding, Severity
from lacis.storage.notices import NoticeFamily

RULE = ShortLivedCompaniesRule()
CREATED = date(2024, 1, 10)
FOUR_MONTHS = date(2024, 5, 10)
SEVEN_MONTHS = date(2024, 8, 10)
TWELVE_MONTHS = date(2025, 1, 10)
EIGHTEEN_MONTHS = date(2025, 7, 12)
SHORT_LIFETIMES = (FOUR_MONTHS, SEVEN_MONTHS, TWELVE_MONTHS)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)[RULE.name]


def findings(builder: InvestigationBuilder, settings: RuleSettings) -> list[Finding]:
    return RULE.evaluate(builder.context(), settings)


def directed(
    builder: InvestigationBuilder,
    director: str,
    closings: tuple[date | None, ...],
    role: str = "Gérant",
) -> list[str]:
    companies = []
    for position, closing in enumerate(closings):
        company = builder.company(
            f"SOCIETE {chr(ord('A') + position)}", CREATED, closing_date=closing
        )
        builder.mandate(director, company, role)
        companies.append(company)
    return companies


def test_the_rule_ships_with_its_default_thresholds(settings: RuleSettings) -> None:
    assert RULE in RULES
    assert settings.severity is Severity.MEDIUM
    assert dict(settings.thresholds) == {
        "minimum_companies": 5,
        "minimum_short_lived": 3,
        "maximum_lifetime_months": 18,
        "include_probable": False,
        "excluded_roles": [
            "Commissaire aux comptes",
            "Commissaire aux comptes suppléant",
            "Administrateur judiciaire",
            "Mandataire judiciaire",
            "Liquidateur judiciaire",
        ],
    }


def test_a_director_of_many_short_lived_companies_is_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    companies = directed(builder, director, (*SHORT_LIFETIMES, None, None))
    [finding] = findings(builder, settings)
    assert finding.subject == director
    assert finding.justifying_entities == tuple(companies[:3])
    assert finding.severity is None
    assert finding.strength == pytest.approx(0.5 * (0.6 + 0.4 * 0.6))
    assert finding.explanation == (
        "Paul MARTIN dirige ou a dirigé 5 entreprises de l'enquête, dont 3 fermées moins de "
        "18 mois après leur création : SOCIETE A (4 mois), SOCIETE B (7 mois), "
        "SOCIETE C (12 mois) ; cette personne n'a pas encore été étendue."
    )


def test_an_expanded_director_needs_no_hint(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN", expanded=True)
    directed(builder, director, (*SHORT_LIFETIMES, None, None))
    [finding] = findings(builder, settings)
    assert finding.explanation.endswith("SOCIETE C (12 mois).")


def test_too_few_companies_are_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed(builder, director, (*SHORT_LIFETIMES, None))
    assert findings(builder, settings) == []


def test_too_few_short_lived_companies_are_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed(builder, director, (FOUR_MONTHS, SEVEN_MONTHS, EIGHTEEN_MONTHS, None, None))
    assert findings(builder, settings) == []


def test_unknown_dates_do_not_make_a_company_short_lived(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed(builder, director, (FOUR_MONTHS, SEVEN_MONTHS, None, None, None))
    undated = builder.company("SANS DATE", None, closing_date=FOUR_MONTHS)
    builder.mandate(director, undated)
    reopened = builder.company("FERMEE AVANT", TWELVE_MONTHS, closing_date=FOUR_MONTHS)
    builder.mandate(director, reopened)
    assert findings(builder, settings) == []


def test_twice_the_minimum_is_severe(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed(builder, director, SHORT_LIFETIMES * 2)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.HIGH
    assert finding.strength == pytest.approx(1.0)


def test_a_liquidation_makes_it_severe_and_is_explained(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN", expanded=True)
    companies = directed(builder, director, (*SHORT_LIFETIMES, None, None))
    builder.notice(
        companies[1],
        NoticeFamily.INSOLVENCY,
        date(2024, 6, 3),
        "Jugement d'ouverture de liquidation judiciaire",
    )
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.HIGH
    assert finding.strength == pytest.approx(0.5 * (0.6 + 0.4 * 0.6) + 0.2)
    assert finding.explanation.endswith(
        "SOCIETE C (12 mois) ; 1 a fermé après une liquidation judiciaire."
    )


@pytest.mark.parametrize(
    "role",
    ["Commissaire aux comptes", "Commissaire aux comptes suppléant", "Liquidateur judiciaire"],
)
def test_auditors_and_court_appointed_officers_are_excluded(
    builder: InvestigationBuilder, settings: RuleSettings, role: str
) -> None:
    auditor = builder.person("Claire", "AUDIT")
    directed(builder, auditor, (*SHORT_LIFETIMES, None, None), role)
    assert findings(builder, settings) == []


def test_excluded_roles_can_be_tuned(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    auditor = builder.person("Claire", "AUDIT")
    directed(builder, auditor, (*SHORT_LIFETIMES, None, None), "Commissaire aux comptes")
    tuned = replace(settings, thresholds={**settings.thresholds, "excluded_roles": []})
    assert [finding.subject for finding in findings(builder, tuned)] == [auditor]


def test_records_confirmed_as_the_same_person_are_counted_together(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    first = builder.person("Jean", "DUPONT", expanded=True)
    second = builder.person("Jean Pierre", "DUPONT", expanded=True)
    directed(builder, first, (FOUR_MONTHS, SEVEN_MONTHS, None))
    other = builder.company("SOCIETE D", CREATED, closing_date=TWELVE_MONTHS)
    builder.mandate(second, other)
    builder.mandate(second, builder.company("SOCIETE E", CREATED))
    assert findings(builder, settings) == []
    builder.same_person(first, second)
    [finding] = findings(builder, settings)
    assert finding.subject == min(first, second)
    assert max(first, second) in finding.justifying_entities
    assert finding.explanation.endswith(" ; le décompte réunit 2 fiches de la même personne.")


def test_probable_homonyms_can_be_counted_together(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    first = builder.person("Jean", "DUPONT", expanded=True)
    second = builder.person("Jean Pierre", "DUPONT", expanded=True)
    directed(builder, first, (FOUR_MONTHS, SEVEN_MONTHS, None))
    builder.mandate(second, builder.company("SOCIETE D", CREATED, closing_date=TWELVE_MONTHS))
    builder.mandate(second, builder.company("SOCIETE E", CREATED))
    assert findings(builder, settings) == []
    tuned = replace(settings, thresholds={**settings.thresholds, "include_probable": True})
    [finding] = findings(builder, tuned)
    assert finding.subject == min(first, second)


def test_a_company_directing_companies_is_flagged_without_hint(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    holding = builder.company("HOLDING MARTIN", date(2015, 1, 1))
    directed(builder, holding, (*SHORT_LIFETIMES, None, None), "Président")
    [finding] = findings(builder, settings)
    assert finding.subject == holding
    assert finding.explanation.endswith("SOCIETE C (12 mois).")


def test_thresholds_can_be_tuned(builder: InvestigationBuilder, settings: RuleSettings) -> None:
    director = builder.person("Paul", "MARTIN", expanded=True)
    directed(builder, director, (FOUR_MONTHS, None))
    tuned = replace(
        settings,
        thresholds={**settings.thresholds, "minimum_companies": 2, "minimum_short_lived": 1},
    )
    [finding] = findings(builder, tuned)
    assert finding.explanation == (
        "Paul MARTIN dirige ou a dirigé 2 entreprises de l'enquête, dont 1 fermée moins de "
        "18 mois après leur création : SOCIETE A (4 mois)."
    )


def test_the_engine_gives_the_signal_with_the_rule_severity(
    builder: InvestigationBuilder,
) -> None:
    director = builder.person("Paul", "MARTIN")
    directed(builder, director, (*SHORT_LIFETIMES, None, None))
    [signal] = SignalEngine.configured().signals(builder.context())
    assert signal.title == "Sociétés éphémères en série"
    assert signal.severity is Severity.MEDIUM
    assert signal.score == 0.42
