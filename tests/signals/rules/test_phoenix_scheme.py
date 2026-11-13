import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import httpx
import pytest

from fake_time import FakeTime
from investigation_builder import TODAY, InvestigationBuilder
from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import GraphExpander
from lacis.signals.configuration import load_configuration
from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine
from lacis.signals.rule_settings import RuleSettings
from lacis.signals.rules import RULES
from lacis.signals.rules.phoenix_scheme import (
    PhoenixSchemeRule,
    delay_text,
    name_words,
    names_are_close,
)
from lacis.signals.signal import Finding, Severity
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import person_identifier
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.notices import NoticeFamily
from lacis.storage.responses import ResponseStore

RULE = PhoenixSchemeRule()
PLUMBING = "43.22A"
CLOSED_ON = date(2023, 1, 15)
LIQUIDATION = "Jugement d'ouverture de liquidation judiciaire"
DESIGN_TARGET = (
    "DUPONT SERVICES a fermé le 15/01/2023 après une liquidation judiciaire ; "
    "ACME PLOMBERIE, même dirigeant (Jean DUPONT) et même activité (43.22A), "
    "a été créée 2 mois plus tôt. Indices : même adresse."
)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)[RULE.name]


def findings(builder: InvestigationBuilder, settings: RuleSettings) -> list[Finding]:
    return RULE.evaluate(builder.context(), settings)


def closed_company(
    builder: InvestigationBuilder,
    director: str,
    label: str = "SERVICES MARTIN",
    judgment: str = LIQUIDATION,
) -> str:
    company = builder.company(label, date(2019, 4, 2), PLUMBING, closing_date=CLOSED_ON)
    builder.mandate(director, company, "Président")
    builder.notice(company, NoticeFamily.INSOLVENCY, date(2022, 6, 14), judgment)
    return company


def successor(
    builder: InvestigationBuilder,
    director: str,
    created: date = date(2022, 11, 10),
    label: str = "ACME PLOMBERIE",
    role: str = "Gérant",
) -> str:
    company = builder.company(label, created, PLUMBING)
    builder.mandate(director, company, role)
    return company


def test_the_rule_ships_with_its_default_thresholds(settings: RuleSettings) -> None:
    assert RULE in RULES
    assert settings.severity is Severity.LOW
    assert settings.whole_number("window_months") == 12
    assert settings.number("name_overlap") == 0.5
    assert not settings.switch("include_probable")
    assert "Commissaire aux comptes" in settings.texts("excluded_roles")


def test_a_successor_created_shortly_before_a_liquidated_company_closed_is_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed = closed_company(builder, director)
    new = successor(builder, director)
    [finding] = findings(builder, settings)
    assert finding.subject == new
    assert finding.justifying_entities == (closed, director)
    assert finding.severity is Severity.MEDIUM
    assert finding.strength == pytest.approx(0.7)
    assert finding.explanation == (
        "SERVICES MARTIN a fermé le 15/01/2023 après une liquidation judiciaire ; "
        "ACME PLOMBERIE, même dirigeant (Paul MARTIN) et même activité (43.22A), "
        "a été créée 2 mois plus tôt."
    )


