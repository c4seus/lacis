import json
import sqlite3
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime
from typing import Any

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.bodacc import (
    Bodacc,
    BodaccNotice,
    OfficeTransfer,
    family_of,
    notice_from,
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
from lacis.storage.entities import CollectedEntity
from lacis.storage.graph_store import GraphStore
from lacis.storage.notices import NoticeFamily, NoticeRole, NoticeStore
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


def notices_by_identifier(bodacc: Bodacc, siren: str) -> dict[str, BodaccNotice]:
    return {notice.identifier: notice for notice in bodacc.notices_of(siren).notices}


def test_every_notice_of_the_fake_api_is_placed_in_its_family(bodacc: Bodacc) -> None:
    notices = bodacc.notices_of("777777777").notices
    assert sorted(notice.family for notice in notices) == sorted(
        family for _, family in EVERY_FAMILY.values()
    )
    for notice in notices:
        assert EVERY_FAMILY[family_code_of(notice)] == (notice.family_label, notice.family)


def family_code_of(notice: BodaccNotice) -> str:
    return next(
        fictional.family
        for fictional in EVERY_FAMILY_NOTICES
        if fictional.identifier == notice.identifier
    )


def test_every_notice_of_the_fake_plumbers_is_placed_in_its_family(bodacc: Bodacc) -> None:
    families = {
        siren: [notice.family for notice in bodacc.notices_of(siren).notices]
        for siren in ("111111111", "222222222", "333333333")
    }
    assert families == {
        "111111111": [NoticeFamily.AMENDMENT, NoticeFamily.ACCOUNTS, NoticeFamily.REGISTRATION],
        "222222222": [NoticeFamily.REMOVAL, NoticeFamily.INSOLVENCY, NoticeFamily.INSOLVENCY],
        "333333333": [NoticeFamily.AMENDMENT],
    }


@pytest.mark.parametrize(
    ("code", "label", "family"),
    [
        ("", "Procédures collectives", NoticeFamily.INSOLVENCY),
        (
            "inconnue",
            "Procédure de rétablissement professionnel",
            NoticeFamily.PROFESSIONAL_RECOVERY,
        ),
        ("", "Avis de dépôt des comptes", NoticeFamily.ACCOUNTS),
        ("", "Cession de fonds", NoticeFamily.SALE),
        (" DPC ", "", NoticeFamily.ACCOUNTS),
        ("", "", NoticeFamily.MISCELLANEOUS),
        ("nouvelle", "Famille inconnue", NoticeFamily.MISCELLANEOUS),
    ],
)
def test_an_unknown_code_is_classified_by_its_label(
    code: str, label: str, family: NoticeFamily
) -> None:
    assert family_of(code, label) is family


def test_a_notice_gives_its_court_publication_date_and_link(bodacc: Bodacc) -> None:
    notice = notices_by_identifier(bodacc, "111111111")["C202400020002"]
    assert notice.court == COURT
    assert notice.published_on == date(2024, 7, 12)
    assert notice.url.endswith("q.id=id:C202400020002")
    assert notice.response.source is ResponseSource.BODACC


def test_an_insolvency_notice_gives_its_judgment_and_its_date(bodacc: Bodacc) -> None:
    notices = notices_by_identifier(bodacc, "222222222")
    closing = notices["A202200030002"]
    assert closing.judgment == "Jugement de clôture pour insuffisance d'actif"
    assert closing.judgment_date == date(2022, 11, 28)
    assert closing.summary == (
        "Jugement de clôture pour insuffisance d'actif. "
        "Jugement prononçant la clôture de la procédure."
    )
    opening = notices["A202200030003"]
    assert opening.judgment == "Jugement d'ouverture de liquidation judiciaire"
    assert opening.summary == "Jugement d'ouverture de liquidation judiciaire"


def test_a_notice_outside_proceedings_has_no_judgment(bodacc: Bodacc) -> None:
    removal = notices_by_identifier(bodacc, "222222222")["B202300030001"]
    assert removal.judgment == ""
    assert removal.judgment_date is None


@pytest.mark.parametrize(
    ("identifier", "summary"),
    [
        ("B202500010001", "Modification survenue sur l'administration. "),
        ("C202400020002", "Comptes annuels et rapports (clôture au 2023-12-31)"),
        ("A202200010003", "Société par actions simplifiée. Plomberie, chauffage."),
    ],
)
def test_a_notice_is_summarised_from_its_family_details(
    bodacc: Bodacc, identifier: str, summary: str
) -> None:
    assert notices_by_identifier(bodacc, "111111111")[identifier].summary.startswith(summary)


def test_a_removal_is_summarised_from_its_details(bodacc: Bodacc) -> None:
    removal = notices_by_identifier(bodacc, "222222222")["B202300030001"]
    assert removal.summary == "Radiation du registre du commerce et des sociétés"


def raw_notice(family: str, **details: object) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "A202500990001",
        "familleavis": family,
        "familleavis_lib": "Famille",
        "typeavis_lib": "Avis initial",
        "dateparution": "2025-03-04",
        "tribunal": COURT,
        "registre": ["111111111", "111 111 111"],
    }
    record.update(
        {
            name: json.dumps(value) if isinstance(value, dict) else value
            for name, value in details.items()
        }
    )
    return record


