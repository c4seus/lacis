import sqlite3
from datetime import UTC, datetime

import pytest

from lacis.identity.homonyms import (
    FirstNameRelation,
    HomonymPair,
    PersonIdentity,
    first_name_relation,
    homonym_pair,
    homonym_pairs,
)
from lacis.storage.entities import Attributes, CollectedEntity, person_identifier
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


@pytest.fixture
def response(response_store: ResponseStore) -> ResponseSummary:
    return response_store.save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            datetime(2026, 11, 6, tzinfo=UTC),
            {"q": "dupont"},
        )
    )


def add_person(
    graph_store: GraphStore,
    response: ResponseSummary,
    last_name: str,
    first_names: str,
    birth_month: str | None,
) -> str:
    identifier = person_identifier(last_name, first_names, birth_month)
    label = f"{first_names} {last_name.upper()}".strip()
    attributes: Attributes = {
        "last_name": last_name,
        "first_names": first_names,
        "birth_month": birth_month,
    }
    graph_store.save_entity(CollectedEntity(identifier, label, attributes), response)
    return identifier


def pairs_of(graph_store: GraphStore) -> list[tuple[str, str, FirstNameRelation]]:
    return [
        (pair.first.label, pair.second.label, pair.first_name_relation)
        for pair in homonym_pairs(graph_store)
    ]


@pytest.mark.parametrize(
    ("first", "second", "relation"),
    [
        (("JEAN",), ("JEAN",), FirstNameRelation.SAME),
        (("JEAN",), ("JEAN", "PIERRE"), FirstNameRelation.COMPOUND),
        (("JEAN", "PIERRE"), ("JEAN",), FirstNameRelation.COMPOUND),
        ((), ("JEAN",), FirstNameRelation.UNKNOWN),
        (("JEAN", "PIERRE"), ("JEAN", "MARC"), None),
        (("PIERRE",), ("JEAN", "PIERRE"), None),
        (("MARIE",), ("JEAN",), None),
    ],
)
def test_first_names_are_compatible_when_one_starts_the_other(
    first: tuple[str, ...], second: tuple[str, ...], relation: FirstNameRelation | None
) -> None:
    assert first_name_relation(first, second) is relation


def test_jean_and_jean_pierre_dupont_born_the_same_month_are_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    [pair] = homonym_pairs(graph_store)
    assert (pair.first.label, pair.second.label) == ("Jean DUPONT", "Jean Pierre DUPONT")
    assert pair.first_name_relation is FirstNameRelation.COMPOUND
    assert pair.same_birth_month


def test_people_born_different_months_are_never_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", "1980-06")
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1975-02")
    assert homonym_pairs(graph_store) == []


def test_a_person_without_birth_month_may_be_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "Dupont", "jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", None)
    [pair] = homonym_pairs(graph_store)
    assert pair.first_name_relation is FirstNameRelation.SAME
    assert not pair.same_birth_month


def test_other_last_names_and_incompatible_first_names_are_not_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Marc", "1980-05")
    add_person(graph_store, response, "DUPONTEL", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Marie", "1980-05")
    assert homonym_pairs(graph_store) == []


def test_every_compatible_pair_is_listed_in_name_order(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Marc", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "MARTIN", "", "1990-01")
    add_person(graph_store, response, "MARTIN", "Paul", "1990-01")
    graph_store.save_entity(CollectedEntity("company:111111111", "DUPONT"), response)
    assert pairs_of(graph_store) == [
        ("Jean DUPONT", "Jean Marc DUPONT", FirstNameRelation.COMPOUND),
        ("Jean DUPONT", "Jean Pierre DUPONT", FirstNameRelation.COMPOUND),
        ("MARTIN", "Paul MARTIN", FirstNameRelation.UNKNOWN),
    ]


def test_people_without_last_name_are_never_paired() -> None:
    nameless = PersonIdentity("person:1", "?", "", ("JEAN",), None)
    other = PersonIdentity("person:2", "?", "", ("JEAN",), None)
    pair = HomonymPair(nameless, other, FirstNameRelation.SAME)
    assert not pair.same_birth_month
    assert homonym_pair(nameless, other) is None
