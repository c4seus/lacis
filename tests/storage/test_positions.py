import sqlite3

import pytest

from investigation_builder import InvestigationBuilder
from lacis.storage.positions import Position, PositionStore


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


def test_a_new_investigation_has_no_position(investigation_connection: sqlite3.Connection) -> None:
    assert PositionStore(investigation_connection).positions() == {}


def test_computed_positions_are_saved_and_replaced(builder: InvestigationBuilder) -> None:
    acme = builder.company("ACME PLOMBERIE")
    jean = builder.person("Jean", "DUPONT")
    store = PositionStore(builder.connection)
    store.save({acme: Position(10.0, 20.0), jean: Position(-5.5, 0.0)})
    store.save({acme: Position(30.0, 40.0)})
    assert store.positions() == {acme: Position(30.0, 40.0), jean: Position(-5.5, 0.0)}


def test_positions_moved_by_the_investigator_are_remembered_as_such(
    builder: InvestigationBuilder,
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    store = PositionStore(builder.connection)
    store.save({acme: Position(10.0, 20.0)})
    store.move({acme: (110.0, 120.0)})
    assert store.positions() == {acme: Position(110.0, 120.0, moved_by_investigator=True)}


def test_a_position_needs_its_entity(builder: InvestigationBuilder) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        PositionStore(builder.connection).save({"company:100000000": Position(0.0, 0.0)})


def test_moving_entities_does_not_revise_the_investigation(builder: InvestigationBuilder) -> None:
    acme = builder.company("ACME PLOMBERIE")
    query = "SELECT revision FROM investigation"
    before = builder.connection.execute(query).fetchone()
    PositionStore(builder.connection).move({acme: (1.0, 2.0)})
    assert builder.connection.execute(query).fetchone() == before
