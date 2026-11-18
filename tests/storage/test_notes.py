import sqlite3
from datetime import UTC, datetime

import pytest

from investigation_builder import InvestigationBuilder
from lacis.storage.graph_store import GraphStore
from lacis.storage.notes import EntityNote, NoteStore

FIRST_MOMENT = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
SECOND_MOMENT = datetime(2026, 11, 19, 14, 5, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.moments = [FIRST_MOMENT]

    def __call__(self) -> datetime:
        return self.moments[-1]


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(builder: InvestigationBuilder, clock: Clock) -> NoteStore:
    return NoteStore(builder.connection, clock)


def test_an_entity_has_no_note_at_first(builder: InvestigationBuilder, store: NoteStore) -> None:
    acme = builder.company("ACME PLOMBERIE")
    assert store.note(acme) is None
    assert store.noted() == frozenset()


def test_a_note_keeps_its_text_and_dates(
    builder: InvestigationBuilder, store: NoteStore, clock: Clock
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    saved = store.save(acme, "Même adresse que **DUPONT SERVICES**.")
    assert saved == EntityNote("Même adresse que **DUPONT SERVICES**.", FIRST_MOMENT, FIRST_MOMENT)
    clock.moments.append(SECOND_MOMENT)
    changed = store.save(acme, "Même gérant.")
    assert changed == EntityNote("Même gérant.", FIRST_MOMENT, SECOND_MOMENT)
    assert store.note(acme) == changed
    assert store.noted() == frozenset({acme})


def test_saving_the_same_text_keeps_the_date_of_the_last_change(
    builder: InvestigationBuilder, store: NoteStore, clock: Clock
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    store.save(acme, "Même gérant.")
    clock.moments.append(SECOND_MOMENT)
    assert store.save(acme, "Même gérant.") == EntityNote(
        "Même gérant.", FIRST_MOMENT, FIRST_MOMENT
    )


@pytest.mark.parametrize("text", ["", "  \n "])
def test_an_empty_note_is_removed(
    builder: InvestigationBuilder, store: NoteStore, text: str
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    store.save(acme, "À vérifier.")
    assert store.save(acme, text) is None
    assert store.note(acme) is None
    assert store.noted() == frozenset()


def test_a_note_never_changes_the_collected_facts(
    builder: InvestigationBuilder, store: NoteStore
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    graph_store = GraphStore(builder.connection)
    before = graph_store.entity(acme)
    store.save(acme, "Gérant de paille ?")
    assert graph_store.entity(acme) == before


def test_a_note_needs_its_entity(store: NoteStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.save("company:100000000", "Introuvable.")
