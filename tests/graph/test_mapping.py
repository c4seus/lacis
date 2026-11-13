from typing import Any

import pytest

from lacis.collectors.company_register import Company, company_from
from lacis.collectors.fake_plumbers import (
    ACME_PLOMBERIE,
    DUPONT_SERVICES,
    HIDDEN_PLUMBER,
)
from lacis.collectors.fictional_records import (
    FictionalAddress,
    FictionalCompany,
    FictionalEstablishment,
    FictionalNaturalPerson,
)
from lacis.graph.mapping import (
    GraphFragment,
    combined,
    company_fragment,
    merged_entities,
)
from lacis.storage.entities import (
    CollectedEntity,
    EntityKind,
    LinkKind,
    address_identifier,
    company_identifier,
    establishment_identifier,
    foreign_company_identifier,
    person_identifier,
)

ACME = company_identifier("111111111")
ACME_HEAD_OFFICE = establishment_identifier("11111111100015")
SHARED_ADDRESS = address_identifier("12 RUE DES LILAS 31000 TOULOUSE")
JEAN_PIERRE = person_identifier("DUPONT", "Jean Pierre", "1980-05")
HOLDING = company_identifier("333333333")
INVEST = foreign_company_identifier("DUPONT INVEST LTD", "")
ALBI_ADDRESS = FictionalAddress(
    "8", "QUAI", "DE L'ÉCLUSE", "81000", "ALBI", "81004", "Tarn", "76", "Occitanie", "43.9", "2.1"
)


def company_of(fictional: FictionalCompany) -> Company:
    return company_from(fictional.record(list(fictional.establishments)))


def entity_of(fragment: GraphFragment, identifier: str) -> CollectedEntity:
    return next(entity for entity in fragment.entities if entity.identifier == identifier)


def links_of(fragment: GraphFragment) -> set[tuple[str, LinkKind, str, str]]:
    return {(link.source, link.kind, link.target, link.role) for link in fragment.links}


def raw_company(**fields: Any) -> Company:
    return company_from({"siren": "111111111", **fields})


def test_a_company_becomes_entities_and_links() -> None:
    fragment = company_fragment(company_of(ACME_PLOMBERIE))
    assert {entity.identifier for entity in fragment.entities} == {
        ACME,
        ACME_HEAD_OFFICE,
        SHARED_ADDRESS,
        JEAN_PIERRE,
        HOLDING,
        INVEST,
    }
    assert links_of(fragment) == {
        (ACME_HEAD_OFFICE, LinkKind.ESTABLISHMENT_OF, ACME, ""),
        (ACME_HEAD_OFFICE, LinkKind.LOCATED_AT, SHARED_ADDRESS, ""),
        (ACME, LinkKind.REGISTERED_OFFICE, SHARED_ADDRESS, ""),
        (JEAN_PIERRE, LinkKind.MANDATE, ACME, "Président"),
        (HOLDING, LinkKind.MANDATE, ACME, "Directeur général"),
        (INVEST, LinkKind.MANDATE, ACME, "Associé"),
    }


def test_the_company_entity_keeps_every_field_used_by_lacis() -> None:
    entity = entity_of(company_fragment(company_of(DUPONT_SERVICES)), "company:222222222")
    assert entity.kind is EntityKind.COMPANY
    assert entity.label == "DUPONT SERVICES"
    assert entity.attributes == {
        "siren": "222222222",
        "name": "DUPONT SERVICES",
        "name_withheld": False,
        "acronym": None,
        "is_active": False,
        "diffusible": True,
        "legal_form": "5710",
        "activity": "43.22A",
        "creation_date": "2019-04-02",
        "closing_date": "2023-01-15",
        "establishment_count": 1,
        "open_establishment_count": 0,
        "is_under_foreign_law": False,
        "country": None,
        "country_source": None,
        "hidden_director_count": 0,
    }


def test_the_establishment_entity_keeps_every_field_used_by_lacis() -> None:
    entity = entity_of(company_fragment(company_of(ACME_PLOMBERIE)), ACME_HEAD_OFFICE)
    assert entity.kind is EntityKind.ESTABLISHMENT
    assert entity.label == "Siège — TOULOUSE"
    assert entity.attributes == {
        "siret": "11111111100015",
        "is_head_office": True,
        "is_open": True,
        "diffusible": True,
        "trade_name": None,
        "activity": "43.22A",
        "creation_date": "2022-11-10",
        "closing_date": None,
        "postcode": "31000",
        "city": "TOULOUSE",
    }


def test_the_address_entity_keeps_every_field_used_by_lacis() -> None:
    entity = entity_of(company_fragment(company_of(ACME_PLOMBERIE)), SHARED_ADDRESS)
    assert entity.kind is EntityKind.ADDRESS
    assert entity.label == "12 RUE DES LILAS 31000 TOULOUSE"
    assert entity.attributes == {
        "text": "12 RUE DES LILAS 31000 TOULOUSE",
        "postcode": "31000",
        "city": "TOULOUSE",
        "city_code": "31555",
        "country": None,
    }