@pytest.mark.parametrize(
    ("record", "summary"),
    [
        (raw_notice("dpc", depot={"typeDepot": "Comptes annuels"}), "Comptes annuels"),
        (raw_notice("dpc", depot={"dateCloture": "2024-12-31"}), "Clôture au 2024-12-31"),
        (raw_notice("dpc"), "Avis initial"),
        (raw_notice("radiation"), "Avis initial"),
        (raw_notice("radiation", radiationaurcs={"motifs": ["", " "]}), "Avis initial"),
        (
            raw_notice("radiation", radiationaurcs={"motif": "Radiation d'office"}),
            "Radiation d'office",
        ),
        (
            raw_notice("radiation", radiationaurcs={"motifs": ["", 3, "Radiation d'office"]}),
            "Radiation d'office",
        ),
        (
            raw_notice("collective", jugement={"complementJugement": "Plan arrêté."}),
            "Plan arrêté.",
        ),
        (raw_notice("vente", acte={"categorieVente": "Vente du fonds"}), "Vente du fonds"),
        (raw_notice("divers", divers={"texte": "Rectificatif."}), "Rectificatif."),
        (raw_notice("divers", typeavis_lib=None), "Famille"),
    ],
)
def test_a_notice_without_its_usual_details_is_still_summarised(
    record: dict[str, Any], summary: str
) -> None:
    assert notice_from(record, RESPONSE).summary == summary


def test_a_long_summary_is_shortened_on_one_line() -> None:
    record = raw_notice("modification", modificationsgenerales={"descriptif": "mot\n " * 200})
    summary = notice_from(record, RESPONSE).summary
    assert len(summary) == 400
    assert summary.endswith("…")
    assert "\n" not in summary


def test_a_notice_without_link_gets_the_link_of_its_bodacc_page() -> None:
    assert notice_from(raw_notice("divers"), RESPONSE).url == (
        "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:A202500990001"
    )


def test_the_companies_of_a_notice_are_given_their_role() -> None:
    record = raw_notice(
        "immatriculation",
        registre=["999999999", "999 999 999", "555555555", "555 555 555", "888888888"],
        listepersonnes={
            "personne": {"numeroImmatriculation": {"numeroIdentification": "999 999 999"}}
        },
        listeprecedentexploitant={
            "personne": {"numeroImmatriculation": {"numeroIdentification": "555 555 555"}}
        },
        listeprecedentproprietaire={
            "personne": [{"numeroImmatriculation": {"numeroIdentification": "RCS 666666666"}}]
        },
    )
    assert notice_from(record, RESPONSE).company_roles == {
        "999999999": NoticeRole.SUBJECT,
        "555555555": NoticeRole.PREVIOUS_OPERATOR,
        "666666666": NoticeRole.PREVIOUS_OWNER,
        "888888888": NoticeRole.MENTIONED,
    }


def test_a_notice_without_persons_concerns_its_registered_companies() -> None:
    record = raw_notice("divers", registre="111 111 111")
    assert notice_from(record, RESPONSE).company_roles == {"111111111": NoticeRole.SUBJECT}


def test_a_notice_is_saved_in_the_investigation_with_its_companies(
    bodacc: Bodacc, investigation_connection: sqlite3.Connection
) -> None:
    notice_store = NoticeStore(investigation_connection)
    company_notices = bodacc.notices_of("111111111")
    GraphStore(investigation_connection).save_entity(
        CollectedEntity("company:111111111", "ACME PLOMBERIE"), company_notices.pages[0].response
    )
    for notice in company_notices.notices:
        notice_store.save_notice(notice.collected_notice(), notice.response)
    notices = notice_store.notices_of_company("company:111111111")
    assert {family: len(items) for family, items in notices.items()} == {
        NoticeFamily.AMENDMENT: 1,
        NoticeFamily.ACCOUNTS: 1,
        NoticeFamily.REGISTRATION: 1,
    }
    assert {item.role for items in notices.values() for item in items} == {NoticeRole.SUBJECT}


@pytest.mark.parametrize(
    "record",
    [
        {"familleavis": "divers", "dateparution": "2025-01-01"},
        {"id": "A1", "familleavis": "divers", "dateparution": "hier"},
        {"id": "A1", "familleavis": "divers"},
    ],
)
def test_an_unreadable_notice_reaches_the_caller_with_a_french_message(
    bodacc_factory: BodaccFactory, record: dict[str, Any]
) -> None:
    bodacc = bodacc_factory(lambda request: httpx.Response(200, content=notice_page([record])))
    company_notices = bodacc.notices_of("111111111")
    with pytest.raises(CollectionError) as failure:
        _ = company_notices.notices
    assert str(failure.value) == (
        "La réponse du service BODACC est illisible. Réessayez plus tard."
    )


