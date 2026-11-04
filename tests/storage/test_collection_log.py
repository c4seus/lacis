import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lacis.storage.collection_log import CollectionLog, LoggedRequest
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
