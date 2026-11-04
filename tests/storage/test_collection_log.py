import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lacis.storage.collection_log import (
    CollectionLog,
    CollectionLogEntry,
    LoggedRequest,
    RequestStatus,
)
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore

SEARCH_ENDPOINT = "https://recherche-entreprises.api.gouv.fr/search"
BODACC_ENDPOINT = "https://bodacc-datadila.opendatasoft.com/api/records"
REQUESTED_AT = datetime(2026, 11, 2, 23, 11, 5, tzinfo=UTC)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def collection_log(connection: sqlite3.Connection) -> CollectionLog:
    return CollectionLog(connection)


def test_a_successful_request_is_recorded_with_all_its_details(
    connection: sqlite3.Connection, collection_log: CollectionLog
) -> None:
    response = ResponseStore(connection).save(
        CollectedResponse(ResponseSource.COMPANY_REGISTER, SEARCH_ENDPOINT, b"{}", REQUESTED_AT)
    )
    request = LoggedRequest(
        requested_at=REQUESTED_AT,
        source=ResponseSource.COMPANY_REGISTER,
        endpoint=SEARCH_ENDPOINT,
        http_status=200,
        duration=timedelta(milliseconds=184),
        response_identifier=response.identifier,
    )
    entry = collection_log.record(request)
    assert entry.request == request
    assert collection_log.entry(entry.identifier) == entry


def test_a_request_served_from_the_cache_is_recorded_as_such(
    collection_log: CollectionLog,
) -> None:
    entry = collection_log.record(
        LoggedRequest(
            REQUESTED_AT,
            ResponseSource.BODACC,
            BODACC_ENDPOINT,
            200,
            timedelta(0),
            served_from_cache=True,
        )
    )
    assert entry.request.served_from_cache
    assert entry.request.duration == timedelta(0)


def test_a_request_refused_by_the_server_is_recorded_with_its_status_and_error(
    collection_log: CollectionLog,
) -> None:
    entry = collection_log.record(
        LoggedRequest(
            REQUESTED_AT,
            ResponseSource.COMPANY_REGISTER,
            SEARCH_ENDPOINT,
            429,
            timedelta(milliseconds=95),
            error="Trop de requêtes : nouvel essai dans 2 secondes.",
        )
    )
    assert entry.request.http_status == 429
    assert entry.request.error == "Trop de requêtes : nouvel essai dans 2 secondes."
    assert entry.request.response_identifier is None


def test_a_request_that_never_reached_the_server_is_recorded_without_status(
    collection_log: CollectionLog,
) -> None:
    entry = collection_log.record(
        LoggedRequest(
            REQUESTED_AT,
            ResponseSource.BODACC,
            BODACC_ENDPOINT,
            None,
            timedelta(seconds=10),
            error="Délai dépassé",
        )
    )
    assert entry.request.http_status is None
    assert entry.request.duration == timedelta(seconds=10)


def test_durations_are_kept_to_the_millisecond(collection_log: CollectionLog) -> None:
    entry = collection_log.record(
        LoggedRequest(
            REQUESTED_AT,
            ResponseSource.BODACC,
            BODACC_ENDPOINT,
            200,
            timedelta(microseconds=1_234_567),
        )
    )
    assert entry.request.duration == timedelta(milliseconds=1235)


def test_a_log_entry_cannot_cite_a_response_that_was_never_stored(
    collection_log: CollectionLog,
) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        collection_log.record(
            LoggedRequest(
                REQUESTED_AT,
                ResponseSource.BODACC,
                BODACC_ENDPOINT,
                200,
                timedelta(milliseconds=12),
                response_identifier=404,
            )
        )


def test_an_unknown_entry_is_refused(collection_log: CollectionLog) -> None:
    with pytest.raises(KeyError):
        collection_log.entry(404)


def request_at(
    minute: int,
    source: ResponseSource,
    http_status: int | None,
    error: str = "",
) -> LoggedRequest:
    endpoint = SEARCH_ENDPOINT if source is ResponseSource.COMPANY_REGISTER else BODACC_ENDPOINT
    return LoggedRequest(
        requested_at=REQUESTED_AT.replace(minute=minute),
        source=source,
        endpoint=endpoint,
        http_status=http_status,
        duration=timedelta(milliseconds=50),
        error=error,
    )


@pytest.fixture
def filled_log(collection_log: CollectionLog) -> CollectionLog:
    for request in [
        request_at(10, ResponseSource.COMPANY_REGISTER, 200),
        request_at(12, ResponseSource.BODACC, 200),
        request_at(14, ResponseSource.COMPANY_REGISTER, 429, "Trop de requêtes"),
        request_at(16, ResponseSource.BODACC, None, "Délai dépassé"),
        request_at(18, ResponseSource.COMPANY_REGISTER, 200, "Réponse illisible"),
    ]:
        collection_log.record(request)
    return collection_log


def minutes_of(entries: list[CollectionLogEntry]) -> list[int]:
    return [entry.request.requested_at.minute for entry in entries]


def test_the_log_is_read_from_the_most_recent_to_the_oldest(filled_log: CollectionLog) -> None:
    assert minutes_of(filled_log.entries()) == [18, 16, 14, 12, 10]


def test_requests_at_the_same_time_keep_their_recording_order_reversed(
    collection_log: CollectionLog,
) -> None:
    first = collection_log.record(request_at(10, ResponseSource.BODACC, 200))
    second = collection_log.record(request_at(10, ResponseSource.BODACC, 200))
    assert [entry.identifier for entry in collection_log.entries()] == [
        second.identifier,
        first.identifier,
    ]


def test_the_log_can_be_filtered_by_source(filled_log: CollectionLog) -> None:
    assert minutes_of(filled_log.entries(source=ResponseSource.BODACC)) == [16, 12]
    assert minutes_of(filled_log.entries(source=ResponseSource.COMPANY_REGISTER)) == [18, 14, 10]


def test_the_log_can_be_filtered_by_status(filled_log: CollectionLog) -> None:
    assert minutes_of(filled_log.entries(status=RequestStatus.SUCCEEDED)) == [12, 10]
    assert minutes_of(filled_log.entries(status=RequestStatus.FAILED)) == [18, 16, 14]


def test_the_log_can_be_filtered_by_source_and_status(filled_log: CollectionLog) -> None:
    failed_register_requests = filled_log.entries(
        source=ResponseSource.COMPANY_REGISTER, status=RequestStatus.FAILED
    )
    assert minutes_of(failed_register_requests) == [18, 14]


@pytest.mark.parametrize(
    ("http_status", "error", "status"),
    [
        (200, "", RequestStatus.SUCCEEDED),
        (204, "", RequestStatus.SUCCEEDED),
        (304, "", RequestStatus.FAILED),
        (404, "", RequestStatus.FAILED),
        (503, "Service indisponible", RequestStatus.FAILED),
        (None, "Délai dépassé", RequestStatus.FAILED),
        (200, "Réponse illisible", RequestStatus.FAILED),
    ],
)
def test_a_request_succeeds_only_with_a_2xx_status_and_no_error(
    http_status: int | None, error: str, status: RequestStatus
) -> None:
    assert request_at(10, ResponseSource.BODACC, http_status, error).status is status


def test_an_empty_log_has_no_entries(collection_log: CollectionLog) -> None:
    assert collection_log.entries() == []
