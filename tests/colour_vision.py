from enum import StrEnum

MATRICES = {
    "protanopia": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deuteranopia": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritanopia": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}
LINEAR_THRESHOLD = 0.04045
ENCODED_THRESHOLD = 0.0031308


class ColourVision(StrEnum):
    PROTANOPIA = "protanopia"
    DEUTERANOPIA = "deuteranopia"
    TRITANOPIA = "tritanopia"


def linear(channel: int) -> float:
    value = channel / 255
    if value <= LINEAR_THRESHOLD:
        return value / 12.92
    return float(((value + 0.055) / 1.055) ** 2.4)


def encoded(value: float) -> int:
    clamped = min(max(value, 0.0), 1.0)
    if clamped <= ENCODED_THRESHOLD:
        return round(255 * 12.92 * clamped)
    return round(255 * (1.055 * float(clamped ** (1 / 2.4)) - 0.055))


def simulated(colour: str, vision: ColourVision) -> str:
    channels = [linear(int(colour[position : position + 2], 16)) for position in (1, 3, 5)]
    matrix = MATRICES[vision.value]
    seen = [encoded(sum(row[index] * channels[index] for index in range(3))) for row in matrix]
    return "#" + "".join(f"{channel:02x}" for channel in seen)
