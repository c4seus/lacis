import sqlite3

import pytest

from investigation_builder import InvestigationBuilder
from lacis.storage.graph_store import GraphStore
from lacis.storage.tags import Tag, TagStore, tag_key, written_tag


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def store(builder: InvestigationBuilder) -> TagStore:
    return TagStore(builder.connection)


def test_a_tag_is_trimmed_and_ignores_case() -> None:
    assert written_tag("  réseau   Dupont ") == "réseau Dupont"
    assert tag_key("  Réseau   DUPONT ") == "réseau dupont"


def test_an_entity_has_no_tag_at_first(builder: InvestigationBuilder, store: TagStore) -> None:
    acme = builder.company("ACME PLOMBERIE")
    assert store.tags_of(acme) == ()
    assert store.tags() == ()
    assert store.tagged() == {}


def test_tags_are_added_and_sorted(builder: InvestigationBuilder, store: TagStore) -> None:
    acme = builder.company("ACME PLOMBERIE")
    assert store.add(acme, " réseau  Dupont ") == Tag("réseau dupont", "réseau Dupont")
    store.add(acme, "à recontacter")
    assert store.tags_of(acme) == (
        Tag("réseau dupont", "réseau Dupont"),
        Tag("à recontacter", "à recontacter"),
    )
    assert store.tagged() == {acme: frozenset({"réseau dupont", "à recontacter"})}


def test_the_same_tag_in_another_case_is_the_same_tag(
    builder: InvestigationBuilder, store: TagStore
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    dupont = builder.company("DUPONT SERVICES", identifier="company:222222222")
    store.add(acme, "Client")
    assert store.add(acme, "CLIENT") == Tag("client", "Client")
    assert store.add(dupont, "client") == Tag("client", "Client")
    assert store.tags_of(acme) == (Tag("client", "Client"),)
    assert store.tags() == (Tag("client", "Client"),)
    assert store.tagged() == {acme: frozenset({"client"}), dupont: frozenset({"client"})}


@pytest.mark.parametrize("text", ["", "   "])
def test_an_empty_tag_is_not_added(
    builder: InvestigationBuilder, store: TagStore, text: str
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    assert store.add(acme, text) is None
    assert store.tags_of(acme) == ()


def test_a_tag_is_removed_from_one_entity(builder: InvestigationBuilder, store: TagStore) -> None:
    acme = builder.company("ACME PLOMBERIE")
    dupont = builder.company("DUPONT SERVICES", identifier="company:222222222")
    store.add(acme, "client")
    store.add(dupont, "client")
    store.remove(acme, "client")
    assert store.tags_of(acme) == ()
    assert store.tagged() == {dupont: frozenset({"client"})}


def test_tags_never_change_the_collected_facts(
    builder: InvestigationBuilder, store: TagStore
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    graph_store = GraphStore(builder.connection)
    before = graph_store.entity(acme)
    store.add(acme, "client")
    assert graph_store.entity(acme) == before


def test_a_tag_needs_its_entity(store: TagStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.add("company:100000000", "client")
