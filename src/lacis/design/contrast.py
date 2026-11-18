from dataclasses import dataclass

from lacis.design.tokens import Theme

TEXT_MINIMUM_RATIO = 4.5
LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO = 3.0
HIGH_CONTRAST_TEXT_MINIMUM_RATIO = 7.0
HIGH_CONTRAST_INTERFACE_MINIMUM_RATIO = 4.5
LINEAR_CHANNEL_THRESHOLD = 0.04045
LINEAR_CHANNEL_DIVISOR = 12.92
GAMMA_OFFSET = 0.055
GAMMA_EXPONENT = 2.4
RED_WEIGHT = 0.2126
GREEN_WEIGHT = 0.7152
BLUE_WEIGHT = 0.0722
LUMINANCE_FLARE = 0.05
MAXIMUM_CHANNEL_VALUE = 255


@dataclass(frozen=True)
class ContrastRequirement:
    foreground: str
    background: str
    minimum_ratio: float
    high_contrast_ratio: float

    def ratio_for(self, theme: Theme) -> float:
        return self.high_contrast_ratio if theme.high_contrast else self.minimum_ratio


@dataclass(frozen=True)
class ContrastFailure:
    theme_name: str
    requirement: ContrastRequirement
    ratio: float
    minimum_ratio: float

    def describe(self) -> str:
        return (
            f"{self.theme_name}: {self.requirement.foreground} on "
            f"{self.requirement.background} is {self.ratio:.2f}:1, "
            f"below {self.minimum_ratio}:1"
        )


def linear_channel(channel: int) -> float:
    normalised_channel = channel / MAXIMUM_CHANNEL_VALUE
    if normalised_channel <= LINEAR_CHANNEL_THRESHOLD:
        return normalised_channel / LINEAR_CHANNEL_DIVISOR
    return float(((normalised_channel + GAMMA_OFFSET) / (1 + GAMMA_OFFSET)) ** GAMMA_EXPONENT)


def relative_luminance(colour: str) -> float:
    red, green, blue = (int(colour[start : start + 2], 16) for start in (1, 3, 5))
    return (
        RED_WEIGHT * linear_channel(red)
        + GREEN_WEIGHT * linear_channel(green)
        + BLUE_WEIGHT * linear_channel(blue)
    )


def contrast_ratio(first_colour: str, second_colour: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(first_colour), relative_luminance(second_colour)), reverse=True
    )
    return (lighter + LUMINANCE_FLARE) / (darker + LUMINANCE_FLARE)


def text_requirements(
    foregrounds: tuple[str, ...], backgrounds: tuple[str, ...]
) -> list[ContrastRequirement]:
    return [
        ContrastRequirement(
            foreground, background, TEXT_MINIMUM_RATIO, HIGH_CONTRAST_TEXT_MINIMUM_RATIO
        )
        for foreground in foregrounds
        for background in backgrounds
    ]


def interface_requirements(
    foregrounds: tuple[str, ...], backgrounds: tuple[str, ...]
) -> list[ContrastRequirement]:
    return [
        ContrastRequirement(
            foreground,
            background,
            LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO,
            HIGH_CONTRAST_INTERFACE_MINIMUM_RATIO,
        )
        for foreground in foregrounds
        for background in backgrounds
    ]


SURFACES = ("background", "surface", "raised_surface")
STATUS_COLOURS = (
    "high_severity",
    "medium_severity",
    "low_severity",
    "information",
    "success",
    "closed",
    "demonstration",
)
ENTITY_KIND_COLOURS = (
    "company",
    "person",
    "address",
    "establishment",
    "foreign_company",
    "identity",
)

CONTRAST_REQUIREMENTS = (
    *text_requirements(("text", "muted_text", "faint_text"), SURFACES),
    *text_requirements(("text_on_accent",), ("accent",)),
    *text_requirements(("accent",), ("surface", "soft_accent")),
    *text_requirements(("text", "muted_text"), ("soft_accent",)),
    *text_requirements(STATUS_COLOURS, ("surface",)),
    *text_requirements(("high_severity",), ("background",)),
    *text_requirements(("text_on_accent",), ("high_severity",)),
    *[
        requirement
        for status_colour in STATUS_COLOURS
        for requirement in text_requirements((status_colour,), (f"soft_{status_colour}",))
    ],
    *text_requirements(("text", "muted_text", "identity"), ("graph_background",)),
    *interface_requirements(("strong_border", "accent"), SURFACES),
    *interface_requirements((*ENTITY_KIND_COLOURS, "graph_edge"), ("graph_background",)),
    *interface_requirements(
        ("high_severity", "medium_severity", "low_severity"), ("graph_background",)
    ),
)
HIGH_CONTRAST_REQUIREMENTS = (*interface_requirements(("border",), SURFACES),)


def requirements_for(theme: Theme) -> tuple[ContrastRequirement, ...]:
    if theme.high_contrast:
        return (*CONTRAST_REQUIREMENTS, *HIGH_CONTRAST_REQUIREMENTS)
    return CONTRAST_REQUIREMENTS


def contrast_failures(theme: Theme) -> list[ContrastFailure]:
    failures = []
    for requirement in requirements_for(theme):
        ratio = contrast_ratio(
            getattr(theme.colours, requirement.foreground),
            getattr(theme.colours, requirement.background),
        )
        minimum_ratio = requirement.ratio_for(theme)
        if ratio < minimum_ratio:
            failures.append(ContrastFailure(theme.name, requirement, ratio, minimum_ratio))
    return failures
