import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from lacis.collectors.endpoints import BODACC_RECORDS_URL, COMPANY_SEARCH_URL
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fictional_records import (
    NON_DIFFUSIBLE,
    FictionalAddress,
    FictionalCompany,
    FictionalEstablishment,
    FictionalLegalPerson,
    FictionalNaturalPerson,
    FictionalNotice,
    FictionalScenario,
)
from lacis.collectors.http_client import CollectorHttpClient
from lacis.storage.collection_log import CollectionLog
from lacis.storage.responses import ResponseSource, ResponseStore
from real_api_structure import (
    COMPANY_KEYS,
    COMPLEMENT_KEYS,
    HEAD_OFFICE_KEYS,
    LEGAL_PERSON_KEYS,
    NATURAL_PERSON_KEYS,
    NOTICE_KEYS,
)

ROSES_ADDRESS = FictionalAddress(
    "4",
    "RUE",
    "DES ROSES",
    "81600",
    "GAILLAC",
    "81099",
    "Tarn",
    "76",
    "Occitanie",
    "43.9",
    "1.9",
)
QUAY_ADDRESS = FictionalAddress(
    "8",
    "QUAI",
    "DE L'ÉCLUSE",
    "81000",
    "ALBI",
    "81004",
    "Tarn",
    "76",
    "Occitanie",
    "43.93",
    "2.15",
)
CHAUFFAGE = FictionalCompany(
    siren="111111111",
    name="CHAUFFAGE IMAGINAIRE",
    establishments=(
        FictionalEstablishment("00015", ROSES_ADDRESS, "2020-01-06"),
        FictionalEstablishment("00023", QUAY_ADDRESS, "2022-05-02", trade_name="CHAUFFAGE 81"),
    ),
    directors=(
        FictionalNaturalPerson("MARTIN", "Léa Anne", "1984-09", "Gérante"),
        FictionalLegalPerson("FINANCIÈRE IMAGINAIRE", "Associé", "222222222"),
    ),
    creation_date="2020-01-06",
    acronym="CI",
)
HIDDEN = FictionalCompany(
    siren="999999999",
    name="MARTIN Paul",
    establishments=(FictionalEstablishment("00015", ROSES_ADDRESS, "2021-02-01"),),
    directors=(FictionalNaturalPerson("MARTIN", "Paul", "1990-01", "Entrepreneur"),),
    creation_date="2021-02-01",
    closing_date="2024-12-31",
    legal_form="1000",
    diffusible=False,
)
NOTICES = (
    FictionalNotice(
        "A202000010001",
        CHAUFFAGE,
        "immatriculation",
        "Immatriculations",
        "2020-01-20",
        "GREFFE DU TRIBUNAL DE COMMERCE D'ALBI",
        {"acte": {"descriptif": "Chauffage, plomberie."}},
    ),
    FictionalNotice(
        "C202400020002",
        CHAUFFAGE,
        "dpc",
        "Dépôts des comptes",
        "2024-07-01",
        "GREFFE DU TRIBUNAL DE COMMERCE D'ALBI",
        {"depot": {"typeDepot": "Comptes annuels et rapports", "dateCloture": "2023-12-31"}},
    ),
    FictionalNotice(
        "B202200030003",
        CHAUFFAGE,
        "modification",
        "Modifications diverses",
        "2022-05-10",
        "GREFFE DU TRIBUNAL DE COMMERCE D'ALBI",
    ),
    FictionalNotice(
        "B202500040004",
        HIDDEN,
        "radiation",
        "Radiations",
        "2025-01-15",
        "GREFFE DU TRIBUNAL DE COMMERCE D'ALBI",
    ),
)
SCENARIO = FictionalScenario((CHAUFFAGE, HIDDEN), NOTICES)


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(SCENARIO)


@pytest.fixture
def client(fake_api: FakeApi) -> Iterator[httpx.Client]:
    with httpx.Client(transport=httpx.MockTransport(fake_api)) as client:
        yield client


def search(client: httpx.Client, **parameters: str) -> dict[str, Any]:
    response = client.get(COMPANY_SEARCH_URL, params=parameters)
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    return payload


def notices(client: httpx.Client, **parameters: str) -> dict[str, Any]:
    response = client.get(BODACC_RECORDS_URL, params=parameters)
    assert response.status_code == 200
    payload: dict[str, Any] = response.json()
    return payload


def sirens(payload: dict[str, Any]) -> list[str]:
    return [result["siren"] for result in payload["results"]]


def sirets(result: dict[str, Any]) -> list[str]:
    return [establishment["siret"] for establishment in result["matching_etablissements"]]


def test_a_search_answers_with_the_structure_of_the_real_api(client: httpx.Client) -> None:
    payload = search(client, q="chauffage imaginaire")
    assert set(payload) == {"results", "total_results", "page", "per_page", "total_pages"}
    [result] = payload["results"]
    assert set(result) == COMPANY_KEYS
    assert set(result["siege"]) == HEAD_OFFICE_KEYS
    assert set(result["complements"]) == COMPLEMENT_KEYS
    assert [set(director) for director in result["dirigeants"]] == [
        NATURAL_PERSON_KEYS,
        LEGAL_PERSON_KEYS,
    ]
    assert result["matching_etablissements"]
    assert all(set(item) == HEAD_OFFICE_KEYS for item in result["matching_etablissements"])


