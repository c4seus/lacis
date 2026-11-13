import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, date, datetime

import httpx
import pytest

from fake_time import FakeTime
from investigation_builder import COURT, TODAY, InvestigationBuilder
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
from lacis.signals.rules.foreign_office_transfer import ForeignOfficeTransferRule
from lacis.signals.signal import Finding, Severity
from lacis.storage.collection_log import CollectionLog
from lacis.storage.notices import (
    CollectedNotice,
    NoticeFamily,
    NoticeRole,
    OfficeTransfer,
)
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore

RULE = ForeignOfficeTransferRule()
TO_BELGIUM = OfficeTransfer("Belgique", date(2025, 9, 1), effective_date_stated=True)
TRANSFER_SUMMARY = "Transfert du siège social à Bruxelles (Belgique)."


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def settings() -> RuleSettings:
    return load_configuration(RULES)[RULE.name]


def findings(builder: InvestigationBuilder, settings: RuleSettings) -> list[Finding]:
    return RULE.evaluate(builder.context(), settings)


def test_the_rule_ships_with_its_default_thresholds(settings: RuleSettings) -> None:
    assert RULE in RULES
    assert settings.severity is Severity.LOW
    assert dict(settings.thresholds) == {"recent_years": 5}


def test_a_recent_transfer_abroad_is_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    builder.notice(
        company, NoticeFamily.AMENDMENT, date(2025, 9, 15), TRANSFER_SUMMARY, TO_BELGIUM
    )
    [finding] = findings(builder, settings)
    assert finding.subject == company
    assert finding.justifying_entities == (company,)
    assert finding.strength == 1.0
    assert finding.severity is Severity.MEDIUM
    assert finding.explanation == (
        "Siège transféré à l'étranger (Belgique) le 01/09/2025, selon l'annonce publiée au "
        f"BODACC le 15/09/2025 ({COURT})."
    )


def test_an_old_transfer_is_flagged_less_strongly(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    old = OfficeTransfer("Suisse", date(2019, 3, 15), effective_date_stated=True)
    builder.notice(company, NoticeFamily.AMENDMENT, date(2019, 4, 2), TRANSFER_SUMMARY, old)
    [finding] = findings(builder, settings)
    assert finding.strength == 0.5
    assert finding.severity is None


def test_a_transfer_on_the_cutoff_day_is_recent(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    cutoff = OfficeTransfer("Suisse", date(TODAY.year - 5, TODAY.month, TODAY.day), True)
    builder.notice(company, NoticeFamily.AMENDMENT, date(2021, 12, 1), TRANSFER_SUMMARY, cutoff)
    [finding] = findings(builder, settings)
    assert finding.severity is Severity.MEDIUM


def test_the_recent_period_can_be_tuned(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    builder.notice(
        company, NoticeFamily.AMENDMENT, date(2025, 9, 15), TRANSFER_SUMMARY, TO_BELGIUM
    )
    tuned = replace(settings, thresholds={"recent_years": 1})
    [finding] = findings(builder, tuned)
    assert finding.strength == 0.5


def test_a_transfer_without_country_nor_date_says_so(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    vague = OfficeTransfer(None, date(2025, 3, 4), effective_date_stated=False)
    builder.notice(company, NoticeFamily.AMENDMENT, date(2025, 3, 4), "Transfert.", vague)
    [finding] = findings(builder, settings)
    assert finding.explanation == (
        "Siège transféré à l'étranger (pays non précisé), selon l'annonce publiée au "
        f"BODACC le 04/03/2025 ({COURT})."
    )


def test_the_latest_of_several_transfers_is_explained(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    first = OfficeTransfer("Suisse", date(2021, 5, 2), effective_date_stated=True)
    builder.notice(company, NoticeFamily.AMENDMENT, date(2021, 5, 20), TRANSFER_SUMMARY, first)
    builder.notice(
        company, NoticeFamily.AMENDMENT, date(2025, 9, 15), TRANSFER_SUMMARY, TO_BELGIUM
    )
    [finding] = findings(builder, settings)
    assert finding.explanation.startswith("Siège transféré à l'étranger (Belgique) le 01/09/2025")
    assert finding.explanation.endswith(", la plus récente de 2 annonces de transfert.")


def test_notices_without_transfer_abroad_are_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("DUPONT SERVICES")
    builder.notice(company, NoticeFamily.REMOVAL, date(2023, 1, 20), "Radiation.")
    builder.company("ACME PLOMBERIE")
    assert findings(builder, settings) == []


def test_a_company_only_mentioned_in_a_transfer_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("ACME PLOMBERIE")
    builder.notice_store.save_notice(
        CollectedNotice(
            "A202500000099",
            NoticeFamily.AMENDMENT,
            date(2025, 9, 15),
            COURT,
            TRANSFER_SUMMARY,
            companies={company: NoticeRole.MENTIONED},
            office_transfer=TO_BELGIUM,
        ),
        builder.bodacc_response,
    )
    assert findings(builder, settings) == []


def test_a_withdrawn_transfer_is_not_flagged(
    builder: InvestigationBuilder, settings: RuleSettings
) -> None:
    company = builder.company("HOLDING DUPONT")
    builder.notice(
        company, NoticeFamily.AMENDMENT, date(2025, 9, 15), TRANSFER_SUMMARY, TO_BELGIUM
    )
    later = ResponseStore(builder.connection).save(
        CollectedResponse(
            ResponseSource.BODACC,
            "https://bodacc.example",
            b"{}",
            datetime(2026, 11, 9, tzinfo=UTC),
        )
    )
    builder.notice_store.record_refresh(company, later, [])
    assert findings(builder, settings) == []


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


def test_the_transfer_of_holding_dupont_becomes_a_signal_once_expanded(
    expander: GraphExpander, investigation_connection: sqlite3.Connection
) -> None:
    expander.expand_company("333333333")
    signals = SignalEngine.configured().signals(
        InvestigationContext(investigation_connection, TODAY)
    )
    transfers = [signal for signal in signals if signal.rule == RULE.name]
    assert [signal.subject for signal in transfers] == ["company:333333333"]
    [signal] = transfers
    assert signal.title == "Transfert du siège à l'étranger"
    assert signal.severity is Severity.MEDIUM
    assert signal.score == 1.0
    assert signal.explanation.startswith("Siège transféré à l'étranger (Belgique) le 01/09/2025")
