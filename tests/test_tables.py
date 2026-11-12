import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.details import BadgeTone
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.collection_log import CollectionLog, LoggedRequest, RequestStatus
from lacis.storage.entities import Attributes, Entity, EntityKind, Link, LinkKind
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore
from lacis.tables import (
    NO_SCORE_TEXT,
    EntityRow,
    EntityStatus,
    LogRow,
    entities_summary,
    entity_rows,
    entity_status,
    log_rows,
    log_summary,
    strongest_marks,
)

SEARCH_ENDPOINT = "https://recherche-entreprises.api.gouv.fr/search"
BODACC_ENDPOINT = "https://bodacc-datadila.opendatasoft.com/api/records"
REQUESTED_AT = datetime(2026, 11, 2, 8, 9, 31, tzinfo=UTC)
FINGERPRINT = "3fe8a5f9ff318929" + "0" * 48


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def rows_by_identifier(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> dict[str, EntityRow]:
    rows = entity_rows(builder.connection, phoenix_report(scenario))
    return {row.identifier: row for row in rows}


def test_each_entity_has_its_kind_status_score_and_links(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = rows_by_identifier(builder, scenario)
    assert len(rows) == 9
    dupont = rows[scenario.dupont_services]
    assert dupont.label == "DUPONT SERVICES"
    assert dupont.kind_label == "Entreprise"
    assert dupont.status == EntityStatus("Fermée", BadgeTone.CLOSED)
    assert dupont.status_text == "Fermée"
    assert dupont.severity is Severity.HIGH
    assert dupont.written_score == "0,85"
    assert dupont.spoken_score == "score 0,85, gravité forte"
    assert dupont.flagged
    assert dupont.links == 3
    assert rows[scenario.acme].status_text == "Active"
    assert rows[scenario.acme].links == 5
    assert rows[scenario.jean].links == 1
    assert rows[scenario.jean].flagged
    assert rows[scenario.invest].status_text == "Étranger"
    assert rows[scenario.dupont_office].status_text == "Fermé"
    assert rows[scenario.acme_office].status is None
    address = rows[scenario.address]
    assert address.status_text == ""
    assert address.links == 4
    assert not address.flagged
    assert address.written_score == NO_SCORE_TEXT
    assert address.spoken_score == "aucun signal"
    assert address.sort_score == (-1, -1.0)
    assert dupont.sort_score == (Severity.HIGH.rank, 0.85)


def test_without_signals_no_entity_is_flagged(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    rows = entity_rows(builder.connection, None)
    assert not any(row.flagged for row in rows)
    assert entities_summary(tuple(rows)) == "9 entités · 0 signalée"


def test_an_entity_keeps_its_strongest_signal(scenario: PlumbersScenario) -> None:
    weak = Signal("rule", "Faible", scenario.acme, Severity.LOW, 0.95, "", ())
    strong = Signal("rule", "Forte", scenario.acme, Severity.HIGH, 0.4, "", ())
    medium = Signal("rule", "Moyenne", scenario.acme, Severity.MEDIUM, 0.6, "", ())
    report = SignalReport((weak, strong, medium), 1, REQUESTED_AT.date(), "", REQUESTED_AT)
    mark = strongest_marks(report)[scenario.acme]
    assert (mark.severity, mark.score) == (Severity.HIGH, 0.4)
    assert (
        entities_summary((EntityRow("a", EntityKind.PERSON, "A", None, Severity.LOW, 0.2, 0),))
        == "1 entité · 1 signalée"
    )
    assert (
        entities_summary(
            tuple(
                EntityRow(name, EntityKind.PERSON, name, None, Severity.LOW, 0.2, 0)
                for name in "ab"
            )
        )
        == "2 entités · 2 signalées"
    )


def entity(kind: EntityKind, attributes: Attributes) -> Entity:
    return Entity(f"{kind.value}:1", kind, "X", attributes, REQUESTED_AT, REQUESTED_AT)


def mandate_from(company: Entity) -> Link:
    return Link(
        "link:1",
        LinkKind.MANDATE,
        company.identifier,
        "person:1",
        "Gérant",
        REQUESTED_AT,
        REQUESTED_AT,
    )


def test_a_company_known_only_as_director_is_partial() -> None:
    company = entity(EntityKind.COMPANY, {})
    assert entity_status(company, [mandate_from(company)]) == EntityStatus(
        "Partielle", BadgeTone.OUTLINE
    )
    assert entity_status(company, []) is None
    assert entity_status(entity(EntityKind.ESTABLISHMENT, {"is_open": True}), []) == (
        EntityStatus("Ouvert", BadgeTone.ACTIVE)
    )


def record(builder: InvestigationBuilder, request: LoggedRequest) -> None:
    CollectionLog(builder.connection).record(request)


def test_the_log_lists_the_requests_from_the_most_recent(builder: InvestigationBuilder) -> None:
    response = ResponseStore(builder.connection).save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            SEARCH_ENDPOINT,
            b'{"results": []}',
            REQUESTED_AT,
            {"q": "111111111", "page": "1"},
        )
    )
    record(
        builder,
        LoggedRequest(
            REQUESTED_AT,
            ResponseSource.COMPANY_REGISTER,
            SEARCH_ENDPOINT,
            200,
            timedelta(milliseconds=184),
            response_identifier=response.identifier,
        ),
    )
    record(
        builder,
        LoggedRequest(
            REQUESTED_AT + timedelta(seconds=5),
            ResponseSource.COMPANY_REGISTER,
            SEARCH_ENDPOINT,
            None,
            timedelta(milliseconds=2),
            served_from_cache=True,
            response_identifier=response.identifier,
        ),
    )
    record(
        builder,
        LoggedRequest(
            REQUESTED_AT + timedelta(seconds=10),
            ResponseSource.BODACC,
            BODACC_ENDPOINT,
            None,
            timedelta(milliseconds=30),
            error="Le service BODACC est injoignable.",
        ),
    )
    failed, cached, fetched = log_rows(builder.connection)
    moment = REQUESTED_AT.astimezone()
    assert fetched.written_time == moment.strftime("%H:%M:%S")
    assert fetched.request_text == "Recherche · 111111111"
    assert fetched.status_text == "200"
    assert fetched.origin_text == "réseau"
    assert fetched.written_duration == "184 ms"
    assert fetched.succeeded
    assert fetched.short_fingerprint == response.fingerprint[:16]
    assert fetched.description == "\n".join(
        [
            moment.strftime("%d/%m/%Y à %H:%M:%S") + " · Recherche d'entreprises · 184 ms",
            SEARCH_ENDPOINT,
            "page=1, q=111111111",
            f"sha256:{response.fingerprint}",
        ]
    )
    assert cached.origin_text == "cache"
    assert cached.status_text == NO_SCORE_TEXT
    assert failed.status is RequestStatus.FAILED
    assert failed.status_text == "Échec"
    assert failed.request_text == "BODACC · /api/records"
    assert failed.fingerprint == ""
    assert failed.description.endswith("\nLe service BODACC est injoignable.")
    rows = (failed, cached, fetched)
    assert log_summary(rows) == "3 requêtes · 1 servie par le cache · 1 échec"


def test_the_log_summary_counts_the_cache_and_the_failures() -> None:
    assert log_summary(()) == "Aucune requête pour l'instant"
    succeeded = LogRow(
        1,
        REQUESTED_AT,
        ResponseSource.BODACC,
        "relative",
        200,
        timedelta(0),
        True,
        RequestStatus.SUCCEEDED,
    )
    assert succeeded.request_text == "BODACC · relative"
    assert log_summary((succeeded, succeeded)) == "2 requêtes · 2 servies par le cache"
