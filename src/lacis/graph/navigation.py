import math
from enum import Enum

from lacis.graph.drawing import GraphDrawing
from lacis.graph.layout import Point

WIDEST_ANGLE = math.radians(75)


class Direction(Enum):
    LEFT = (-1.0, 0.0)
    RIGHT = (1.0, 0.0)
    UP = (0.0, -1.0)
    DOWN = (0.0, 1.0)


def angle_from(direction: Direction, start: Point, end: Point) -> float:
    delta_x = end[0] - start[0]
    delta_y = end[1] - start[1]
    along = delta_x * direction.value[0] + delta_y * direction.value[1]
    across = delta_x * direction.value[1] - delta_y * direction.value[0]
    return abs(math.atan2(across, along))


def linked_towards(
    drawing: GraphDrawing,
    points: dict[str, Point],
    identifier: str,
    direction: Direction,
    shown: set[str],
) -> str | None:
    start = points[identifier]
    candidates = []
    for edge in drawing.edges:
        if not edge.touches(identifier):
            continue
        other = edge.other_end(identifier)
        if other not in shown or points[other] == start:
            continue
        angle = angle_from(direction, start, points[other])
        if angle <= WIDEST_ANGLE:
            distance = math.dist(start, points[other])
            candidates.append((distance * (1 + angle), other))
    return min(candidates)[1] if candidates else None


def starting_entity(
    drawing: GraphDrawing, points: dict[str, Point], shown: set[str]
) -> str | None:
    flagged = [
        node.identifier for node in drawing.nodes if node.identifier in shown and node.severity
    ]
    choices = flagged or [node.identifier for node in drawing.nodes if node.identifier in shown]
    if not choices:
        return None
    return min(choices, key=lambda identifier: (points[identifier][1], points[identifier][0]))
