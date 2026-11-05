import pytest

from lacis.collectors.company_register import Company, company_from
from lacis.graph.foreign import (
    ForeignCountry,
    country_name,
    country_of_company,
    country_of_legal_form,
    is_under_foreign_law,
    joined_initials,
)


@pytest.mark.parametrize(
    ("name", "country", "source"),
    [
        ("DUPONT INVEST LTD", "Royaume-Uni", "Forme juridique LTD"),
        ("Dupont Invest Ltd.", "Royaume-Uni", "Forme juridique LTD"),
        ("THAMES TRADING LIMITED", "Royaume-Uni", "Forme juridique LIMITED"),
        ("RHEIN HANDEL GMBH", "Allemagne", "Forme juridique GMBH"),
        ("TULP BEHEER B.V.", "Pays-Bas", "Forme juridique BV"),
        ("SOLE MIO S.P.A.", "Italie", "Forme juridique SPA"),
        ("SOL Y MAR SL", "Espagne", "Forme juridique SL"),
        ("WISLA SP. Z O.O.", "Pologne", "Forme juridique SP ZOO"),
        ("ATLANTIC WIDGETS INC", "États-Unis", "Forme juridique INC"),
    ],
)
def test_a_foreign_legal_form_gives_the_probable_country(
    name: str, country: str, source: str
) -> None:
    assert country_of_legal_form(name) == ForeignCountry(country, source)


@pytest.mark.parametrize(
    "name", ["ATLAS", "HOLDING DUPONT", "DUPONT SARL", "LTD SERVICES", "SRL ROMA", ""]
)
def test_a_name_without_foreign_legal_form_gives_no_country(name: str) -> None:
    assert country_of_legal_form(name) is None


def test_initials_are_read_as_one_word() -> None:
    assert joined_initials(["TULP", "B", "V"]) == ("TULP", "BV")
    assert joined_initials(["A", "B", "TRADING", "S", "A"]) == ("AB", "TRADING", "SA")


def company_with(**fields: object) -> Company:
    return company_from({"siren": "121212121", **fields})


FRENCH_HEAD_OFFICE = {"siret": "12121212100023", "est_siege": True, "libelle_commune": "MARSEILLE"}
LONDON_HEAD_OFFICE = {
    "siret": "12121212100015",
    "est_siege": True,
    "libelle_commune_etranger": "LONDRES",
    "libelle_pays_etranger": "ROYAUME-UNI",
}


def test_a_company_with_its_head_office_abroad_takes_the_country_of_the_address() -> None:
    company = company_with(nom_complet="THAMES TRADING", siege=LONDON_HEAD_OFFICE)
    assert is_under_foreign_law(company)
    assert country_of_company(company) == ForeignCountry("Royaume-Uni", "Adresse du siège")


def test_a_company_under_foreign_law_in_france_takes_the_country_of_its_legal_form() -> None:
    company = company_with(
        nom_complet="THAMES TRADING LIMITED", nature_juridique="3120", siege=FRENCH_HEAD_OFFICE
    )
    assert is_under_foreign_law(company)
    assert country_of_company(company) == ForeignCountry("Royaume-Uni", "Forme juridique LIMITED")


def test_a_company_under_foreign_law_without_known_legal_form_has_no_country() -> None:
    company = company_with(nom_complet="ATLAS", nature_juridique="3120")
    assert is_under_foreign_law(company)
    assert country_of_company(company) is None


@pytest.mark.parametrize(
    "fields",
    [
        {
            "nom_complet": "DUPONT SERVICES",
            "nature_juridique": "5710",
            "siege": FRENCH_HEAD_OFFICE,
        },
        {"nom_complet": "ACME LTD", "nature_juridique": "5499"},
        {"nom_complet": "[NON-DIFFUSIBLE]"},
    ],
)
def test_a_french_company_is_not_under_foreign_law(fields: dict[str, object]) -> None:
    company = company_with(**fields)
    assert not is_under_foreign_law(company)
    assert country_of_company(company) is None


@pytest.mark.parametrize(
    ("api_label", "name"),
    [("ROYAUME-UNI", "Royaume-Uni"), ("ETATS-UNIS", "États-Unis"), ("SÉNÉGAL", "Sénégal")],
)
def test_a_country_label_of_the_api_is_written_in_french(api_label: str, name: str) -> None:
    assert country_name(api_label) == name