def test_a_company_carries_its_head_office_directors_and_counts(client: httpx.Client) -> None:
    [result] = search(client, q="111111111")["results"]
    assert result["nom_complet"] == "CHAUFFAGE IMAGINAIRE"
    assert result["sigle"] == "CI"
    assert result["etat_administratif"] == "A"
    assert result["statut_diffusion"] == "O"
    assert result["nombre_etablissements"] == 2
    assert result["nombre_etablissements_ouverts"] == 2
    assert result["siege"]["siret"] == "11111111100015"
    assert result["siege"]["est_siege"] is True
    assert result["siege"]["adresse"] == "4 RUE DES ROSES 81600 GAILLAC"
    assert result["siege"]["departement"] == "81"
    assert result["dirigeants"][0] == {
        "nom": "MARTIN",
        "prenoms": "Léa Anne",
        "annee_de_naissance": "1984",
        "date_de_naissance": "1984-09",
        "qualite": "Gérante",
        "nationalite": "Française",
        "type_dirigeant": "personne physique",
    }
    assert result["dirigeants"][1] == {
        "siren": "222222222",
        "denomination": "FINANCIÈRE IMAGINAIRE",
        "qualite": "Associé",
        "type_dirigeant": "personne morale",
    }


def test_a_search_by_siren_typed_with_spaces_gives_every_establishment(
    client: httpx.Client,
) -> None:
    [result] = search(client, q="111 111 111")["results"]
    assert sirets(result) == ["11111111100015", "11111111100023"]
    assert [item["est_siege"] for item in result["matching_etablissements"]] == [True, False]
    assert result["matching_etablissements"][1]["nom_commercial"] == "CHAUFFAGE 81"


def test_a_search_by_siret_gives_the_matching_establishment(client: httpx.Client) -> None:
    [result] = search(client, q="111 111 111 00023")["results"]
    assert sirets(result) == ["11111111100023"]


def test_an_address_search_ignores_case_and_accents(client: httpx.Client) -> None:
    [result] = search(client, q="quai de l'ecluse albi")["results"]
    assert sirets(result) == ["11111111100023"]


def test_a_search_by_director_or_acronym_finds_the_company(client: httpx.Client) -> None:
    assert sirens(search(client, q="lea martin")) == ["111111111"]
    assert sirens(search(client, q="financiere imaginaire")) == ["111111111"]
    assert sirens(search(client, q="ci gaillac")) == ["111111111"]


def test_a_search_by_person_name_finds_the_companies_they_direct(client: httpx.Client) -> None:
    assert sirens(search(client, nom_personne="martin")) == ["111111111"]
    assert sirens(search(client, nom_personne="Martin", prenoms_personne="lea")) == ["111111111"]
    assert sirens(search(client, nom_personne="martin", prenoms_personne="paul")) == []
    assert sirens(search(client, q="rue des roses", nom_personne="martin")) == ["111111111"]


def test_an_unknown_company_gives_no_result(client: httpx.Client) -> None:
    assert search(client, q="123456780") == {
        "results": [],
        "total_results": 0,
        "page": 1,
        "per_page": 10,
        "total_pages": 1,
    }
    assert search(client, q="00000000000000")["results"] == []
    assert search(client, q="boulangerie")["results"] == []


def test_a_non_diffusible_company_is_found_by_siren_only_with_hidden_fields(
    client: httpx.Client,
) -> None:
    assert sirens(search(client, q="martin paul")) == []
    assert sirens(search(client, q="gaillac")) == ["111111111", "999999999"]
    [result] = search(client, q="999999999")["results"]
    assert result["nom_complet"] == NON_DIFFUSIBLE
    assert result["statut_diffusion"] == "P"
    assert result["etat_administratif"] == "C"
    assert result["complements"]["est_entrepreneur_individuel"] is True
    assert result["siege"]["adresse"] == "81600 GAILLAC"
    assert result["siege"]["libelle_voie"] == NON_DIFFUSIBLE
    assert result["siege"]["statut_diffusion_etablissement"] == "P"
    assert result["dirigeants"][0]["nom"] == NON_DIFFUSIBLE
    assert result["dirigeants"][0]["date_de_naissance"] is None


def test_search_results_are_paginated(client: httpx.Client) -> None:
    second_page = search(client, q="gaillac", page="2", per_page="1")
    assert sirens(second_page) == ["999999999"]
    assert second_page["total_results"] == 2
    assert second_page["page"] == 2
    assert second_page["per_page"] == 1
    assert second_page["total_pages"] == 2
    assert sirens(search(client, q="gaillac", page="3", per_page="1")) == []


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"q": "gaillac", "per_page": "26"}, "Paramètre per_page invalide : 26"),
        ({"q": "gaillac", "page": "0"}, "Paramètre page invalide : 0"),
        ({"q": "gaillac", "page": "deux"}, "Paramètre page invalide : deux"),
        ({"q": " "}, "Veuillez indiquer au moins un terme de recherche."),
        ({}, "Veuillez indiquer au moins un terme de recherche."),
    ],
)
def test_an_invalid_search_is_refused_like_the_real_api(
    client: httpx.Client, parameters: dict[str, str], message: str
) -> None:
    response = client.get(COMPANY_SEARCH_URL, params=parameters)
    assert response.status_code == 400
    assert response.json() == {"erreur": message}


