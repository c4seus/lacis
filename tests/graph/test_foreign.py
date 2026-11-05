import pytest

from lacis.graph.foreign import ForeignCountry, country_of_legal_form, joined_initials


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