def test_a_transfer_of_the_registered_office_abroad_gives_its_country_and_date(
    bodacc: Bodacc,
) -> None:
    [notice] = bodacc.notices_of("333333333").notices
    assert notice.office_transfer == OfficeTransfer(
        "Belgique", date(2025, 9, 1), effective_date_stated=True
    )


def test_notices_without_transfer_abroad_have_none(bodacc: Bodacc) -> None:
    for siren in ("111111111", "222222222", "777777777"):
        assert all(notice.office_transfer is None for notice in bodacc.notices_of(siren).notices)


def transfer_of(field_name: str = "modificationsgenerales", **detail: object) -> object:
    return notice_from(
        raw_notice("modification", **{field_name: detail}), RESPONSE
    ).office_transfer


@pytest.mark.parametrize(
    ("detail", "transfer"),
    [
        (
            {"descriptif": "Transfert du siège social à Genève (Suisse) le 15/03/2025."},
            OfficeTransfer("Suisse", date(2025, 3, 15), effective_date_stated=True),
        ),
        (
            {"descriptif": "Transfert du siège social au Royaume-Uni.", "dateEffet": "2025-02-01"},
            OfficeTransfer("Royaume-Uni", date(2025, 2, 1), effective_date_stated=True),
        ),
        (
            {"descriptif": "Transfert du siège social à Lisbonne (PORTUGAL) au 2025-01-20."},
            OfficeTransfer("Portugal", date(2025, 1, 20), effective_date_stated=True),
        ),
        (
            {"descriptif": "Transfert du siège social hors de France."},
            OfficeTransfer(None, date(2025, 3, 4), effective_date_stated=False),
        ),
        (
            {"descriptif": "Transfert de siège à l'étranger le 31 février 2025."},
            OfficeTransfer(None, date(2025, 3, 4), effective_date_stated=False),
        ),
        (
            {"descriptif": "Transfert du siège social à Tunis le 3 mai 2025.", "pays": "Tunisie"},
            OfficeTransfer("Tunisie", date(2025, 5, 3), effective_date_stated=True),
        ),
        (
            {"descriptif": "Transfert du siège social.", "adresse": {"pays": "SÉNÉGAL"}},
            OfficeTransfer("SÉNÉGAL", date(2025, 3, 4), effective_date_stated=False),
        ),
        (
            {"descriptif": "Transfert du siège le 2 brumaire 2025 hors de France."},
            OfficeTransfer(None, date(2025, 3, 4), effective_date_stated=False),
        ),
    ],
)
def test_a_transfer_abroad_is_recognised_in_its_forms(
    detail: dict[str, str], transfer: OfficeTransfer
) -> None:
    assert transfer_of(**detail) == transfer


def test_a_removal_after_a_transfer_abroad_is_recognised() -> None:
    transfer = transfer_of(
        "radiationaurcs",
        radiationPM="Radiation suite au transfert du siège en Allemagne.",
        dateCessationActivitePM="2025-06-30",
    )
    assert transfer == OfficeTransfer("Allemagne", date(2025, 6, 30), effective_date_stated=True)


@pytest.mark.parametrize(
    "detail",
    [
        {"descriptif": "Transfert du siège social au 5 avenue du Port 13002 Marseille."},
        {"descriptif": "Transfert du siège social.", "pays": "France"},
        {"descriptif": "Nouveau gérant domicilié en Belgique."},
        {"descriptif": "Transfert d'un établissement en Belgique."},
    ],
)
def test_a_domestic_transfer_or_another_change_is_not_a_transfer_abroad(
    detail: dict[str, str],
) -> None:
    assert transfer_of(**detail) is None


def test_the_country_of_the_persons_counts_for_a_transfer() -> None:
    record = raw_notice(
        "modification",
        modificationsgenerales={"descriptif": "Transfert du siège social."},
        listepersonnes={"personne": {"adresseSiegeSocial": {"pays": "Belgique"}}},
    )
    transfer = notice_from(record, RESPONSE).office_transfer
    assert transfer == OfficeTransfer("Belgique", date(2025, 3, 4), effective_date_stated=False)


def test_a_detail_that_is_not_valid_json_is_read_as_plain_text() -> None:
    record = raw_notice("divers", divers="{texte tronqué")
    assert notice_from(record, RESPONSE).summary == "Avis initial"


def test_a_transfer_described_in_a_list_of_texts_is_recognised() -> None:
    transfer = transfer_of(descriptif=["", "Transfert du siège social en Italie."])
    assert transfer == OfficeTransfer("Italie", date(2025, 3, 4), effective_date_stated=False)


def test_numbers_that_are_not_sirens_give_no_company() -> None:
    record = raw_notice(
        "immatriculation",
        registre=["111111111", "inconnu"],
        listepersonnes={
            "personne": [
                {"numeroImmatriculation": {"numeroIdentification": "111 111 111"}},
                {"numeroImmatriculation": {"numeroIdentification": "en cours"}},
            ]
        },
    )
    assert notice_from(record, RESPONSE).company_roles == {"111111111": NoticeRole.SUBJECT}
