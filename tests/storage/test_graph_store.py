import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.entities import (
    CollectedEntity,
    EntityKind,
    address_identifier,
    company_identifier,
    establishment_identifier,
    foreign_company_identifier,
    person_identifier,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import InvestigationLibrary

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
    stored = graph_store.save_entity(collected_entity, FIRST_COLLECTION)
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
        graph_store.save_entity(collected_entity, FIRST_COLLECTION)
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
        FIRST_COLLECTION,
    )
    assert stored.attributes == {
        "activity": "Travaux d'installation d'eau et de gaz",
        "employees": 12,
        "capital": 1500.5,
        "closed_on": None,
    }
