import pytest
from PySide6.QtCore import Qt

from colour_vision import ColourVision, simulated
from lacis.design.contrast import LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO, contrast_ratio
from lacis.design.tokens import THEMES, Theme
from lacis.graph.drawing import SHAPES, EdgeKind, GraphEdge
from lacis.signals.signal import Severity
from lacis.ui.graph_view import RING_COUNTS, edge_pen, ring_pen

LINE_COLOURS = ("graph_edge", "high_severity", "medium_severity", "low_severity", "identity")
SHAPE_COLOURS = ("company", "person", "address", "establishment", "foreign_company")
LARGE_SHAPE_MINIMUM_RATIO = 2.5


def seen_contrast(theme: Theme, colour: str, vision: ColourVision) -> float:
    colours = theme.colours
    return contrast_ratio(
        simulated(getattr(colours, colour), vision), simulated(colours.graph_background, vision)
    )


def test_the_simulation_keeps_greys_and_moves_reds() -> None:
    for vision in ColourVision:
        assert simulated("#ffffff", vision) == "#ffffff"
        assert simulated("#000000", vision) == "#000000"
        assert simulated("#808080", vision) == "#808080"
    assert simulated("#ff0000", ColourVision.PROTANOPIA) != "#ff0000"


@pytest.mark.parametrize("vision", list(ColourVision), ids=str)
@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_the_lines_of_the_graph_stay_visible_without_full_colour_vision(
    theme: Theme, vision: ColourVision
) -> None:
    for colour in LINE_COLOURS:
        assert seen_contrast(theme, colour, vision) >= LARGE_TEXT_AND_INTERFACE_MINIMUM_RATIO


@pytest.mark.parametrize("vision", list(ColourVision), ids=str)
@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_the_entities_of_the_graph_stay_visible_without_full_colour_vision(
    theme: Theme, vision: ColourVision
) -> None:
    for colour in SHAPE_COLOURS:
        assert seen_contrast(theme, colour, vision) >= LARGE_SHAPE_MINIMUM_RATIO


def test_each_kind_of_entity_has_its_own_shape() -> None:
    assert len(set(SHAPES.values())) == len(SHAPES)


def test_each_severity_is_told_by_its_ring_and_not_only_by_its_colour() -> None:
    colours = THEMES[0].colours
    signatures = {
        (RING_COUNTS[severity], ring_pen(colours, severity).style()) for severity in Severity
    }
    assert len(signatures) == len(Severity)
    assert ring_pen(colours, Severity.LOW).style() == Qt.PenStyle.CustomDashLine


def test_each_kind_of_link_is_told_by_its_line_and_not_only_by_its_colour() -> None:
    colours = THEMES[0].colours
    edges = [GraphEdge(kind.value, kind, "source", "target", "") for kind in EdgeKind]
    signatures = {
        (
            edge_pen(colours, edge.kind).widthF(),
            edge_pen(colours, edge.kind).style(),
            edge.has_arrow,
        )
        for edge in edges
    }
    assert len(signatures) == len(EdgeKind)