def test_the_person_entity_keeps_every_field_used_by_lacis() -> None:
    entity = entity_of(company_fragment(company_of(ACME_PLOMBERIE)), JEAN_PIERRE)
    assert entity.kind is EntityKind.PERSON
    assert entity.label == "Jean Pierre DUPONT"
    assert entity.attributes == {
        "last_name": "DUPONT",
        "first_names": "Jean Pierre",
        "birth_month": "1980-05",
        "nationality": "Française",
    }


def test_a_company_director_becomes_a_company_entity_not_a_person() -> None:
    fragment = company_fragment(company_of(ACME_PLOMBERIE))
    holding = entity_of(fragment, HOLDING)
    assert holding.kind is EntityKind.COMPANY
    assert holding.label == "HOLDING DUPONT"
    assert holding.attributes == {"siren": "333333333", "name": "HOLDING DUPONT"}
    assert not any(
        entity.kind is EntityKind.PERSON and "HOLDING" in entity.label
        for entity in fragment.entities
    )


def test_a_company_director_without_siren_becomes_a_foreign_company() -> None:
    invest = entity_of(company_fragment(company_of(ACME_PLOMBERIE)), INVEST)
    assert invest.kind is EntityKind.FOREIGN_COMPANY
    assert invest.label == "DUPONT INVEST LTD"
    assert invest.attributes == {
        "name": "DUPONT INVEST LTD",
        "country": "Royaume-Uni",
        "country_source": "Forme juridique LTD",
    }


def test_two_spellings_of_the_same_address_give_the_same_address_entity() -> None:
    abbreviated = raw_company(
        siege={
            "siret": "11111111100015",
            "est_siege": True,
            "adresse": "12 R. des Lilas 31000 Toulouse",
        }
    )
    first = company_fragment(company_of(DUPONT_SERVICES))
    second = company_fragment(abbreviated)
    first_addresses = {e.identifier for e in first.entities if e.kind is EntityKind.ADDRESS}
    second_addresses = {e.identifier for e in second.entities if e.kind is EntityKind.ADDRESS}
    assert first_addresses == second_addresses == {SHARED_ADDRESS}


def test_companies_at_the_same_address_share_one_address_entity() -> None:
    fragment = combined(
        [
            company_fragment(company_of(ACME_PLOMBERIE)),
            company_fragment(company_of(DUPONT_SERVICES)),
        ]
    )
    assert [e.identifier for e in fragment.entities if e.kind is EntityKind.ADDRESS] == [
        SHARED_ADDRESS
    ]
    assert {link.source for link in fragment.links if link.kind is LinkKind.REGISTERED_OFFICE} == {
        ACME,
        "company:222222222",
    }


def test_a_non_diffusible_company_keeps_no_hidden_field() -> None:
    fragment = company_fragment(company_of(HIDDEN_PLUMBER))
    company = entity_of(fragment, "company:999999999")
    assert company.label == "Entreprise non diffusible (999 999 999)"
    assert company.attributes["name"] is None
    assert company.attributes["name_withheld"] is True
    assert company.attributes["diffusible"] is False
    assert company.attributes["hidden_director_count"] == 1
    assert {entity.kind for entity in fragment.entities} == {
        EntityKind.COMPANY,
        EntityKind.ESTABLISHMENT,
    }
    assert "BLANC" not in repr(fragment).upper()
    head_office = entity_of(fragment, establishment_identifier("99999999900015"))
    assert head_office.attributes["diffusible"] is False
    assert head_office.label == "Siège — TOULOUSE"


def test_a_hidden_director_of_a_diffusible_company_is_counted_not_guessed() -> None:
    fragment = company_fragment(company_of(ACME_PLOMBERIE))
    assert entity_of(fragment, ACME).attributes["hidden_director_count"] == 1
    assert "LEROUX" not in repr(fragment).upper()


def test_other_establishments_are_linked_to_their_company_and_address() -> None:
    company = FictionalCompany(
        siren="111111111",
        name="ACME PLOMBERIE",
        establishments=(
            ACME_PLOMBERIE.establishments[0],
            FictionalEstablishment("00023", ALBI_ADDRESS, "2023-05-02", trade_name="ACME 81"),
        ),
        directors=(),
        creation_date="2022-11-10",
    )
    fragment = company_fragment(company_of(company))
    second = establishment_identifier("11111111100023")
    albi = address_identifier("8 QUAI DE L'ÉCLUSE 81000 ALBI")
    assert entity_of(fragment, second).label == "ACME 81 — ALBI"
    assert entity_of(fragment, second).attributes["is_head_office"] is False
    assert (second, LinkKind.ESTABLISHMENT_OF, ACME, "") in links_of(fragment)
    assert (second, LinkKind.LOCATED_AT, albi, "") in links_of(fragment)
    assert (ACME, LinkKind.REGISTERED_OFFICE, albi, "") not in links_of(fragment)
    assert [entity.identifier for entity in fragment.entities].count(ACME_HEAD_OFFICE) == 1


def test_a_company_without_head_office_has_no_registered_office() -> None:
    fragment = company_fragment(raw_company(nom_complet="SANS SIÈGE"))
    assert [entity.identifier for entity in fragment.entities] == [ACME]
    assert fragment.links == ()


