import json

from lacis.collectors.fictional_records import (
    FictionalAddress,
    FictionalCompany,
    FictionalEstablishment,
    FictionalLegalPerson,
    FictionalNaturalPerson,
    FictionalNotice,
    searchable,
    spaced_siren,
    without_accents,
)

ADDRESS = FictionalAddress(
    "4",
    "RUE",
    "DES ÉCOLES",
    "81600",
    "GAILLAC",
    "81099",
    "Tarn",
    "76",
    "Occitanie",
    "43.9",
    "1.9",
)
COMPANY = FictionalCompany(
    siren="111111111",
    name="ÉCOLE IMAGINAIRE",
    establishments=(
        FictionalEstablishment("00015", ADDRESS, "2020-01-06"),
        FictionalEstablishment("00023", ADDRESS, "2021-01-04", closing_date="2022-01-03"),
    ),
    directors=(
        FictionalNaturalPerson("MARTIN", "Léa", "1984-09", "Gérante"),
        FictionalLegalPerson("FINANCIÈRE IMAGINAIRE", "Associé", "222222222"),
    ),
    creation_date="2020-01-06",
)


def test_text_is_compared_without_case_or_accents() -> None:
    assert without_accents("Société Élan") == "Societe Elan"
    assert searchable("Société Élan") == "SOCIETE ELAN"


def test_a_siren_is_spaced_in_groups_of_three_digits() -> None:
    assert spaced_siren("111111111") == "111 111 111"


def test_an_address_gives_its_full_text_and_department() -> None:
    assert ADDRESS.full_text == "4 RUE DES ÉCOLES 81600 GAILLAC"
    assert ADDRESS.department == "81"


def test_the_first_establishment_is_the_head_office() -> None:
    record = COMPANY.record(list(COMPANY.establishments))
    assert record["siege"]["siret"] == "11111111100015"
    assert [item["est_siege"] for item in record["matching_etablissements"]] == [True, False]
    assert [item["etat_administratif"] for item in record["matching_etablissements"]] == [
        "A",
        "F",
    ]
    assert record["nombre_etablissements_ouverts"] == 1


def test_a_closed_company_has_its_closing_date_and_state() -> None:
    closed_company = FictionalCompany(
        siren="111111111",
        name="ÉCOLE IMAGINAIRE",
        establishments=COMPANY.establishments,
        directors=(),
        creation_date="2020-01-06",
        closing_date="2022-01-03",
    )
    record = closed_company.record([])
    assert record["etat_administratif"] == "C"
    assert record["date_fermeture"] == "2022-01-03"


def test_the_searchable_text_holds_names_directors_and_the_address() -> None:
    assert COMPANY.searchable_text(COMPANY.head_office) == (
        "ECOLE IMAGINAIRE  MARTIN LEA FINANCIERE IMAGINAIRE  4 RUE DES ECOLES 81600 GAILLAC"
    )


def test_a_notice_publication_follows_its_family() -> None:
    publications = {
        family: FictionalNotice(
            "A202000010001", COMPANY, family, family, "2020-01-20", ""
        ).record()["publicationavis"]
        for family in ("immatriculation", "modification", "dpc")
    }
    assert publications == {"immatriculation": "A", "modification": "B", "dpc": "C"}


def test_notice_details_are_kept_as_json_text() -> None:
    notice = FictionalNotice(
        "B202200030003",
        COMPANY,
        "modification",
        "Modifications diverses",
        "2022-05-10",
        "GREFFE DU TRIBUNAL DE COMMERCE D'ALBI",
        {"modificationsgenerales": {"descriptif": "Nouvelle gérante : MARTIN Léa"}},
    )
    record = notice.record()
    assert record["modificationsgenerales"] == ('{"descriptif": "Nouvelle gérante : MARTIN Léa"}')
    assert json.loads(record["listepersonnes"])["personne"]["denomination"] == "ÉCOLE IMAGINAIRE"
    assert record["parution"] == "20220003"
    assert record["numeroannonce"] == 3


def test_a_company_has_the_vat_number_derived_from_its_siren() -> None:
    assert COMPANY.vat_number == "FR23111111111"
    assert COMPANY.record([])["tva"] == ["FR23111111111"]
