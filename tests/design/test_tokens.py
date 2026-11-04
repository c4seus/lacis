import re
from dataclasses import fields

import pytest

from lacis.design.tokens import DARK_THEME, LIGHT_THEME, THEMES, Colours, Theme

HEXADECIMAL_COLOUR = re.compile(r"#[0-9a-f]{6}")


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_colour_is_a_lowercase_hexadecimal_colour(theme: Theme) -> None:
    for colour_field in fields(Colours):
        assert HEXADECIMAL_COLOUR.fullmatch(getattr(theme.colours, colour_field.name))


@pytest.mark.parametrize(
    ("theme", "background", "surface", "text", "accent"),
    [
        (LIGHT_THEME, "#f4f5f7", "#ffffff", "#171a1f", "#2f55d4"),
        (DARK_THEME, "#0f1115", "#171a20", "#e8eaee", "#7c9cff"),
    ],
    ids=["light", "dark"],
)
def test_the_main_colours_match_the_design_target(
    theme: Theme, background: str, surface: str, text: str, accent: str
) -> None:
    assert theme.colours.background == background
    assert theme.colours.surface == surface
    assert theme.colours.text == text
    assert theme.colours.accent == accent


def test_entity_kinds_have_distinct_colours_in_each_theme() -> None:
    for theme in THEMES:
        kind_colours = [
            theme.colours.company,
            theme.colours.person,
            theme.colours.address,
            theme.colours.establishment,
            theme.colours.foreign_company,
            theme.colours.identity,
        ]
        assert len(set(kind_colours)) == len(kind_colours)


def test_both_themes_share_spacing_radii_and_typography() -> None:
    assert LIGHT_THEME.spacing == DARK_THEME.spacing
    assert LIGHT_THEME.radii == DARK_THEME.radii
    assert LIGHT_THEME.font_sizes == DARK_THEME.font_sizes
    assert LIGHT_THEME.font_weights == DARK_THEME.font_weights


def test_spacing_and_font_sizes_grow_with_their_step() -> None:
    spacing_values = [
        getattr(LIGHT_THEME.spacing, field.name) for field in fields(LIGHT_THEME.spacing)
    ]
    font_size_values = [
        getattr(LIGHT_THEME.font_sizes, field.name) for field in fields(LIGHT_THEME.font_sizes)
    ]
    assert spacing_values == sorted(spacing_values)
    assert font_size_values == sorted(font_size_values)
