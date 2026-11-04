import pytest

from lacis.storage.entities import (
    CollectedEntity,
    EntityKind,
    InvalidIdentifierError,
    address_identifier,
    company_identifier,
    establishment_identifier,
    foreign_company_identifier,
    kind_of,
    normalise_text,
    person_identifier,
)


def test_texts_are_normalised_without_accents_case_or_punctuation() -> None:
    assert (
        normalise_text("  12, rue des Lilas — 31000 Toulouse ")
        == "12 RUE DES LILAS 31000 TOULOUSE"
    )
    assert normalise_text("Jean-Pierre Dupont") == "JEAN PIERRE DUPONT"
    assert normalise_text("Société Générale") == "SOCIETE GENERALE"


def test_a_company_is_identified_by_its_siren() -> None:
    assert company_identifier("222 222 222") == "company:222222222"


def test_an_establishment_is_identified_by_its_siret() -> None:
    assert establishment_identifier("222 222 222 00015") == "establishment:22222222200015"


@pytest.mark.parametrize("siren", ["22222222", "2222222222", "22222222A", ""])
def test_a_malformed_siren_is_refused(siren: str) -> None:
    with pytest.raises(InvalidIdentifierError, match="9 digits"):
        company_identifier(siren)


@pytest.mark.parametrize("siret", ["2222222220001", "22222222200015X"])
def test_a_malformed_siret_is_refused(siret: str) -> None:
    with pytest.raises(InvalidIdentifierError, match="14 digits"):
        establishment_identifier(siret)


def test_a_person_is_identified_by_name_and_month_of_birth() -> None:
    jean = person_identifier("DUPONT", "Jean", "1980-05")
    assert jean.startswith("person:")
    assert jean == person_identifier("Dupont", "jean", "1980-05")
    assert jean != person_identifier("DUPONT", "Jean Pierre", "1980-05")
    assert jean != person_identifier("DUPONT", "Jean", "1980-06")
    assert jean != person_identifier("DUPONT", "Jean", None)


@pytest.mark.parametrize("month_of_birth", ["1980-5", "1980-13", "05/1980", "1980"])
def test_a_malformed_month_of_birth_is_refused(month_of_birth: str) -> None:
    with pytest.raises(InvalidIdentifierError, match="YYYY-MM"):
        person_identifier("DUPONT", "Jean", month_of_birth)


def test_a_person_needs_a_last_name() -> None:
    with pytest.raises(InvalidIdentifierError, match="last name"):
        person_identifier(" ", "Jean", None)


def test_an_address_is_identified_by_its_normalised_text() -> None:
    address = address_identifier("12 rue des Lilas 31000 Toulouse")
    assert address.startswith("address:")
    assert address == address_identifier("12, RUE DES LILAS, 31000 TOULOUSE")
    assert address != address_identifier("14 rue des Lilas 31000 Toulouse")
    with pytest.raises(InvalidIdentifierError):
        address_identifier(" , ")


def test_a_foreign_company_is_identified_by_its_name_and_country() -> None:
    invest = foreign_company_identifier("DUPONT INVEST LTD", "Royaume-Uni")
    assert invest.startswith("foreign_company:")
    assert invest == foreign_company_identifier("Dupont Invest Ltd.", "ROYAUME UNI")
    assert invest != foreign_company_identifier("DUPONT INVEST LTD", "Irlande")
    with pytest.raises(InvalidIdentifierError):
        foreign_company_identifier("", "Irlande")


@pytest.mark.parametrize(
    ("entity_identifier", "kind"),
    [
        ("company:222222222", EntityKind.COMPANY),
        ("establishment:22222222200015", EntityKind.ESTABLISHMENT),
        (person_identifier("DUPONT", "Jean", "1980-05"), EntityKind.PERSON),
        (address_identifier("12 rue des Lilas"), EntityKind.ADDRESS),
        (
            foreign_company_identifier("DUPONT INVEST LTD", "Royaume-Uni"),
            EntityKind.FOREIGN_COMPANY,
        ),
    ],
)
def test_the_kind_is_read_from_the_identifier(entity_identifier: str, kind: EntityKind) -> None:
    assert kind_of(entity_identifier) is kind
    assert CollectedEntity(entity_identifier, "label").kind is kind
