from dataclasses import fields, replace

import pytest

from lacis.design.contrast import (
    CONTRAST_REQUIREMENTS,
    HIGH_CONTRAST_INTERFACE_MINIMUM_RATIO,
    HIGH_CONTRAST_REQUIREMENTS,
    HIGH_CONTRAST_TEXT_MINIMUM_RATIO,
    LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO,
    TEXT_MINIMUM_RATIO,
    ContrastFailure,
    ContrastRequirement,
    contrast_failures,
    contrast_ratio,
    relative_luminance,
    requirements_for,
)
from lacis.design.tokens import (
    HIGH_CONTRAST_DARK_THEME,
    HIGH_CONTRAST_LIGHT_THEME,
    LIGHT_THEME,
    THEMES,
    Colours,
    Theme,
)

HIGH_CONTRAST_THEMES = (HIGH_CONTRAST_LIGHT_THEME, HIGH_CONTRAST_DARK_THEME)


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_text_and_interface_pair_meets_wcag_aa(theme: Theme) -> None:
    failures = contrast_failures(theme)
    assert not failures, "\n".join(failure.describe() for failure in failures)


def test_the_requirements_name_existing_colours() -> None:
    colour_names = {colour_field.name for colour_field in fields(Colours)}
    for requirement in (*CONTRAST_REQUIREMENTS, *HIGH_CONTRAST_REQUIREMENTS):
        assert requirement.foreground in colour_names
        assert requirement.background in colour_names


def test_black_on_white_has_the_maximum_ratio() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21)
    assert contrast_ratio("#ffffff", "#000000") == pytest.approx(21)


def test_luminance_goes_from_black_to_white() -> None:
    assert relative_luminance("#000000") == 0
    assert relative_luminance("#ffffff") == pytest.approx(1)


def test_a_grey_just_below_four_and_a_half_fails_for_text_but_not_for_interface() -> None:
    ratio = contrast_ratio("#777777", "#ffffff")
    assert LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO < ratio < TEXT_MINIMUM_RATIO


def test_a_text_pair_below_four_and_a_half_is_reported() -> None:
    faded_theme = replace(LIGHT_THEME, colours=replace(LIGHT_THEME.colours, muted_text="#999999"))
    failing_pairs = {
        (failure.requirement.foreground, failure.requirement.background)
        for failure in contrast_failures(faded_theme)
    }
    assert ("muted_text", "surface") in failing_pairs


def test_an_interface_pair_below_three_is_reported() -> None:
    faded_theme = replace(
        LIGHT_THEME, colours=replace(LIGHT_THEME.colours, strong_border="#d0d0d0")
    )
    failing_pairs = {
        (failure.requirement.foreground, failure.requirement.background)
        for failure in contrast_failures(faded_theme)
    }
    assert ("strong_border", "surface") in failing_pairs


def test_a_failure_describes_the_pair_and_its_ratio() -> None:
    requirement = ContrastRequirement(
        "muted_text", "surface", TEXT_MINIMUM_RATIO, HIGH_CONTRAST_TEXT_MINIMUM_RATIO
    )
    failure = ContrastFailure("light", requirement, 2.85, TEXT_MINIMUM_RATIO)
    assert failure.describe() == "light: muted_text on surface is 2.85:1, below 4.5:1"


@pytest.mark.parametrize("theme", HIGH_CONTRAST_THEMES, ids=lambda theme: theme.name)
def test_high_contrast_reaches_seven_for_text_and_four_and_a_half_for_interface(
    theme: Theme,
) -> None:
    requirements = requirements_for(theme)
    assert set(requirements) > set(CONTRAST_REQUIREMENTS)
    for requirement in requirements:
        ratio = contrast_ratio(
            getattr(theme.colours, requirement.foreground),
            getattr(theme.colours, requirement.background),
        )
        assert ratio >= requirement.ratio_for(theme)
        assert requirement.ratio_for(theme) in {
            HIGH_CONTRAST_TEXT_MINIMUM_RATIO,
            HIGH_CONTRAST_INTERFACE_MINIMUM_RATIO,
        }


def test_borders_only_count_as_interface_in_high_contrast() -> None:
    assert requirements_for(LIGHT_THEME) == CONTRAST_REQUIREMENTS
    assert {requirement.foreground for requirement in HIGH_CONTRAST_REQUIREMENTS} == {"border"}


def test_a_text_pair_that_passes_aa_fails_in_high_contrast() -> None:
    softened = replace(
        HIGH_CONTRAST_LIGHT_THEME,
        colours=replace(HIGH_CONTRAST_LIGHT_THEME.colours, muted_text="#707070"),
    )
    assert contrast_ratio("#707070", "#ffffff") > TEXT_MINIMUM_RATIO
    failures = contrast_failures(softened)
    assert ("muted_text", "surface") in {
        (failure.requirement.foreground, failure.requirement.background) for failure in failures
    }
    assert {failure.minimum_ratio for failure in failures} == {HIGH_CONTRAST_TEXT_MINIMUM_RATIO}