def test_notices_answer_with_the_structure_of_the_real_api(client: httpx.Client) -> None:
    payload = notices(client, where='registre="111111111"')
    assert set(payload) == {"total_count", "results"}
    assert payload["total_count"] == 3
    assert all(set(record) == NOTICE_KEYS for record in payload["results"])


def test_a_notice_describes_the_company_and_its_publication(client: httpx.Client) -> None:
    [record] = notices(client, where='registre="111111111"', limit="1")["results"]
    assert record["id"] == "A202000010001"
    assert record["publicationavis"] == "A"
    assert record["dateparution"] == "2020-01-20"
    assert record["numeroannonce"] == 1
    assert record["familleavis"] == "immatriculation"
    assert record["familleavis_lib"] == "Immatriculations"
    assert record["commercant"] == "CHAUFFAGE IMAGINAIRE"
    assert record["registre"] == ["111111111", "111 111 111"]
    assert record["numerodepartement"] == "81"
    assert record["departement_nom_officiel"] == "Tarn"
    assert record["region_code"] == 76
    assert record["region_nom_officiel"] == "Occitanie"
    assert record["url_complete"].endswith("q.id=id:A202000010001")


def test_notice_details_are_json_text_like_in_the_real_api(client: httpx.Client) -> None:
    [record] = notices(client, where='registre="111111111"', limit="1")["results"]
    persons = json.loads(record["listepersonnes"])
    assert persons["personne"]["denomination"] == "CHAUFFAGE IMAGINAIRE"
    assert persons["personne"]["numeroImmatriculation"]["numeroIdentification"] == ("111 111 111")
    assert json.loads(record["acte"]) == {"descriptif": "Chauffage, plomberie."}
    assert record["jugement"] is None


def test_notices_are_sorted_and_paginated(client: httpx.Client) -> None:
    newest_first = notices(
        client, where='registre="111 111 111"', order_by="dateparution desc", limit="2"
    )
    assert [record["dateparution"] for record in newest_first["results"]] == [
        "2024-07-01",
        "2022-05-10",
    ]
    assert newest_first["total_count"] == 3
    oldest_last = notices(
        client, where='registre="111111111"', order_by="dateparution", offset="2"
    )
    assert [record["dateparution"] for record in oldest_last["results"]] == ["2024-07-01"]


def test_notices_without_filter_are_all_listed(client: httpx.Client) -> None:
    assert notices(client)["total_count"] == len(NOTICES)
    assert notices(client, where='registre="123456780"') == {"total_count": 0, "results": []}


@pytest.mark.parametrize(
    ("parameters", "message"),
    [
        ({"limit": "101"}, "Paramètre limit invalide : 101"),
        ({"limit": "0"}, "Paramètre limit invalide : 0"),
        ({"offset": "-1"}, "Paramètre offset invalide : -1"),
        ({"where": "commercant like 'A%'"}, "Filtre non pris en charge : commercant like 'A%'"),
        ({"order_by": "commercant"}, "Tri non pris en charge : commercant"),
    ],
)
def test_an_invalid_notice_query_is_refused_like_the_real_api(
    client: httpx.Client, parameters: dict[str, str], message: str
) -> None:
    response = client.get(BODACC_RECORDS_URL, params=parameters)
    assert response.status_code == 400
    assert response.json() == {"error_code": "InvalidRESTParameterError", "message": message}


def test_an_unknown_endpoint_is_not_found(client: httpx.Client) -> None:
    response = client.get("https://recherche-entreprises.api.gouv.fr/near_point")
    assert response.status_code == 404
    assert response.json() == {"erreur": "Ressource inconnue : /near_point"}
    assert client.post(COMPANY_SEARCH_URL).status_code == 404


def test_the_fake_api_remembers_the_requests_it_received(
    client: httpx.Client, fake_api: FakeApi
) -> None:
    search(client, q="gaillac")
    notices(client)
    assert [str(request.url.copy_with(query=None)) for request in fake_api.requests] == [
        COMPANY_SEARCH_URL,
        BODACC_RECORDS_URL,
    ]


def test_the_collector_client_reaches_the_fake_api_without_network(
    fake_api: FakeApi, response_store: ResponseStore, collection_log: CollectionLog
) -> None:
    client = CollectorHttpClient(response_store, collection_log, httpx.MockTransport(fake_api))
    try:
        stored = client.get(ResponseSource.COMPANY_REGISTER, COMPANY_SEARCH_URL, {"q": "ci"})
    finally:
        client.close()
    assert sirens(json.loads(stored.body)) == ["111111111"]
    assert len(fake_api.requests) == 1
