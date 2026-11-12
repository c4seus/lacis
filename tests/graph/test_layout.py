import math

import pytest

from investigation_builder import COLLECTED_AT
from lacis.graph.layout import (
    COLUMN_GAP,
    IDEAL_DISTANCE,
    ITERATIONS,
    LAYERED_LIMIT,
    NEWCOMER_DISTANCE,
    Cooling,
    LayoutRequest,
    Point,
    initial_positions,
    lay_out,
    layered_positions,
    relax,
    scattered_positions,
)
from lacis.storage.entities import Entity, EntityKind


def entity(identifier: str, kind: EntityKind = EntityKind.COMPANY) -> Entity:
    return Entity(identifier, kind, identifier.upper(), {}, COLLECTED_AT, COLLECTED_AT)


def distance(first: Point, second: Point) -> float:
    return math.dist(first, second)


def test_without_known_positions_entities_start_in_rows() -> None:
    entities = [entity("company:1"), entity("person:1", EntityKind.PERSON)]
    pairs = [("person:1", "company:1")]
    assert initial_positions(entities, pairs, set(), {}) == layered_positions(
        entities, pairs, set()
    )
    assert initial_positions(entities, pairs, set(), {"company:9": (5.0, 5.0)}) == (
        layered_positions(entities, pairs, set())
    )


def test_known_positions_are_kept_and_newcomers_join_their_neighbours() -> None:
    entities = [
        entity("company:1"),
        entity("company:2"),
        entity("person:1", EntityKind.PERSON),
        entity("person:2", EntityKind.PERSON),
    ]
    pairs = [("person:1", "company:1"), ("person:1", "company:2"), ("person:2", "person:1")]
    known = {"company:1": (0.0, 0.0), "company:2": (400.0, 0.0)}
    positions = initial_positions(entities, pairs, set(), known)
    assert positions["company:1"] == (0.0, 0.0)
    assert positions["company:2"] == (400.0, 0.0)
    assert distance(positions["person:1"], (200.0, 0.0)) == pytest.approx(NEWCOMER_DISTANCE)
    assert distance(positions["person:2"], positions["person:1"]) == pytest.approx(
        NEWCOMER_DISTANCE
    )


def test_a_newcomer_without_placed_neighbour_goes_beside_the_graph() -> None:
    entities = [entity("company:1"), entity("company:2"), entity("company:3")]
    known = {"company:1": (0.0, 50.0)}
    positions = initial_positions(entities, [("company:2", "company:3")], set(), known)
    assert positions["company:2"] == (COLUMN_GAP, 50.0)
    assert distance(positions["company:3"], positions["company:2"]) == pytest.approx(
        NEWCOMER_DISTANCE
    )


def test_fixed_entities_never_move() -> None:
    positions = {"company:1": (0.0, 0.0), "company:2": (10.0, 0.0), "person:1": (5.0, 5.0)}
    pairs = [("person:1", "company:1"), ("person:1", "company:2")]
    relaxed = relax(positions, pairs, {"company:1", "company:2"})
    assert relaxed["company:1"] == (0.0, 0.0)
    assert relaxed["company:2"] == (10.0, 0.0)
    assert relaxed["person:1"] != (5.0, 5.0)
    assert positions["person:1"] == (5.0, 5.0)


def test_entities_on_top_of_each_other_are_pushed_apart() -> None:
    positions = {"company:1": (0.0, 0.0), "company:2": (0.0, 0.0)}
    relaxed = relax(positions, [], set())
    assert distance(relaxed["company:1"], relaxed["company:2"]) > IDEAL_DISTANCE


def test_linked_entities_settle_near_the_ideal_distance() -> None:
    positions = {"company:1": (0.0, 0.0), "person:1": (1000.0, 0.0)}
    relaxed = relax(positions, [("person:1", "company:1")], {"company:1"})
    assert distance(relaxed["company:1"], relaxed["person:1"]) == pytest.approx(
        IDEAL_DISTANCE, rel=0.05
    )


def test_relaxing_is_deterministic_and_pauses_after_each_round() -> None:
    positions = {f"company:{index}": (float(index), 0.0) for index in range(6)}
    pairs = [(f"company:{index}", f"company:{index + 1}") for index in range(5)]
    pauses: list[None] = []
    first = relax(positions, pairs, set(), lambda: pauses.append(None))
    assert first == relax(positions, pairs, set())
    assert len(pauses) == ITERATIONS


def test_nothing_moves_when_every_entity_is_fixed() -> None:
    pauses: list[None] = []
    positions = {"company:1": (0.0, 0.0)}
    assert relax(positions, [], {"company:1"}, lambda: pauses.append(None)) == positions
    assert pauses == []


def test_links_to_unknown_entities_are_ignored() -> None:
    relaxed = relax({"company:1": (0.0, 0.0)}, [("company:1", "person:9")], set())
    assert set(relaxed) == {"company:1"}


def test_a_single_round_is_enough_to_relax() -> None:
    relaxed = relax(
        {"company:1": (0.0, 0.0), "company:2": (1.0, 0.0)},
        [],
        set(),
        cooling=Cooling(iterations=1),
    )
    assert distance(relaxed["company:1"], relaxed["company:2"]) > 1.0


def chain(count: int) -> tuple[list[Entity], list[tuple[str, str]]]:
    entities = [entity(f"company:{index}") for index in range(count)]
    pairs = [(f"company:{index}", f"company:{index + 1}") for index in range(count - 1)]
    return entities, pairs


def test_a_small_graph_is_first_laid_out_in_rows() -> None:
    entities, pairs = chain(LAYERED_LIMIT)
    pauses: list[None] = []
    positions = lay_out(
        LayoutRequest(entities, pairs, pairs, set(), {}), lambda: pauses.append(None)
    )
    assert positions == layered_positions(entities, pairs, set())
    assert pauses == [None]


def test_a_large_graph_is_first_scattered_then_relaxed() -> None:
    entities, pairs = chain(LAYERED_LIMIT + 1)
    identifiers = [item.identifier for item in entities]
    scattered = scattered_positions(identifiers)
    assert scattered == scattered_positions(reversed(identifiers))
    side = math.sqrt(len(entities)) * IDEAL_DISTANCE
    assert all(0 <= x <= side and 0 <= y <= side for x, y in scattered.values())
    positions = lay_out(LayoutRequest(entities, pairs, pairs, set(), {}))
    assert set(positions) == set(identifiers)
    assert positions != scattered
    links = [math.dist(positions[first], positions[second]) for first, second in pairs]
    assert sum(links) / len(links) < 2 * IDEAL_DISTANCE


def test_a_growing_graph_only_moves_its_newcomers() -> None:
    entities, pairs = chain(4)
    known = {"company:0": (0.0, 0.0), "company:1": (170.0, 0.0), "company:2": (340.0, 0.0)}
    positions = lay_out(LayoutRequest(entities, pairs, pairs, set(), known))
    assert {identifier: positions[identifier] for identifier in known} == known
    assert math.dist(positions["company:3"], known["company:2"]) == pytest.approx(
        IDEAL_DISTANCE, rel=0.2
    )
