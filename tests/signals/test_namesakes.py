import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import date

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import SHARED_ADDRESS
from lacis.collectors.fictional_records import (
    FictionalCompany,
    FictionalEstablishment,
    FictionalNaturalPerson,
    FictionalScenario,
)
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import GraphExpander
from lacis.signals.configuration import load_configuration
from lacis.signals.context import InvestigationContext
from lacis.signals.engine import SignalEngine
from lacis.signals.rules import RULES
from lacis.signals.signal import Signal
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import EntityKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.responses import ResponseStore

CREATION_DATES = ("2025-01-10", "2025-02-01", "2025-03-15")
NAMESAKE_COMPANIES = tuple(
    FictionalCompany(
        siren=f"{digit}" * 9,
        name=f"MARTIN NUMERO {digit}",
        establishments=(
            FictionalEstablishment(
                "00012", replace(SHARED_ADDRESS, number=f"{digit}"), creation_date
            ),
        ),
        directors=(FictionalNaturalPerson("MARTIN", "Paul", "1990-01", "Gérant"),),
        creation_date=creation_date,
    )
    for digit, creation_date in zip("789", CREATION_DATES, strict=True)
)


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
        httpx.MockTransport(FakeApi(FictionalScenario(NAMESAKE_COMPANIES, ()))),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            monotonic=fake_time.clock,
        ),
    )
    expander = GraphExpander(investigation_connection, CompanyRegister(client), Bodacc(client))
    for company in NAMESAKE_COMPANIES:
        expander.expand_company(company.siren)
    yield expander
    client.close()


def bursts(connection: sqlite3.Connection, engine: SignalEngine) -> list[Signal]:
    signals = engine.signals(InvestigationContext(connection, date(2026, 11, 10)))
    return [signal for signal in signals if signal.rule == "creation_burst"]


def namesakes(connection: sqlite3.Connection) -> list[str]:
    return sorted(
        entity.identifier
        for entity in GraphStore(connection).entities()
        if entity.kind is EntityKind.PERSON
    )


@pytest.mark.usefixtures("expander")
def test_namesakes_of_unrelated_companies_are_not_counted_together(
    investigation_connection: sqlite3.Connection,
) -> None:
    assert len(namesakes(investigation_connection)) == 3
    assert bursts(investigation_connection, SignalEngine.configured()) == []


@pytest.mark.usefixtures("expander")
def test_namesakes_count_together_once_the_investigator_confirms_them(
    investigation_connection: sqlite3.Connection,
) -> None:
    first, second, third = namesakes(investigation_connection)
    decisions = HomonymDecisionStore(investigation_connection)
    decisions.record(first, second, HomonymDecision.SAME_PERSON)
    decisions.record(second, third, HomonymDecision.SAME_PERSON)
    [burst] = bursts(investigation_connection, SignalEngine.configured())
    assert burst.subject == first
    assert burst.explanation.startswith("3 entreprises créées en 65 jours")


@pytest.mark.usefixtures("expander")
def test_namesakes_count_together_when_the_settings_include_probable_matches(
    investigation_connection: sqlite3.Connection,
) -> None:
    configuration = load_configuration(RULES)
    settings = configuration["creation_burst"]
    configuration["creation_burst"] = replace(
        settings, thresholds={**settings.thresholds, "include_probable": True}
    )
    assert len(bursts(investigation_connection, SignalEngine(RULES, configuration))) == 1
