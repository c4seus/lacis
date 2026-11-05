import json
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.bodacc import (
    Bodacc,
)
from lacis.collectors.company_register import InvalidQueryError
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import (
    FAKE_PLUMBERS_NOTICES,
    FAKE_PLUMBERS_SCENARIO,
    SHARED_ADDRESS,
)
from lacis.collectors.fictional_records import (
    FictionalCompany,
    FictionalEstablishment,
    FictionalNotice,
    FictionalScenario,
)
from lacis.collectors.http_client import CollectionError, CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.storage.collection_log import CollectionLog
from lacis.storage.notices import NoticeFamily
from lacis.storage.responses import ResponseSource, ResponseStore, ResponseSummary

Handler = Callable[[httpx.Request], httpx.Response]
BodaccFactory = Callable[..., Bodacc]
COURT = "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE"
RESPONSE = ResponseSummary(
    1,
    ResponseSource.BODACC,
    "https://bodacc-datadila.opendatasoft.com/api/records",
    {},
    datetime(2026, 11, 5, 9, 0, tzinfo=UTC),
    "0" * 64,
)
EVERY_FAMILY_COMPANY = FictionalCompany(
    siren="777777777",
    name="TOUTES FAMILLES",
    establishments=(FictionalEstablishment("00015", SHARED_ADDRESS, "2015-01-05"),),
    directors=(),
    creation_date="2015-01-05",
)
EVERY_FAMILY = {
    "creation": ("Créations", NoticeFamily.CREATION),
    "immatriculation": ("Immatriculations", NoticeFamily.REGISTRATION),
    "modification": ("Modifications diverses", NoticeFamily.AMENDMENT),
    "collective": ("Procédures collectives", NoticeFamily.INSOLVENCY),
    "conciliation": ("Procédures de conciliation", NoticeFamily.CONCILIATION),
    "retablissement_professionnel": (
        "Procédures de rétablissement professionnel",
        NoticeFamily.PROFESSIONAL_RECOVERY,
    ),
    "vente": ("Ventes et cessions", NoticeFamily.SALE),
    "dpc": ("Dépôts des comptes", NoticeFamily.ACCOUNTS),
    "radiation": ("Radiations", NoticeFamily.REMOVAL),
    "divers": ("Avis divers", NoticeFamily.MISCELLANEOUS),
}
EVERY_FAMILY_NOTICES = tuple(
    FictionalNotice(
        f"A2015{index:04d}{index:04d}",
        EVERY_FAMILY_COMPANY,
        code,
        label,
        f"2015-02-{index + 1:02d}",
        COURT,
    )
    for index, (code, (label, _)) in enumerate(EVERY_FAMILY.items())
)
SCENARIO = FictionalScenario(
    (*FAKE_PLUMBERS_SCENARIO.companies, EVERY_FAMILY_COMPANY),
    (*FAKE_PLUMBERS_NOTICES, *EVERY_FAMILY_NOTICES),
)


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(SCENARIO)


@pytest.fixture
def bodacc_factory(
    fake_api: FakeApi, response_store: ResponseStore, collection_log: CollectionLog
) -> Iterator[BodaccFactory]:
    http_clients: list[CollectorHttpClient] = []

    def create(handler: Handler = fake_api, **settings: int) -> Bodacc:
        fake_time = FakeTime()
        http_client = CollectorHttpClient(
            response_store,
            collection_log,
            httpx.MockTransport(handler),
            CollectorTiming(
                rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
                monotonic=fake_time.clock,
            ),
        )
        http_clients.append(http_client)
        return Bodacc(http_client, **settings)

    yield create
    for http_client in http_clients:
        http_client.close()


@pytest.fixture
def bodacc(bodacc_factory: BodaccFactory) -> Bodacc:
    return bodacc_factory()


def sent_parameters(fake_api: FakeApi) -> list[dict[str, str]]:
    return [dict(request.url.params) for request in fake_api.requests]


