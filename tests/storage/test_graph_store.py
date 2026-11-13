import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.entities import (
    CollectedEntity,
    CollectedLink,
    EntityKind,
    address_identifier,
    company_identifier,
    establishment_identifier,
    establishment_of_link,
    foreign_company_identifier,
    located_at_link,
    mandate_link,
    person_identifier,
    registered_office_link,
    same_person_link,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)

FIRST_COLLECTION = datetime(2026, 11, 2, 23, 11, tzinfo=UTC)

DUPONT_SERVICES = CollectedEntity(
    company_identifier("222222222"),
    "DUPONT SERVICES",
    {"siren": "222222222", "naf": "43.22A", "active": False, "created_on": "2021-03-01"},
)
TOULOUSE_ESTABLISHMENT = CollectedEntity(
    establishment_identifier("22222222200015"),
    "Siège - TOULOUSE",
    {"siret": "22222222200015", "headquarters": True},
)
JEAN_DUPONT = CollectedEntity(
    person_identifier("DUPONT", "Jean", "1980-05"),
    "Jean DUPONT",
    {"last_name": "DUPONT", "first_names": "Jean", "month_of_birth": "1980-05"},
)
LILAS_ADDRESS = CollectedEntity(
    address_identifier("12 rue des Lilas 31000 Toulouse"),
    "12 RUE DES LILAS 31000 TOULOUSE",
    {"postal_code": "31000", "city": "TOULOUSE"},
)
DUPONT_INVEST = CollectedEntity(
    foreign_company_identifier("DUPONT INVEST LTD", "Royaume-Uni"),
    "DUPONT INVEST LTD",
    {"country": "Royaume-Uni"},
)
EVERY_KIND = [DUPONT_SERVICES, TOULOUSE_ESTABLISHMENT, JEAN_DUPONT, LILAS_ADDRESS, DUPONT_INVEST]


def response_at(store: GraphStore, collected_at: datetime) -> ResponseSummary:
    return ResponseStore(store.connection).save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            collected_at,
        )
    )


@pytest.fixture
def connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    library = InvestigationLibrary(tmp_path)
    library.create("faux-plombiers-31", "")
    with library.open("faux-plombiers-31") as opened:
        yield opened.connection