def test_an_establishment_without_address_gives_no_address_entity() -> None:
    fragment = company_fragment(
        raw_company(
            siege={"siret": "11111111100015", "est_siege": True, "libelle_commune": "ALBI"}
        )
    )
    assert {entity.kind for entity in fragment.entities} == {
        EntityKind.COMPANY,
        EntityKind.ESTABLISHMENT,
    }
    assert entity_of(fragment, ACME_HEAD_OFFICE).label == "Siège — ALBI"


@pytest.mark.parametrize(
    ("director", "label", "attributes"),
    [
        (
            {
                "type_dirigeant": "personne physique",
                "nom": "Martin",
                "prenoms": "",
                "qualite": "Gérant",
            },
            "MARTIN",
            {"last_name": "Martin", "first_names": "", "birth_month": None, "nationality": None},
        ),
        (
            {
                "type_dirigeant": "personne physique",
                "nom": "MARTIN",
                "prenoms": "Léa",
                "date_de_naissance": "1984",
                "qualite": "Gérante",
            },
            "Léa MARTIN",
            {
                "last_name": "MARTIN",
                "first_names": "Léa",
                "birth_month": None,
                "nationality": None,
            },
        ),
    ],
)
def test_a_person_without_first_names_or_valid_birth_month_is_still_mapped(
    director: dict[str, str], label: str, attributes: dict[str, object]
) -> None:
    fragment = company_fragment(raw_company(dirigeants=[director]))
    [person] = [entity for entity in fragment.entities if entity.kind is EntityKind.PERSON]
    assert person.label == label
    assert person.attributes == attributes


@pytest.mark.parametrize(
    "director",
    [
        {"type_dirigeant": "personne physique", "prenoms": "Léa", "qualite": "Gérante"},
        {"type_dirigeant": "personne morale", "denomination": "[NON-DIFFUSIBLE]"},
        {"type_dirigeant": "personne morale", "siren": "111111111", "denomination": "ACME"},
    ],
)
def test_a_director_that_cannot_be_identified_or_is_the_company_itself_is_left_out(
    director: dict[str, str],
) -> None:
    fragment = company_fragment(raw_company(dirigeants=[director]))
    assert [entity.identifier for entity in fragment.entities] == [ACME]
    assert fragment.links == ()


def test_a_company_director_without_name_is_labelled_by_its_siren() -> None:
    fragment = company_fragment(
        raw_company(dirigeants=[{"type_dirigeant": "personne morale", "siren": "333333333"}])
    )
    assert entity_of(fragment, HOLDING).label == "333 333 333"


def test_entities_found_twice_keep_their_first_label_and_every_attribute() -> None:
    merged = merged_entities(
        [
            CollectedEntity(HOLDING, "HOLDING DUPONT", {"name": "HOLDING", "acronym": None}),
            CollectedEntity(
                HOLDING, "333 333 333", {"name": None, "acronym": "HD", "active": True}
            ),
        ]
    )
    assert merged == (
        CollectedEntity(
            HOLDING, "HOLDING DUPONT", {"name": "HOLDING", "acronym": "HD", "active": True}
        ),
    )


def test_a_director_found_twice_keeps_one_entity_and_one_link_per_role() -> None:
    jean = FictionalNaturalPerson("DUPONT", "Jean", "1980-05", "Président")
    company = FictionalCompany(
        siren="111111111",
        name="ACME PLOMBERIE",
        establishments=ACME_PLOMBERIE.establishments,
        directors=(jean, jean, FictionalNaturalPerson("DUPONT", "Jean", "1980-05", "Associé")),
        creation_date="2022-11-10",
    )
    fragment = company_fragment(company_of(company))
    assert [e.kind for e in fragment.entities].count(EntityKind.PERSON) == 1
    assert sorted(link.role for link in fragment.links if link.kind is LinkKind.MANDATE) == [
        "Associé",
        "Président",
    ]


def test_a_director_without_role_gets_an_unspecified_role() -> None:
    fragment = company_fragment(
        raw_company(dirigeants=[{"type_dirigeant": "personne morale", "siren": "333333333"}])
    )
    assert [link.role for link in fragment.links] == ["Fonction non précisée"]


def test_the_roles_of_directors_use_the_fixed_french_labels() -> None:
    directors = [
        {"type_dirigeant": "personne morale", "siren": "333333333", "qualite": "Présidente"},
        {"type_dirigeant": "personne physique", "nom": "MARTIN", "qualite": "Co-gérante"},
    ]
    fragment = company_fragment(raw_company(dirigeants=directors))
    assert sorted(link.role for link in fragment.links) == ["Gérant", "Président"]


def test_a_foreign_company_without_known_legal_form_has_no_country() -> None:
    fragment = company_fragment(
        raw_company(dirigeants=[{"type_dirigeant": "personne morale", "denomination": "ATLAS"}])
    )
    atlas = entity_of(fragment, foreign_company_identifier("ATLAS", ""))
    assert atlas.attributes == {"name": "ATLAS", "country": None, "country_source": None}
