import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.notices import CollectedNotice, NoticeFamily, NoticeStore
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)

FIRST_COLLECTION = datetime(2026, 11, 2, 23, 11, tzinfo=UTC)
SECOND_COLLECTION = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
EARLIER_COLLECTION = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)
TOULOUSE_COURT = "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE"

REMOVAL = CollectedNotice(
    identifier="B202300150001",
    family=NoticeFamily.REMOVAL,
    published_on=date(2023, 1, 20),
    court=TOULOUSE_COURT,
    summary="Radiation du registre du commerce et des sociétés",
)
INSOLVENCY = CollectedNotice(
    identifier="A202202360042",
    family=NoticeFamily.INSOLVENCY,
    published_on=date(2022, 12, 5),
    court=TOULOUSE_COURT,
    summary="Jugement de clôture pour insuffisance d'actif.",
    judgment="Jugement prononçant la clôture de la procédure, jugement du 28/11/2022",
)


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def notice_store(connection: sqlite3.Connection) -> NoticeStore:
    return NoticeStore(connection)


def bodacc_response(connection: sqlite3.Connection, collected_at: datetime) -> ResponseSummary:
    return ResponseStore(connection).save(
        CollectedResponse(
            ResponseSource.BODACC,
            "https://bodacc-datadila.opendatasoft.com/api/records",
            b"{}",
            collected_at,
            {"siren": "222222222"},
        )
    )


def test_a_notice_is_stored_with_its_details_and_source_response(
    connection: sqlite3.Connection, notice_store: NoticeStore
) -> None:
    response = bodacc_response(connection, FIRST_COLLECTION)
    stored = notice_store.save_notice(INSOLVENCY, response)
    assert stored.identifier == "A202202360042"
    assert stored.family is NoticeFamily.INSOLVENCY
    assert stored.published_on == date(2022, 12, 5)
    assert stored.court == TOULOUSE_COURT
    assert stored.judgment.startswith("Jugement prononçant la clôture")
    assert stored.summary == "Jugement de clôture pour insuffisance d'actif."
    assert stored.response_identifier == response.identifier
    assert stored.first_collected_at == stored.last_collected_at == FIRST_COLLECTION
    assert notice_store.notice("A202202360042") == stored


@pytest.mark.parametrize("family", list(NoticeFamily))
def test_every_notice_family_is_stored(
    connection: sqlite3.Connection, notice_store: NoticeStore, family: NoticeFamily
) -> None:
    notice = CollectedNotice(f"NOTICE-{family}", family, date(2024, 1, 1), TOULOUSE_COURT, "")
    stored = notice_store.save_notice(notice, bodacc_response(connection, FIRST_COLLECTION))
    assert stored.family is family
    assert stored.judgment == ""


def test_collecting_a_notice_again_updates_it_without_duplicating_it(
    connection: sqlite3.Connection, notice_store: NoticeStore
) -> None:
    notice_store.save_notice(REMOVAL, bodacc_response(connection, FIRST_COLLECTION))
    corrected = CollectedNotice(
        REMOVAL.identifier, REMOVAL.family, REMOVAL.published_on, TOULOUSE_COURT, "Radiation"
    )
    second_response = bodacc_response(connection, SECOND_COLLECTION)
    updated = notice_store.save_notice(corrected, second_response)
    assert updated.summary == "Radiation"
    assert updated.response_identifier == second_response.identifier
    assert updated.first_collected_at == FIRST_COLLECTION
    assert updated.last_collected_at == SECOND_COLLECTION
    assert connection.execute("SELECT COUNT(*) FROM notice").fetchone() == (1,)


def test_an_older_collection_never_overwrites_a_newer_notice(
    connection: sqlite3.Connection, notice_store: NoticeStore
) -> None:
    newer_response = bodacc_response(connection, SECOND_COLLECTION)
    notice_store.save_notice(REMOVAL, newer_response)
    outdated = CollectedNotice(
        REMOVAL.identifier, REMOVAL.family, REMOVAL.published_on, TOULOUSE_COURT, "Ancien"
    )
    updated = notice_store.save_notice(outdated, bodacc_response(connection, EARLIER_COLLECTION))
    assert updated.summary == REMOVAL.summary
    assert updated.response_identifier == newer_response.identifier
    assert updated.first_collected_at == EARLIER_COLLECTION
    assert updated.last_collected_at == SECOND_COLLECTION


def test_a_notice_cannot_cite_a_response_that_was_never_stored(
    notice_store: NoticeStore,
) -> None:
    unknown_response = ResponseSummary(
        404, ResponseSource.BODACC, "https://bodacc.example", {}, FIRST_COLLECTION, "0" * 64
    )
    with pytest.raises(sqlite3.IntegrityError):
        notice_store.save_notice(REMOVAL, unknown_response)
    assert notice_store.notice(REMOVAL.identifier) is None


def test_a_missing_notice_is_none(notice_store: NoticeStore) -> None:
    assert notice_store.notice("UNKNOWN") is None
    with pytest.raises(KeyError):
        notice_store.require_notice("UNKNOWN")
