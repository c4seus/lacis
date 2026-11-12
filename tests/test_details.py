import sqlite3
from datetime import date

import pytest

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import COLLECTED_AT, InvestigationBuilder
from lacis.details import (
    Badge,
    BadgeTone,
    EntityDetails,
    entity_details,
    written_day,
    written_month,
)
from lacis.storage.entities import CollectedEntity
from lacis.storage.graph_store import GraphStore


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def details_of(builder: InvestigationBuilder, identifier: str) -> EntityDetails:
    details = entity_details(builder.connection, identifier)
    assert details is not None
    return details


def siren_of(identifier: str) -> str:
    return identifier.removeprefix("company:")


def spaced(siren: str) -> str:
    return f"{siren[:3]} {siren[3:6]} {siren[6:]}"


def test_a_closed_company_shows_its_status_identifiers_and_dates(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    details = details_of(builder, scenario.dupont_services)
    siren = siren_of(scenario.dupont_services)
    assert (details.kind_label, details.name) == ("Entreprise", "DUPONT SERVICES")
    assert details.badges == (Badge("Fermée", BadgeTone.CLOSED),)
    assert details.facts == (
        f"SIREN {spaced(siren)}",
        "Créée le 01/06/2019",
        "Fermée le 15/01/2023",
    )
    assert (details.copy_label, details.copy_value) == ("Copier le SIREN", siren)
    assert details.directory_url == f"https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"
    assert details.expandable
    assert not details.expanded
    assert details.expanded_on == ""


def test_an_active_company_known_only_as_director_says_so(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    acme = details_of(builder, scenario.acme)
    assert acme.badges == (Badge("Active", BadgeTone.ACTIVE),)
    assert "NAF" not in " ".join(acme.facts)
    holding = details_of(builder, scenario.holding)
    assert holding.badges == (
        Badge("Active", BadgeTone.ACTIVE),
        Badge("Connue comme dirigeante seulement", BadgeTone.OUTLINE),
    )


def test_a_company_shows_its_activity(builder: InvestigationBuilder) -> None:
    company = builder.company("ACME PLOMBERIE", date(2021, 3, 1), "43.22A")
    assert details_of(builder, company).facts[-1] == "NAF 43.22A"


def test_an_establishment_shows_its_siret_and_status(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    closed = details_of(builder, scenario.dupont_office)
    siret = scenario.dupont_office.removeprefix("establishment:")
    assert closed.kind_label == "Établissement"
    assert closed.badges == (
        Badge("Siège", BadgeTone.OUTLINE),
        Badge("Fermé", BadgeTone.CLOSED),
    )
    assert closed.facts == (
        f"SIRET {spaced(siret[:9])} {siret[9:]}",
        "Fermé le 15/01/2023",
    )
    assert (closed.copy_label, closed.copy_value) == ("Copier le SIRET", siret)
    assert closed.directory_url.endswith(f"/etablissement/{siret}")
    assert not closed.expandable


def test_an_open_establishment_says_so(builder: InvestigationBuilder) -> None:
    company = builder.company("ACME PLOMBERIE")
    address = builder.address("12 RUE DES LILAS 31000 TOULOUSE", postcode="31000")
    office = builder.establishment(company, address)
    GraphStore(builder.connection).save_entity(
        CollectedEntity(
            office,
            "Siège — TOULOUSE",
            {"is_open": True, "creation_date": "2021-03-01", "activity": "43.22A"},
        ),
        builder.response,
    )
    details = details_of(builder, office)
    assert Badge("Ouvert", BadgeTone.ACTIVE) in details.badges
    assert details.facts[-2:] == ("Créé le 01/03/2021", "NAF 43.22A")


def test_a_person_shows_birth_and_nationality(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    GraphStore(builder.connection).save_entity(
        CollectedEntity(scenario.jean, "Jean DUPONT", {"nationality": "Française"}),
        builder.response,
    )
    details = details_of(builder, scenario.jean)
    assert (details.kind_label, details.badges) == ("Personne", ())
    assert details.facts == ("Né en 05/1980", "Nationalité Française")
    assert (details.copy_label, details.copy_value) == ("Copier le nom", "Jean DUPONT")
    assert details.directory_url.endswith("/rechercher?terme=Jean%20DUPONT")


def test_an_address_shows_its_postcode_and_town(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    GraphStore(builder.connection).save_entity(
        CollectedEntity(scenario.address, "12 RUE DES LILAS 31000 TOULOUSE", {"city": "TOULOUSE"}),
        builder.response,
    )
    details = details_of(builder, scenario.address)
    assert details.facts == ("Code postal 31000", "Commune TOULOUSE")
    assert details.copy_label == "Copier l'adresse"
    assert details.directory_url.startswith("https://annuaire-entreprises.data.gouv.fr/rechercher")


def test_a_foreign_company_shows_its_country_without_directory(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    details = details_of(builder, scenario.invest)
    assert details.kind_label == "Entreprise étrangère"
    assert details.facts == ("Pays Royaume-Uni",)
    assert details.directory_url == ""
    assert not details.expandable


def test_a_company_without_siren_copies_its_name(builder: InvestigationBuilder) -> None:
    company = builder.company("ACME PLOMBERIE")
    GraphStore(builder.connection).save_entity(
        CollectedEntity(company, "ACME PLOMBERIE", {"siren": None}), builder.response
    )
    builder.connection.execute(
        "UPDATE entity SET attributes = '{}' WHERE identifier = ?", (company,)
    )
    details = details_of(builder, company)
    assert (details.copy_label, details.directory_url, details.facts) == (
        "Copier le nom",
        "",
        (),
    )


def test_an_expanded_entity_tells_when(builder: InvestigationBuilder) -> None:
    person = builder.person("Jean", "DUPONT", expanded=True)
    details = details_of(builder, person)
    moment = COLLECTED_AT.astimezone().strftime("%d/%m/%Y à %H:%M")
    assert details.expanded
    assert details.expanded_on == f"Étendue le {moment}"


def test_an_unknown_entity_has_no_details(builder: InvestigationBuilder) -> None:
    assert entity_details(builder.connection, "company:100000000") is None


def test_dates_are_written_the_french_way() -> None:
    assert written_day("2023-01-15") == "15/01/2023"
    assert written_day("pas une date") == ""
    assert written_day(None) == ""
    assert written_month("1980-05") == "05/1980"
    assert written_month(None) == ""


def test_a_secondary_establishment_has_no_head_office_badge(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    builder.connection.execute(
        "UPDATE entity SET attributes = ? WHERE identifier = ?",
        ('{"is_open": true}', scenario.acme_office),
    )
    assert details_of(builder, scenario.acme_office).badges == (Badge("Ouvert", BadgeTone.ACTIVE),)
