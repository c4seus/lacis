import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from identifier_checks import passes_luhn_check
from lacis.collectors.endpoints import BODACC_RECORDS_URL, COMPANY_SEARCH_URL
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import (
    FAKE_PLUMBERS_INVESTIGATION_NAME,
    FAKE_PLUMBERS_QUESTION,
    FAKE_PLUMBERS_SCENARIO,
)
from lacis.storage.names import validate_investigation_name
from real_api_structure import COMPANY_KEYS, NOTICE_KEYS

ALL_SIRENS = [company.siren for company in FAKE_PLUMBERS_SCENARIO.companies]


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    transport = httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO))
    with httpx.Client(transport=transport) as client:
        yield client


def search(client: httpx.Client, **parameters: str) -> list[dict[str, Any]]:
    response = client.get(COMPANY_SEARCH_URL, params={"per_page": "25", **parameters})
    results: list[dict[str, Any]] = response.json()["results"]
    return results


def names(results: list[dict[str, Any]]) -> list[str]:
    return [result["nom_complet"] for result in results]


def notices_of(client: httpx.Client, siren: str) -> list[dict[str, Any]]:
    response = client.get(
        BODACC_RECORDS_URL,
        params={"where": f'registre="{siren}"', "order_by": "dateparution desc"},
    )
    records: list[dict[str, Any]] = response.json()["results"]
    return records


def identifiers_in(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for item in value.values():
            yield from identifiers_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from identifiers_in(item)
    elif isinstance(value, str):
        digits = value.replace(" ", "")
        if digits.isdigit() and len(digits) in {9, 14}:
            yield digits
        elif value.startswith("{"):
            yield from identifiers_in(json.loads(value))


def test_the_luhn_check_recognises_valid_and_invalid_numbers() -> None:
    assert passes_luhn_check("123456782")
    assert passes_luhn_check("12345678200002")
    assert not passes_luhn_check("123456789")
    assert not passes_luhn_check("12345678200007")


def test_every_siren_and_siret_of_the_scenario_fails_the_luhn_check(
    client: httpx.Client,
) -> None:
    records: list[object] = []
    for siren in ALL_SIRENS:
        records.extend(search(client, q=siren))
        records.extend(notices_of(client, siren))
    identifiers = set(identifiers_in(records))
    assert set(ALL_SIRENS) <= identifiers
    assert "11111111100015" in identifiers
    assert [identifier for identifier in identifiers if passes_luhn_check(identifier)] == []


def test_every_company_answers_with_the_structure_of_the_real_api(client: httpx.Client) -> None:
    for siren in ALL_SIRENS:
        [result] = search(client, q=siren)
        assert set(result) == COMPANY_KEYS
        assert all(set(record) == NOTICE_KEYS for record in notices_of(client, siren))


def test_the_investigation_of_the_scenario_has_a_valid_name() -> None:
    assert validate_investigation_name(FAKE_PLUMBERS_INVESTIGATION_NAME) == "faux-plombiers-31"
    assert FAKE_PLUMBERS_QUESTION.endswith("?")


def test_the_shared_address_gathers_both_plumbers(client: httpx.Client) -> None:
    results = search(client, q="12 rue des lilas toulouse")
    assert names(results) == ["ACME PLOMBERIE", "DUPONT SERVICES"]
    assert [result["etat_administratif"] for result in results] == ["A", "C"]


def test_the_hidden_company_at_the_shared_address_shows_its_city_only(
    client: httpx.Client,
) -> None:
    [hidden] = search(client, q="999999999")
    assert hidden["siege"]["adresse"] == "31000 TOULOUSE"
    assert names(search(client, q="toulouse")) == [
        "ACME PLOMBERIE",
        "DUPONT SERVICES",
        "[NON-DIFFUSIBLE]",
    ]


def test_the_same_street_in_another_city_is_another_address(client: httpx.Client) -> None:
    assert names(search(client, q="rue des lilas")) == [
        "ACME PLOMBERIE",
        "DUPONT SERVICES",
        "LILAS BOULANGERIE",
    ]
    assert names(search(client, q="rue des lilas lyon")) == ["LILAS BOULANGERIE"]


def test_a_search_for_plumbers_in_toulouse_finds_acme(client: httpx.Client) -> None:
    assert names(search(client, q="plomberie toulouse")) == ["ACME PLOMBERIE"]


def test_jean_dupont_and_his_namesakes_direct_several_companies(client: httpx.Client) -> None:
    assert names(search(client, nom_personne="dupont", prenoms_personne="jean")) == [
        "ACME PLOMBERIE",
        "DUPONT SERVICES",
        "HOLDING DUPONT",
        "DUPONT RENOVATION",
    ]
    assert names(search(client, nom_personne="dupont", prenoms_personne="marie")) == [
        "AUTRE SOCIETE"
    ]


def test_acme_is_directed_by_a_person_a_holding_a_foreign_company_and_a_hidden_person(
    client: httpx.Client,
) -> None:
    [acme] = search(client, q="111111111")
    assert [
        (director.get("nom") or director.get("denomination"), director["qualite"])
        for director in acme["dirigeants"]
    ] == [
        ("DUPONT", "Président"),
        ("HOLDING DUPONT", "Directeur général"),
        ("DUPONT INVEST LTD", "Associé"),
        ("[NON-DIFFUSIBLE]", "Associé"),
    ]
    assert acme["dirigeants"][1]["siren"] == "333333333"
    assert acme["dirigeants"][2]["siren"] is None
    assert names(search(client, nom_personne="leroux")) == []


def test_the_notices_tell_the_history_of_each_company(client: httpx.Client) -> None:
    assert [record["familleavis"] for record in notices_of(client, "111111111")] == [
        "modification",
        "dpc",
        "immatriculation",
    ]
    assert [record["familleavis"] for record in notices_of(client, "222222222")] == [
        "radiation",
        "collective",
        "collective",
    ]
    assert [record["tribunal"] for record in notices_of(client, "333333333")] == [
        "GREFFE DU TRIBUNAL DE COMMERCE DE MARSEILLE"
    ]
    assert notices_of(client, "444444444") == []


def test_the_liquidation_of_dupont_services_is_described_by_its_judgments(
    client: httpx.Client,
) -> None:
    judgments = [
        json.loads(record["jugement"])["nature"] for record in notices_of(client, "222222222")[1:]
    ]
    assert judgments == [
        "Jugement de clôture pour insuffisance d'actif",
        "Jugement d'ouverture de liquidation judiciaire",
    ]
