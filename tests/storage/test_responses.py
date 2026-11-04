import hashlib
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.errors import TamperedResponseError
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    fingerprint,
)

COLLECTED_AT = datetime(2026, 11, 2, 23, 11, tzinfo=UTC)
COMPANY_BODY = b'{"results": [{"siren": "222222222", "nom_complet": "DUPONT SERVICES"}]}'
SEARCH_RESPONSE = CollectedResponse(
    source=ResponseSource.COMPANY_REGISTER,
    url="https://recherche-entreprises.api.gouv.fr/search",
    parameters={"q": "222222222", "page": "1"},
    body=COMPANY_BODY,
    collected_at=COLLECTED_AT,
)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def response_store(connection: sqlite3.Connection) -> ResponseStore:
    return ResponseStore(connection)


def test_the_fingerprint_is_the_sha256_of_the_body() -> None:
    assert fingerprint(COMPANY_BODY) == hashlib.sha256(COMPANY_BODY).hexdigest()
    assert len(fingerprint(b"")) == 64


def test_a_response_is_stored_with_its_source_url_parameters_date_and_fingerprint(
    response_store: ResponseStore,
) -> None:
    summary = response_store.save(SEARCH_RESPONSE)
    assert summary.source is ResponseSource.COMPANY_REGISTER
    assert summary.url == "https://recherche-entreprises.api.gouv.fr/search"
    assert summary.parameters == {"q": "222222222", "page": "1"}
    assert summary.collected_at == COLLECTED_AT
    assert summary.fingerprint == hashlib.sha256(COMPANY_BODY).hexdigest()


def test_the_raw_body_is_kept_byte_for_byte(response_store: ResponseStore) -> None:
    body = "Société « DUPONT » é\n\x00".encode()
    summary = response_store.save(
        CollectedResponse(
            ResponseSource.BODACC, "https://bodacc.example/annonces", body, COLLECTED_AT
        )
    )
    stored = response_store.read(summary.identifier)
    assert stored.body == body
    assert stored.summary == summary


def test_each_collection_is_kept_even_with_the_same_body(response_store: ResponseStore) -> None:
    first = response_store.save(SEARCH_RESPONSE)
    second = response_store.save(SEARCH_RESPONSE)
    assert first.identifier != second.identifier
    assert first.fingerprint == second.fingerprint
    assert [summary.identifier for summary in response_store.summaries()] == [
        first.identifier,
        second.identifier,
    ]


def test_responses_are_listed_by_collection_date(response_store: ResponseStore) -> None:
    later = response_store.save(SEARCH_RESPONSE)
    earlier = response_store.save(
        CollectedResponse(
            ResponseSource.BODACC,
            "https://bodacc.example/annonces",
            b"[]",
            datetime(2026, 11, 1, tzinfo=UTC),
        )
    )
    assert [summary.identifier for summary in response_store.summaries()] == [
        earlier.identifier,
        later.identifier,
    ]


def test_an_unknown_response_is_refused(response_store: ResponseStore) -> None:
    with pytest.raises(KeyError):
        response_store.read(404)


def tamper(connection: sqlite3.Connection, statement: str, identifier: int) -> None:
    with connection:
        connection.execute(statement, (identifier,))


def test_an_untouched_response_is_read_without_complaint(response_store: ResponseStore) -> None:
    summary = response_store.save(SEARCH_RESPONSE)
    assert response_store.read(summary.identifier).body == COMPANY_BODY


def test_a_response_whose_body_was_modified_is_reported_when_read(
    connection: sqlite3.Connection, response_store: ResponseStore
) -> None:
    summary = response_store.save(SEARCH_RESPONSE)
    tamper(
        connection,
        "UPDATE response SET body = replace(body, 'DUPONT', 'DURAND') WHERE identifier = ?",
        summary.identifier,
    )
    with pytest.raises(TamperedResponseError) as tampering:
        response_store.read(summary.identifier)
    assert str(tampering.value) == (
        f"La réponse n\u00a0{summary.identifier} a été modifiée depuis sa collecte\u00a0: "
        "son contenu ne correspond plus à l'empreinte enregistrée."
    )
    assert tampering.value.expected_fingerprint == summary.fingerprint
    assert tampering.value.actual_fingerprint == fingerprint(
        COMPANY_BODY.replace(b"DUPONT", b"DURAND")
    )


def test_a_response_whose_fingerprint_was_modified_is_reported_when_read(
    connection: sqlite3.Connection, response_store: ResponseStore
) -> None:
    summary = response_store.save(SEARCH_RESPONSE)
    tamper(
        connection,
        "UPDATE response SET fingerprint = '" + "0" * 64 + "' WHERE identifier = ?",
        summary.identifier,
    )
    with pytest.raises(TamperedResponseError):
        response_store.read(summary.identifier)
