import hashlib
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from statistics import fmean

from lacis.storage.entities import Entity, EntityKind

type Point = tuple[float, float]
type Pair = tuple[str, str]

COLUMN_GAP = 320.0
MINIMUM_GAP = 170.0
IDEAL_DISTANCE = 170.0
REPULSION_REACH = 2.5 * IDEAL_DISTANCE
NEWCOMER_DISTANCE = 120.0
STARTING_TEMPERATURE = IDEAL_DISTANCE / 2
LAST_TEMPERATURE = 1.0
ITERATIONS = 150
LAYERED_LIMIT = 60
SCATTERED_TEMPERATURE_SHARE = 0.1
DIRECTOR_ROW = 0
COMPANY_ROW = 1
ESTABLISHMENT_ROW = 2
ADDRESS_ROW = 3
ROW_HEIGHTS = {DIRECTOR_ROW: 0.0, COMPANY_ROW: 170.0, ESTABLISHMENT_ROW: 310.0, ADDRESS_ROW: 420.0}
ROW_ORDER = (COMPANY_ROW, DIRECTOR_ROW, ESTABLISHMENT_ROW, ADDRESS_ROW)


def no_pause() -> None:
    return None


@dataclass(frozen=True)
class Cooling:
    iterations: int = ITERATIONS
    starting_temperature: float = STARTING_TEMPERATURE


GENTLE_COOLING = Cooling()


@dataclass(frozen=True)
class LayoutRequest:
    entities: list[Entity]
    pairs: list[Pair]
    layered_pairs: list[Pair]
    director_only: set[str]
    known: dict[str, Point]


@dataclass
class Block:
    identifiers: list[str]
    desired: list[float]
    start: float = field(init=False)

    def __post_init__(self) -> None:
        self.place()

    def place(self) -> None:
        self.start = fmean(
            position - index * MINIMUM_GAP for index, position in enumerate(self.desired)
        )

    @property
    def end(self) -> float:
        return self.start + (len(self.identifiers) - 1) * MINIMUM_GAP

    def absorb(self, other: "Block") -> None:
        self.identifiers.extend(other.identifiers)
        self.desired.extend(other.desired)
        self.place()


def spread(desired: dict[str, float]) -> dict[str, float]:
    blocks: list[Block] = []
    for identifier, position in sorted(desired.items(), key=lambda item: (item[1], item[0])):
        block = Block([identifier], [position])
        while blocks and blocks[-1].end + MINIMUM_GAP > block.start:
            previous = blocks.pop()
            previous.absorb(block)
            block = previous
        blocks.append(block)
    return {
        identifier: block.start + index * MINIMUM_GAP
        for block in blocks
        for index, identifier in enumerate(block.identifiers)
    }


def neighbourhoods(pairs: Iterable[Pair]) -> dict[str, list[str]]:
    neighbours: dict[str, list[str]] = {}
    for first, second in pairs:
        neighbours.setdefault(first, []).append(second)
        neighbours.setdefault(second, []).append(first)
    return neighbours


def row_of(entity: Entity, director_only: set[str]) -> int:
    if entity.kind is EntityKind.COMPANY:
        return DIRECTOR_ROW if entity.identifier in director_only else COMPANY_ROW
    if entity.kind is EntityKind.ESTABLISHMENT:
        return ESTABLISHMENT_ROW
    if entity.kind is EntityKind.ADDRESS:
        return ADDRESS_ROW
    return DIRECTOR_ROW


def layered_positions(
    entities: list[Entity], pairs: list[Pair], director_only: set[str]
) -> dict[str, Point]:
    neighbours = neighbourhoods(pairs)
    rows: dict[int, list[Entity]] = {row: [] for row in ROW_ORDER}
    for entity in entities:
        rows[row_of(entity, director_only)].append(entity)
    placed: dict[str, float] = {}
    positions: dict[str, Point] = {}
    for row in ROW_ORDER:
        members = sorted(rows[row], key=lambda entity: (entity.label, entity.identifier))
        desired = {}
        for index, entity in enumerate(members):
            around = [
                placed[neighbour]
                for neighbour in neighbours.get(entity.identifier, [])
                if neighbour in placed
            ]
            desired[entity.identifier] = fmean(around) if around else index * COLUMN_GAP
        for identifier, position in spread(desired).items():
            placed[identifier] = position
            positions[identifier] = (position, ROW_HEIGHTS[row])
    return positions


