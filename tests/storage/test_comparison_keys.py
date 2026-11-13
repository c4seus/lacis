import pytest

from lacis.storage.comparison_keys import (
    address_key,
    company_name_key,
    normalise_text,
    person_name_key,
)


def test_texts_are_normalised_without_accents_case_or_punctuation() -> None:
    assert (
        normalise_text("  12, rue des Lilas — 31000 Toulouse ")
        == "12 RUE DES LILAS 31000 TOULOUSE"
    )
    assert normalise_text("Jean-Pierre Dupont") == "JEAN PIERRE DUPONT"
    assert normalise_text("Société Générale") == "SOCIETE GENERALE"


@pytest.mark.parametrize(
    "spelling",
    [
        "12 RUE DES LILAS 31000 TOULOUSE",
        "12, rue des Lilas, 31000 Toulouse",
        "12 R. des Lilas 31000 TOULOUSE",
        "12 r des lilas  31000 toulouse France",
        "12 RUE DES LILAS 31000 TOULOUSE CEDEX 9",
        "12 RUE DES LILAS BP 1234 31000 TOULOUSE",
    ],
)
def test_two_spellings_of_the_same_address_give_the_same_key(spelling: str) -> None:
    assert address_key(spelling) == "12 RUE DES LILAS 31000 TOULOUSE"


@pytest.mark.parametrize(
    ("first_spelling", "second_spelling"),
    [
        ("5 AV DU PORT 13002 MARSEILLE", "5 avenue du Port 13002 Marseille"),
        ("3 BD DE LA PLAGE 06000 NICE", "3 boulevard de la Plage 06000 Nice"),
        ("1 PL ST ETIENNE 31000 TOULOUSE", "1 place Saint-Étienne 31000 Toulouse"),
        ("8 IMP DES SAULES 34000 MONTPELLIER", "8 impasse des Saules 34000 Montpellier"),
        ("2 CHE DU MOULIN 81600 GAILLAC", "2 chemin du Moulin 81600 Gaillac"),
        ("7 RTE DE LYON 38000 GRENOBLE", "7 route de Lyon 38000 Grenoble"),
        ("4 QU DE LA FOSSE 44000 NANTES", "4 quai de la Fosse 44000 Nantes"),
        ("9 CRS MIRABEAU 13100 AIX", "9 cours Mirabeau 13100 Aix"),
        ("6 ALL DES PINS 33000 BORDEAUX", "6 allée des Pins 33000 Bordeaux"),
        ("12B RUE DES LILAS 31000 TOULOUSE", "12 bis rue des Lilas 31000 Toulouse"),
        ("12 B RUE DES LILAS 31000 TOULOUSE", "12 BIS RUE DES LILAS 31000 TOULOUSE"),
        ("12T RUE DES LILAS 31000 TOULOUSE", "12 ter rue des Lilas 31000 Toulouse"),
    ],
)
def test_street_abbreviations_and_repetitions_are_spelled_out(
    first_spelling: str, second_spelling: str
) -> None:
    assert address_key(first_spelling) == address_key(second_spelling)


@pytest.mark.parametrize(
    ("first_address", "second_address"),
    [
        ("12 RUE DES LILAS 31000 TOULOUSE", "14 RUE DES LILAS 31000 TOULOUSE"),
        ("12 RUE DES LILAS 31000 TOULOUSE", "12 RUE DES LILAS 69001 LYON"),
        ("12 RUE DES LILAS 31000 TOULOUSE", "12 BIS RUE DES LILAS 31000 TOULOUSE"),
        ("12 RUE DES LILAS 31000 TOULOUSE", "12 AVENUE DES LILAS 31000 TOULOUSE"),
    ],
)
def test_different_addresses_keep_different_keys(first_address: str, second_address: str) -> None:
    assert address_key(first_address) != address_key(second_address)


def test_an_address_made_of_its_country_only_keeps_it() -> None:
    assert address_key("France") == "FRANCE"
    assert address_key(" , ") == ""


def test_a_b_that_does_not_follow_a_number_is_kept() -> None:
    assert address_key("RESIDENCE B 31000 TOULOUSE") == "RESIDENCE B 31000 TOULOUSE"


@pytest.mark.parametrize(
    "spelling",
    [
        "DUPONT INVEST LTD",
        "Dupont Invest Limited",
        "DUPONT INVEST",
        "dupont-invest ltd.",
    ],
)
def test_legal_forms_do_not_change_the_key_of_a_company_name(spelling: str) -> None:
    assert company_name_key(spelling) == "DUPONT INVEST"


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("DUPONT SERVICES SARL", "DUPONT SERVICES"),
        ("Société par actions simplifiée ACME PLOMBERIE", "ACME PLOMBERIE"),
        ("ACME PLOMBERIE, société à responsabilité limitée", "ACME PLOMBERIE"),
        ("Dupont & Fils", "DUPONT ET FILS"),
        ("SAS", "SAS"),
        ("SCI", "SCI"),
    ],
)
def test_a_company_name_key_keeps_the_meaningful_words(name: str, key: str) -> None:
    assert company_name_key(name) == key


def test_a_person_name_key_ignores_accents_case_and_hyphens() -> None:
    assert person_name_key("Jean-Pierre") == person_name_key("JEAN PIERRE")
    assert person_name_key("Hélène") == "HELENE"
