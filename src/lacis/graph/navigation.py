from enum import Enum


class Direction(Enum):
    LEFT = (-1.0, 0.0)
    RIGHT = (1.0, 0.0)
    UP = (0.0, -1.0)
    DOWN = (0.0, 1.0)