def test_a_successor_created_after_the_closing_is_flagged_too(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed_company(builder, director)
    successor(builder, director, date(2023, 6, 20))
    [finding] = findings(builder, settings)
    assert "a été créée 5 mois plus tard." in finding.explanation


def test_clues_make_the_signal_stronger_and_severe(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed = closed_company(builder, director, "PLOMBERIE MARTIN")
    new = successor(builder, director, label="MARTIN PLOMBERIE NOUVELLE")
    address = builder.address("12 rue des Lilas 31000 Toulouse")
    builder.registered_office(closed, address)
    builder.registered_office(new, address)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.HIGH
    assert finding.strength == pytest.approx(1.0)
    assert finding.explanation.endswith(" Indices : même adresse, nom proche.")


def test_another_insolvency_proceeding_is_named_as_such(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed_company(builder, director, judgment="Jugement de redressement judiciaire")
    successor(builder, director)
    [finding] = findings(builder, settings)
    assert "a fermé le 15/01/2023 après une procédure collective ;" in finding.explanation
    assert finding.severity is None
    assert finding.strength == pytest.approx(0.5)


def test_a_company_closed_without_insolvency_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    company = builder.company(
        "SERVICES MARTIN", date(2019, 4, 2), PLUMBING, closing_date=CLOSED_ON
    )
    builder.mandate(director, company)
    builder.notice(company, NoticeFamily.REMOVAL, date(2023, 1, 20), "Radiation.")
    successor(builder, director)
    assert findings(builder, settings) == []


def test_a_company_still_open_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    company = builder.company("SERVICES MARTIN", date(2019, 4, 2), PLUMBING)
    builder.mandate(director, company)
    builder.notice(company, NoticeFamily.INSOLVENCY, date(2022, 6, 14), LIQUIDATION)
    successor(builder, director)
    assert findings(builder, settings) == []


def test_a_successor_outside_the_window_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed_company(builder, director)
    successor(builder, director, date(2021, 12, 1))
    successor(builder, director, date(2024, 2, 1), "PLOMBIER TARDIF")
    assert findings(builder, settings) == []


def test_the_window_can_be_tuned(builder: InvestigationBuilder, settings: RuleSettings) -> None:
    director = builder.person("Paul", "MARTIN")
    closed_company(builder, director)
    successor(builder, director, date(2021, 12, 1))
    tuned = replace(settings, thresholds={**settings.thresholds, "window_months": 14})
    [finding] = findings(builder, tuned)
    assert "a été créée 13 mois plus tôt." in finding.explanation


def test_another_activity_or_another_director_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed_company(builder, director)
    other_activity = builder.company("BOULANGERIE MARTIN", date(2022, 11, 10), "10.71C")
    builder.mandate(director, other_activity)
    successor(builder, builder.person("Lucie", "BERNARD"))
    assert findings(builder, settings) == []


def test_an_older_company_is_not_a_successor(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    closed = builder.company(
        "SERVICES MARTIN", date(2022, 12, 1), PLUMBING, closing_date=CLOSED_ON
    )
    builder.mandate(director, closed)
    builder.notice(closed, NoticeFamily.INSOLVENCY, date(2022, 12, 20), LIQUIDATION)
    successor(builder, director)
    assert findings(builder, settings) == []


def test_companies_without_known_activity_or_creation_are_left_out(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    director = builder.person("Paul", "MARTIN")
    no_activity = builder.company("SANS ACTIVITE", date(2019, 4, 2), closing_date=CLOSED_ON)
    builder.mandate(director, no_activity)
    builder.notice(no_activity, NoticeFamily.INSOLVENCY, date(2022, 6, 14), LIQUIDATION)
    closed_company(builder, director)
    undated = builder.company("SANS DATE", None, PLUMBING)
    builder.mandate(director, undated)
    assert findings(builder, settings) == []


@pytest.mark.parametrize(
    "role", ["Commissaire aux comptes titulaire", "Administrateur judiciaire"]
)
def test_auditors_and_court_appointed_officers_are_excluded(
    builder: InvestigationBuilder, settings: RuleSettings, role: str
) -> None:
    officer = builder.person("Claire", "AUDIT")
    closed = builder.company("SERVICES MARTIN", date(2019, 4, 2), PLUMBING, closing_date=CLOSED_ON)
    builder.mandate(officer, closed, role)
    builder.notice(closed, NoticeFamily.INSOLVENCY, date(2022, 6, 14), LIQUIDATION)
    successor(builder, officer, role=role)
    assert findings(builder, settings) == []


def test_several_shared_directors_are_named(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    first = builder.person("Paul", "MARTIN")
    second = builder.person("Lucie", "BERNARD")
    closed = closed_company(builder, first)
    builder.mandate(second, closed)
    new = successor(builder, first)
    builder.mandate(second, new)
    [finding] = findings(builder, settings)
    assert "mêmes dirigeants (Lucie BERNARD, Paul MARTIN)" in finding.explanation


def test_homonyms_confirmed_as_one_person_are_the_same_director(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    jean = builder.person("Jean", "DUPONT")
    jean_pierre = builder.person("Jean Pierre", "DUPONT")
    closed_company(builder, jean, "DUPONT SERVICES")
    successor(builder, jean_pierre)
    assert findings(builder, settings) == []
    builder.same_person(jean, jean_pierre)
    [finding] = findings(builder, settings)
    assert finding.justifying_entities[1:] == (jean, jean_pierre)
    assert "même dirigeant (Jean DUPONT)" in finding.explanation
    tuned = replace(settings, thresholds={**settings.thresholds, "include_probable": True})
    assert len(findings(builder, tuned)) == 1


def test_names_are_close_when_most_of_their_words_are_shared() -> None:
    assert name_words("SARL Les Plombiers du Sud") == {"PLOMBIERS", "SUD"}
    assert names_are_close("PLOMBERIE MARTIN", "MARTIN PLOMBERIE NOUVELLE", 0.5)
    assert not names_are_close("DUPONT SERVICES", "ACME PLOMBERIE", 0.5)
    assert not names_are_close("SAS", "ACME PLOMBERIE", 0.5)


def test_delays_are_written_in_months() -> None:
    assert delay_text(date(2023, 1, 2), CLOSED_ON) == "le même mois"
    assert delay_text(date(2022, 11, 10), CLOSED_ON) == "2 mois plus tôt"
    assert delay_text(date(2023, 6, 20), CLOSED_ON) == "5 mois plus tard"


@pytest.fixture
def expander(
    investigation_connection: sqlite3.Connection,
    response_store: ResponseStore,
    collection_log: CollectionLog,
) -> Iterator[GraphExpander]:
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            sleep=fake_time.sleep,
            monotonic=fake_time.clock,
        ),
    )
    yield GraphExpander(investigation_connection, CompanyRegister(client), Bodacc(client))
    client.close()


def test_the_phoenix_signal_of_the_design_target_appears_on_the_fake_plumbers(
    expander: GraphExpander, investigation_connection: sqlite3.Connection
) -> None:
    expander.expand_company("111111111")
    expander.expand_company("222222222")
    jean = person_identifier("DUPONT", "Jean", "1980-05")
    jean_pierre = person_identifier("DUPONT", "Jean Pierre", "1980-05")
    HomonymDecisionStore(investigation_connection).record(
        jean, jean_pierre, HomonymDecision.SAME_PERSON
    )
    signals = SignalEngine.configured().signals(
        InvestigationContext(investigation_connection, TODAY)
    )
    [signal] = [signal for signal in signals if signal.rule == RULE.name]
    assert signal.title == "Schéma phénix"
    assert signal.severity is Severity.HIGH
    assert signal.score == 0.85
    assert signal.subject == "company:111111111"
    assert signal.justifying_entities == ("company:222222222", jean, jean_pierre)
    assert signal.explanation == DESIGN_TARGET