@pytest.fixture
def graph_store(connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(connection)


@pytest.mark.parametrize("collected_entity", EVERY_KIND, ids=lambda entity: entity.kind.value)
def test_every_entity_kind_is_stored_and_read_back(
    graph_store: GraphStore, collected_entity: CollectedEntity
) -> None:
    stored = graph_store.save_entity(collected_entity, response_at(graph_store, FIRST_COLLECTION))
    assert stored.identifier == collected_entity.identifier
    assert stored.kind is collected_entity.kind
    assert stored.label == collected_entity.label
    assert stored.attributes == collected_entity.attributes
    assert stored.first_collected_at == FIRST_COLLECTION
    assert stored.last_collected_at == FIRST_COLLECTION
    assert graph_store.entity(collected_entity.identifier) == stored


def test_a_missing_entity_is_none(graph_store: GraphStore) -> None:
    assert graph_store.entity(company_identifier("999999999")) is None
    with pytest.raises(KeyError):
        graph_store.require_entity(company_identifier("999999999"))


def test_entities_are_listed_by_identifier_and_by_kind(graph_store: GraphStore) -> None:
    for collected_entity in EVERY_KIND:
        graph_store.save_entity(collected_entity, response_at(graph_store, FIRST_COLLECTION))
    assert len(graph_store.entities()) == len(EVERY_KIND)
    assert [entity.identifier for entity in graph_store.entities()] == sorted(
        entity.identifier for entity in EVERY_KIND
    )
    assert [entity.label for entity in graph_store.entities(EntityKind.PERSON)] == ["Jean DUPONT"]


def test_attributes_keep_accents_and_types(graph_store: GraphStore) -> None:
    stored = graph_store.save_entity(
        CollectedEntity(
            company_identifier("111111111"),
            "ACME PLOMBERIE",
            {
                "activity": "Travaux d'installation d'eau et de gaz",
                "employees": 12,
                "capital": 1500.5,
                "closed_on": None,
            },
        ),
        response_at(graph_store, FIRST_COLLECTION),
    )
    assert stored.attributes == {
        "activity": "Travaux d'installation d'eau et de gaz",
        "employees": 12,
        "capital": 1500.5,
        "closed_on": None,
    }


ACME_PLOMBERIE = CollectedEntity(company_identifier("111111111"), "ACME PLOMBERIE")
JEAN_PIERRE_DUPONT = CollectedEntity(
    person_identifier("DUPONT", "Jean Pierre", "1980-05"), "Jean Pierre DUPONT"
)
EVERY_LINK_KIND = [
    mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président"),
    registered_office_link(DUPONT_SERVICES.identifier, LILAS_ADDRESS.identifier),
    located_at_link(TOULOUSE_ESTABLISHMENT.identifier, LILAS_ADDRESS.identifier),
    establishment_of_link(TOULOUSE_ESTABLISHMENT.identifier, DUPONT_SERVICES.identifier),
    same_person_link(JEAN_DUPONT.identifier, JEAN_PIERRE_DUPONT.identifier),
    mandate_link(DUPONT_INVEST.identifier, ACME_PLOMBERIE.identifier, "Associé"),
]


@pytest.fixture
def scenario_store(graph_store: GraphStore) -> GraphStore:
    for collected_entity in [*EVERY_KIND, ACME_PLOMBERIE, JEAN_PIERRE_DUPONT]:
        graph_store.save_entity(collected_entity, response_at(graph_store, FIRST_COLLECTION))
    return graph_store


@pytest.mark.parametrize("collected_link", EVERY_LINK_KIND, ids=lambda link: link.kind.value)
def test_every_link_kind_is_stored_and_read_back(
    scenario_store: GraphStore, collected_link: CollectedLink
) -> None:
    stored = scenario_store.save_link(
        collected_link, response_at(scenario_store, FIRST_COLLECTION)
    )
    assert (stored.source, stored.target, stored.kind, stored.role) == (
        collected_link.source,
        collected_link.target,
        collected_link.kind,
        collected_link.role,
    )
    assert stored.identifier == collected_link.identifier
    assert stored.first_collected_at == stored.last_collected_at == FIRST_COLLECTION
    assert scenario_store.link(collected_link.identifier) == stored


def test_the_links_of_an_entity_include_both_directions(scenario_store: GraphStore) -> None:
    for collected_link in EVERY_LINK_KIND:
        scenario_store.save_link(collected_link, response_at(scenario_store, FIRST_COLLECTION))
    kinds_around_dupont_services = sorted(
        link.kind.value for link in scenario_store.links_of(DUPONT_SERVICES.identifier)
    )
    assert kinds_around_dupont_services == ["establishment_of", "mandate", "registered_office"]
    assert len(scenario_store.links()) == len(EVERY_LINK_KIND)


def test_a_link_to_an_unknown_entity_is_refused(graph_store: GraphStore) -> None:
    graph_store.save_entity(JEAN_DUPONT, response_at(graph_store, FIRST_COLLECTION))
    with pytest.raises(sqlite3.IntegrityError):
        graph_store.save_link(
            mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président"),
            response_at(graph_store, FIRST_COLLECTION),
        )
    assert graph_store.links() == []


def test_a_missing_link_is_none(graph_store: GraphStore) -> None:
    assert graph_store.link("link:0000000000000000") is None
    with pytest.raises(KeyError):
        graph_store.require_link("link:0000000000000000")


SECOND_COLLECTION = datetime(2026, 11, 4, 9, 30, tzinfo=UTC)
EARLIER_COLLECTION = datetime(2026, 10, 1, 8, 0, tzinfo=UTC)


def collect_dupont_services(store: GraphStore, collected_at: datetime) -> None:
    response = response_at(store, collected_at)
    store.save_entity(DUPONT_SERVICES, response)
    store.save_entity(TOULOUSE_ESTABLISHMENT, response)
    store.save_entity(LILAS_ADDRESS, response)
    store.save_entity(JEAN_DUPONT, response)
    for collected_link in [
        mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président"),
        registered_office_link(DUPONT_SERVICES.identifier, LILAS_ADDRESS.identifier),
        located_at_link(TOULOUSE_ESTABLISHMENT.identifier, LILAS_ADDRESS.identifier),
        establishment_of_link(TOULOUSE_ESTABLISHMENT.identifier, DUPONT_SERVICES.identifier),
    ]:
        store.save_link(collected_link, response)


def test_collecting_the_same_company_twice_leaves_one_entity_and_the_same_links(
    graph_store: GraphStore,
) -> None:
    collect_dupont_services(graph_store, FIRST_COLLECTION)
    entities_after_first = [entity.identifier for entity in graph_store.entities()]
    links_after_first = [link.identifier for link in graph_store.links()]
    collect_dupont_services(graph_store, SECOND_COLLECTION)
    assert [entity.identifier for entity in graph_store.entities()] == entities_after_first
    assert [link.identifier for link in graph_store.links()] == links_after_first
    assert len(graph_store.entities(EntityKind.COMPANY)) == 1


def test_updating_an_entity_keeps_its_first_collection_date_and_updates_its_last_one(
    graph_store: GraphStore,
) -> None:
    graph_store.save_entity(DUPONT_SERVICES, response_at(graph_store, FIRST_COLLECTION))
    updated = graph_store.save_entity(DUPONT_SERVICES, response_at(graph_store, SECOND_COLLECTION))
    assert updated.first_collected_at == FIRST_COLLECTION
    assert updated.last_collected_at == SECOND_COLLECTION


def test_a_newer_collection_updates_the_label_and_the_attributes_it_brings(
    graph_store: GraphStore,
) -> None:
    graph_store.save_entity(DUPONT_SERVICES, response_at(graph_store, FIRST_COLLECTION))
    renamed = CollectedEntity(
        DUPONT_SERVICES.identifier, "DUPONT SERVICES SAS", {"active": True, "employees": 3}
    )
    updated = graph_store.save_entity(renamed, response_at(graph_store, SECOND_COLLECTION))
    assert updated.label == "DUPONT SERVICES SAS"
    assert updated.attributes == {
        "siren": "222222222",
        "naf": "43.22A",
        "active": True,
        "created_on": "2021-03-01",
        "employees": 3,
    }


def test_an_older_collection_never_overwrites_newer_facts(graph_store: GraphStore) -> None:
    graph_store.save_entity(DUPONT_SERVICES, response_at(graph_store, SECOND_COLLECTION))
    older = CollectedEntity(
        DUPONT_SERVICES.identifier, "ANCIEN NOM", {"active": True, "former_name": "ANCIEN NOM"}
    )
    updated = graph_store.save_entity(older, response_at(graph_store, EARLIER_COLLECTION))
    assert updated.label == "DUPONT SERVICES"
    assert updated.attributes["active"] is False
    assert updated.attributes["former_name"] == "ANCIEN NOM"
    assert updated.first_collected_at == EARLIER_COLLECTION
    assert updated.last_collected_at == SECOND_COLLECTION


def test_collecting_a_link_again_keeps_its_first_collection_date(
    scenario_store: GraphStore,
) -> None:
    president = mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président")
    scenario_store.save_link(president, response_at(scenario_store, FIRST_COLLECTION))
    updated = scenario_store.save_link(president, response_at(scenario_store, SECOND_COLLECTION))
    assert updated.first_collected_at == FIRST_COLLECTION
    assert updated.last_collected_at == SECOND_COLLECTION
    earlier = scenario_store.save_link(president, response_at(scenario_store, EARLIER_COLLECTION))
    assert earlier.first_collected_at == EARLIER_COLLECTION
    assert earlier.last_collected_at == SECOND_COLLECTION
    assert len(scenario_store.links()) == 1


def test_a_new_role_between_the_same_entities_is_a_new_mandate(
    scenario_store: GraphStore,
) -> None:
    scenario_store.save_link(
        mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Président"),
        response_at(scenario_store, FIRST_COLLECTION),
    )
    scenario_store.save_link(
        mandate_link(JEAN_DUPONT.identifier, DUPONT_SERVICES.identifier, "Associé"),
        response_at(scenario_store, FIRST_COLLECTION),
    )
    assert sorted(link.role for link in scenario_store.links()) == ["Associé", "Président"]
