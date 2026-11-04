import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.entities import (
    CollectedEntity,
    company_identifier,
    mandate_link,
    person_identifier,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)

DUPONT_SERVICES = CollectedEntity(company_identifier("222222222"), "DUPONT SERVICES")
JEAN_DUPONT = CollectedEntity(person_identifier("DUPONT", "Jean", "1980-05"), "Jean DUPONT")
PRESIDENT = mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président")


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def graph_store(connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(connection)


@pytest.fixture
def response_store(connection: sqlite3.Connection) -> ResponseStore:
    return ResponseStore(connection)


def collect(response_store: ResponseStore, body: bytes, collected_at: datetime) -> ResponseSummary:
    return response_store.save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            body,
            collected_at,
            {"q": "222222222"},
        )
    )


def test_an_entity_lists_the_responses_it_comes_from_with_dates_and_fingerprints(
    graph_store: GraphStore, response_store: ResponseStore
) -> None:
    first = collect(response_store, b'{"page": 1}', datetime(2026, 11, 2, tzinfo=UTC))
    second = collect(response_store, b'{"page": 2}', datetime(2026, 11, 4, tzinfo=UTC))
    graph_store.save_entity(DUPONT_SERVICES, second)
    graph_store.save_entity(DUPONT_SERVICES, first)
    sources = graph_store.sources_of_entity(DUPONT_SERVICES.identifier)
    assert sources == [first, second]
    assert [source.collected_at for source in sources] == [
        datetime(2026, 11, 2, tzinfo=UTC),
        datetime(2026, 11, 4, tzinfo=UTC),
    ]
    assert first.fingerprint != second.fingerprint


def test_the_same_response_is_listed_once(
    graph_store: GraphStore, response_store: ResponseStore
) -> None:
    response = collect(response_store, b"{}", datetime(2026, 11, 2, tzinfo=UTC))
    graph_store.save_entity(DUPONT_SERVICES, response)
    graph_store.save_entity(DUPONT_SERVICES, response)
    assert graph_store.sources_of_entity(DUPONT_SERVICES.identifier) == [response]


def test_a_link_lists_the_responses_it_comes_from(
    graph_store: GraphStore, response_store: ResponseStore
) -> None:
    response = collect(response_store, b"{}", datetime(2026, 11, 2, tzinfo=UTC))
    graph_store.save_entity(DUPONT_SERVICES, response)
    graph_store.save_entity(JEAN_DUPONT, response)
    graph_store.save_link(PRESIDENT, response)
    assert graph_store.sources_of_link(PRESIDENT.identifier) == [response]


def test_entities_only_list_their_own_sources(
    graph_store: GraphStore, response_store: ResponseStore
) -> None:
    company_response = collect(response_store, b"company", datetime(2026, 11, 2, tzinfo=UTC))
    person_response = collect(response_store, b"person", datetime(2026, 11, 3, tzinfo=UTC))
    graph_store.save_entity(DUPONT_SERVICES, company_response)
    graph_store.save_entity(JEAN_DUPONT, person_response)
    assert graph_store.sources_of_entity(JEAN_DUPONT.identifier) == [person_response]
    assert graph_store.sources_of_entity(company_identifier("999999999")) == []


def test_a_fact_cannot_cite_a_response_that_was_never_stored(graph_store: GraphStore) -> None:
    unknown_response = ResponseSummary(
        404,
        ResponseSource.COMPANY_REGISTER,
        "https://recherche-entreprises.api.gouv.fr/search",
        {},
        datetime(2026, 11, 2, tzinfo=UTC),
        "0" * 64,
    )
    with pytest.raises(sqlite3.IntegrityError):
        graph_store.save_entity(DUPONT_SERVICES, unknown_response)
    assert graph_store.entity(DUPONT_SERVICES.identifier) is None