def notice_page(records: list[dict[str, Any]], total_count: int | None = None) -> bytes:
    page = {
        "total_count": len(records) if total_count is None else total_count,
        "results": records,
    }
    return json.dumps(page).encode()


def test_the_notices_of_a_company_are_fetched_by_its_siren_newest_first(
    bodacc: Bodacc, fake_api: FakeApi
) -> None:
    company_notices = bodacc.notices_of("111 111 111")
    assert company_notices.siren == "111111111"
    assert [record["dateparution"] for record in company_notices.records] == [
        "2025-02-03",
        "2024-07-12",
        "2022-11-24",
    ]
    assert company_notices.total_count == 3
    assert company_notices.is_complete
    assert sent_parameters(fake_api) == [
        {
            "where": 'registre="111111111"',
            "order_by": "dateparution desc",
            "limit": "100",
            "offset": "0",
        }
    ]


def test_the_notices_are_fetched_page_by_page(
    bodacc_factory: BodaccFactory, fake_api: FakeApi, response_store: ResponseStore
) -> None:
    bodacc = bodacc_factory(notices_per_page=4)
    company_notices = bodacc.notices_of("777777777")
    assert len(company_notices.pages) == 3
    assert len(company_notices.records) == len(EVERY_FAMILY)
    assert company_notices.is_complete
    assert [parameters["offset"] for parameters in sent_parameters(fake_api)] == ["0", "4", "8"]
    assert [page.response for page in company_notices.pages] == response_store.summaries()


def test_the_number_of_pages_is_capped(bodacc_factory: BodaccFactory) -> None:
    bodacc = bodacc_factory(notices_per_page=4, maximum_pages=2)
    company_notices = bodacc.notices_of("777777777")
    assert len(company_notices.records) == 8
    assert company_notices.total_count == len(EVERY_FAMILY)
    assert not company_notices.is_complete


def test_a_company_without_notices_has_an_empty_complete_list(bodacc: Bodacc) -> None:
    company_notices = bodacc.notices_of("444444444")
    assert company_notices.records == ()
    assert company_notices.total_count == 0
    assert company_notices.is_complete


def test_an_empty_page_stops_the_fetching(bodacc_factory: BodaccFactory) -> None:
    requests: list[httpx.Request] = []

    def answer_with_an_empty_page(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=notice_page([], total_count=5))

    company_notices = bodacc_factory(answer_with_an_empty_page).notices_of("111111111")
    assert len(requests) == 1
    assert not company_notices.is_complete


@pytest.mark.parametrize("siren", ["1234", "111 111 111 00015", ""])
def test_notices_are_only_fetched_for_a_siren(
    bodacc: Bodacc, fake_api: FakeApi, siren: str
) -> None:
    with pytest.raises(InvalidQueryError):
        bodacc.notices_of(siren)
    assert fake_api.requests == []


def test_repeated_notices_are_served_from_the_cache_unless_refreshed(
    bodacc: Bodacc, fake_api: FakeApi
) -> None:
    bodacc.notices_of("222222222")
    bodacc.notices_of("222222222")
    assert len(fake_api.requests) == 1
    bodacc.notices_of("222222222", refresh=True)
    assert len(fake_api.requests) == 2


@pytest.mark.parametrize(
    "body",
    [
        b"<html>maintenance</html>",
        b"{}",
        json.dumps({"results": [], "total_count": "beaucoup"}).encode(),
        json.dumps({"results": ["texte"], "total_count": 1}).encode(),
        json.dumps({"results": None, "total_count": 0}).encode(),
    ],
)
def test_an_unreadable_page_reaches_the_caller_with_a_french_message(
    bodacc_factory: BodaccFactory, body: bytes
) -> None:
    bodacc = bodacc_factory(lambda request: httpx.Response(200, content=body))
    with pytest.raises(CollectionError) as failure:
        bodacc.notices_of("111111111")
    assert str(failure.value) == (
        "La réponse du service BODACC est illisible. Réessayez plus tard."
    )