def direction_of(identifier: str) -> float:
    digest = hashlib.sha256(identifier.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") / 2**32 * math.tau


def beside(centre: Point, identifier: str, distance: float) -> Point:
    angle = direction_of(identifier)
    return (centre[0] + distance * math.cos(angle), centre[1] + distance * math.sin(angle))


def free_spot(positions: dict[str, Point]) -> Point:
    return (
        max(x for x, _ in positions.values()) + COLUMN_GAP,
        min(y for _, y in positions.values()),
    )


def scattered_side(count: int) -> float:
    return math.sqrt(count) * IDEAL_DISTANCE


def scattered_positions(identifiers: Iterable[str]) -> dict[str, Point]:
    ordered = sorted(identifiers)
    side = scattered_side(len(ordered))
    positions = {}
    for identifier in ordered:
        digest = hashlib.sha256(identifier.encode("utf-8")).digest()
        across = int.from_bytes(digest[:4], "big") / 2**32
        down = int.from_bytes(digest[4:8], "big") / 2**32
        positions[identifier] = (across * side, down * side)
    return positions


def first_positions(
    entities: list[Entity], pairs: list[Pair], director_only: set[str]
) -> dict[str, Point]:
    if len(entities) <= LAYERED_LIMIT:
        return layered_positions(entities, pairs, director_only)
    return scattered_positions(entity.identifier for entity in entities)


def initial_positions(
    entities: list[Entity],
    pairs: list[Pair],
    director_only: set[str],
    known: dict[str, Point],
) -> dict[str, Point]:
    identifiers = {entity.identifier for entity in entities}
    positions = {
        identifier: point for identifier, point in known.items() if identifier in identifiers
    }
    if not positions:
        return first_positions(entities, pairs, director_only)
    neighbours = neighbourhoods(pairs)
    pending = sorted(identifiers - set(positions))
    while pending:
        newcomers = {}
        for identifier in pending:
            around = [
                positions[neighbour]
                for neighbour in neighbours.get(identifier, [])
                if neighbour in positions
            ]
            if around:
                centre = (fmean(x for x, _ in around), fmean(y for _, y in around))
                newcomers[identifier] = beside(centre, identifier, NEWCOMER_DISTANCE)
        if not newcomers:
            newcomers[pending[0]] = free_spot(positions)
        positions.update(newcomers)
        pending = [identifier for identifier in pending if identifier not in newcomers]
    return positions


def cell_of(point: Point) -> tuple[int, int]:
    return (math.floor(point[0] / REPULSION_REACH), math.floor(point[1] / REPULSION_REACH))


def nearby(cells: dict[tuple[int, int], list[str]], point: Point) -> Iterable[str]:
    column, row = cell_of(point)
    for column_step in (-1, 0, 1):
        for row_step in (-1, 0, 1):
            yield from cells.get((column + column_step, row + row_step), ())


def separation(first: str, second: str, positions: dict[str, Point]) -> tuple[float, float, float]:
    delta_x = positions[first][0] - positions[second][0]
    delta_y = positions[first][1] - positions[second][1]
    distance = math.hypot(delta_x, delta_y)
    if distance == 0:
        angle = direction_of(f"{first}|{second}")
        return math.cos(angle), math.sin(angle), 1.0
    return delta_x, delta_y, distance


def repulsion(
    identifier: str, positions: dict[str, Point], cells: dict[tuple[int, int], list[str]]
) -> Point:
    push_x = push_y = 0.0
    for other in nearby(cells, positions[identifier]):
        if other == identifier:
            continue
        delta_x, delta_y, distance = separation(identifier, other, positions)
        if distance < REPULSION_REACH:
            strength = IDEAL_DISTANCE**2 / distance**2
            push_x += delta_x * strength
            push_y += delta_y * strength
    return push_x, push_y


def attraction(moves: dict[str, Point], links: list[Pair], positions: dict[str, Point]) -> None:
    for first, second in links:
        delta_x, delta_y, distance = separation(first, second, positions)
        strength = distance / IDEAL_DISTANCE
        if first in moves:
            move_x, move_y = moves[first]
            moves[first] = (move_x - delta_x * strength, move_y - delta_y * strength)
        if second in moves:
            move_x, move_y = moves[second]
            moves[second] = (move_x + delta_x * strength, move_y + delta_y * strength)


def limited(move: Point, temperature: float) -> Point:
    length = math.hypot(*move)
    if length <= temperature:
        return move
    return (move[0] / length * temperature, move[1] / length * temperature)


def temperature_at(iteration: int, iterations: int, starting_temperature: float) -> float:
    progress = iteration / max(iterations - 1, 1)
    return starting_temperature + (LAST_TEMPERATURE - starting_temperature) * progress


def step(
    positions: dict[str, Point], links: list[Pair], free: list[str], temperature: float
) -> None:
    cells: dict[tuple[int, int], list[str]] = {}
    for identifier, point in positions.items():
        cells.setdefault(cell_of(point), []).append(identifier)
    moves = {identifier: repulsion(identifier, positions, cells) for identifier in free}
    attraction(moves, links, positions)
    for identifier, move in moves.items():
        move_x, move_y = limited(move, temperature)
        x, y = positions[identifier]
        positions[identifier] = (x + move_x, y + move_y)


def relax(
    positions: dict[str, Point],
    pairs: list[Pair],
    fixed: set[str],
    pause: Callable[[], None] = no_pause,
    cooling: Cooling = GENTLE_COOLING,
) -> dict[str, Point]:
    positions = dict(positions)
    free = sorted(set(positions) - fixed)
    if not free:
        return positions
    links = [pair for pair in pairs if pair[0] in positions and pair[1] in positions]
    for iteration in range(cooling.iterations):
        step(
            positions,
            links,
            free,
            temperature_at(iteration, cooling.iterations, cooling.starting_temperature),
        )
        pause()
    return positions


def lay_out(request: LayoutRequest, pause: Callable[[], None] = no_pause) -> dict[str, Point]:
    pause()
    positions = initial_positions(
        request.entities, request.layered_pairs, request.director_only, request.known
    )
    fixed = set(request.known) & set(positions)
    if fixed:
        return relax(positions, request.pairs, fixed, pause)
    if len(request.entities) <= LAYERED_LIMIT:
        return positions
    side = scattered_side(len(request.entities))
    cooling = Cooling(starting_temperature=side * SCATTERED_TEMPERATURE_SHARE)
    return relax(positions, request.pairs, set(), pause, cooling)
