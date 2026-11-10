import sqlite3

import pytest
from PySide6.QtCore import QPoint, QPointF
from PySide6.QtGui import QColor, QFont, QImage
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Colours
from lacis.graph.drawing import (
    EdgeKind,
    GraphDrawing,
    GraphNode,
    NodeShape,
    graph_drawing,
)
from lacis.storage.entities import EntityKind
from lacis.ui.graph_view import (
    ARROW_LENGTH,
    CLOSED_FILL_OPACITY,
    GRAPH_ACCESSIBLE_NAME,
    GraphLegend,
    GraphView,
    NodeItem,
    arrow_head,
    boundary_point,
    edge_label_colour,
    edge_label_font,
    edge_pen,
    kind_colour,
    node_border,
    node_fill,
    shape_path,
    upright_angle,
)
from lacis.ui.investigation_columns import GraphArea

COLOURS = LIGHT_THEME.colours


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def scenario_drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection)


def node(kind: EntityKind, *, closed: bool = False, partial: bool = False) -> GraphNode:
    return GraphNode("company:100000001", kind, "ACME PLOMBERIE", closed, partial, 0.0, 0.0)


def shown_view(qtbot: QtBot, icon_factory: IconFactory, drawing: GraphDrawing) -> GraphView:
    view = GraphView(icon_factory.colours_provider)
    qtbot.addWidget(view)
    view.resize(900, 640)
    view.show()
    qtbot.waitExposed(view)
    view.show_drawing(drawing)
    return view


def pixel_at_node(view: GraphView, identifier: str) -> QColor:
    item = view.graph_scene.node_items[identifier]
    position: QPoint = view.mapFromScene(item.pos())
    image: QImage = view.viewport().grab().toImage()
    return image.pixelColor(position)


def same_colour(first: QColor, second: QColor, tolerance: int = 6) -> bool:
    return all(
        abs(left - right) <= tolerance
        for left, right in (
            (first.red(), second.red()),
            (first.green(), second.green()),
            (first.blue(), second.blue()),
        )
    )


@pytest.mark.parametrize(
    ("shape", "polygon_points"),
    [(NodeShape.DIAMOND, 5), (NodeShape.HEXAGON, 7)],
)
def test_polygon_shapes_have_their_corners(shape: NodeShape, polygon_points: int) -> None:
    path = shape_path(shape, 30.0)
    assert path.toFillPolygon().count() == polygon_points
    assert path.boundingRect().width() == pytest.approx(30.0)


def test_round_shapes_fill_their_square() -> None:
    for shape, size in ((NodeShape.CIRCLE, 30.0), (NodeShape.SMALL_CIRCLE, 14.0)):
        path = shape_path(shape, size)
        assert path.boundingRect().width() == pytest.approx(size)
        assert path.contains(QPointF(0, 0))
        assert not path.contains(QPointF(size / 2 - 1, size / 2 - 1))
    square = shape_path(NodeShape.ROUNDED_SQUARE, 34.0)
    assert square.contains(QPointF(16, 0))
    assert not square.contains(QPointF(16.8, 16.8))


def test_a_diamond_leaves_its_corners_empty() -> None:
    diamond = shape_path(NodeShape.DIAMOND, 30.0)
    assert diamond.contains(QPointF(0, 14))
    assert not diamond.contains(QPointF(10, 10))


@pytest.mark.parametrize("colours", [LIGHT_THEME.colours, DARK_THEME.colours])
def test_each_kind_takes_its_theme_colour(colours: Colours) -> None:
    assert kind_colour(colours, EntityKind.COMPANY) == QColor(colours.company)
    assert kind_colour(colours, EntityKind.PERSON) == QColor(colours.person)
    assert kind_colour(colours, EntityKind.ADDRESS) == QColor(colours.address)
    assert kind_colour(colours, EntityKind.ESTABLISHMENT) == QColor(colours.establishment)
    assert kind_colour(colours, EntityKind.FOREIGN_COMPANY) == QColor(colours.foreign_company)


def test_open_entities_are_filled_and_ringed_with_the_surface() -> None:
    assert node_fill(COLOURS, node(EntityKind.COMPANY)) == QColor(COLOURS.company)
    border = node_border(COLOURS, node(EntityKind.COMPANY))
    assert border.color() == QColor(COLOURS.surface)
    assert border.dashPattern() == []


def test_closed_entities_are_faded_with_a_dashed_border() -> None:
    closed = node(EntityKind.COMPANY, closed=True)
    assert node_fill(COLOURS, closed).alphaF() == pytest.approx(CLOSED_FILL_OPACITY, abs=0.01)
    border = node_border(COLOURS, closed)
    assert border.color() == QColor(COLOURS.company)
    assert border.dashPattern() != []


def test_partial_entities_have_a_faint_dashed_border() -> None:
    border = node_border(COLOURS, node(EntityKind.COMPANY, partial=True))
    assert border.color() == QColor(COLOURS.faint_text)
    assert border.dashPattern() != []


def test_the_view_draws_one_item_per_entity(
    qtbot: QtBot,
    icon_factory: IconFactory,
    scenario: PlumbersScenario,
    scenario_drawing: GraphDrawing,
) -> None:
    view = shown_view(qtbot, icon_factory, scenario_drawing)
    assert set(view.graph_scene.node_items) == {node.identifier for node in scenario_drawing.nodes}
    acme = view.graph_scene.node_items[scenario.acme]
    assert isinstance(acme, NodeItem)
    assert acme.pos() == QPointF(acme.node.x, acme.node.y)
    assert view.accessibleName() == GRAPH_ACCESSIBLE_NAME


@pytest.mark.parametrize("preference", [ThemePreference.LIGHT, ThemePreference.DARK])
def test_the_view_paints_entities_in_their_colours_in_both_themes(
    qtbot: QtBot,
    theme_controller: ThemeController,
    preference: ThemePreference,
    scenario: PlumbersScenario,
    scenario_drawing: GraphDrawing,
) -> None:
    theme_controller.set_preference(preference)
    colours = theme_controller.current_theme.colours
    icon_factory = IconFactory(lambda: theme_controller.current_theme.colours)
    view = shown_view(qtbot, icon_factory, scenario_drawing)
    expected = {
        scenario.acme: colours.company,
        scenario.jean: colours.person,
        scenario.address: colours.address,
        scenario.acme_office: colours.establishment,
        scenario.invest: colours.foreign_company,
    }
    for identifier, colour in expected.items():
        assert same_colour(pixel_at_node(view, identifier), QColor(colour))


def test_the_view_repaints_when_the_theme_changes(
    qtbot: QtBot,
    icon_factory: IconFactory,
    theme_controller: ThemeController,
    scenario: PlumbersScenario,
    scenario_drawing: GraphDrawing,
) -> None:
    theme_controller.set_preference(ThemePreference.LIGHT)
    view = shown_view(qtbot, icon_factory, scenario_drawing)
    theme_controller.set_preference(ThemePreference.DARK)
    qtbot.wait(10)
    assert same_colour(pixel_at_node(view, scenario.jean), QColor(DARK_THEME.colours.person))


def test_the_view_fits_the_whole_graph_without_enlarging_it(
    qtbot: QtBot, icon_factory: IconFactory, scenario_drawing: GraphDrawing
) -> None:
    view = shown_view(qtbot, icon_factory, scenario_drawing)
    assert 0 < view.transform().m11() <= 1.0
    for item in view.graph_scene.node_items.values():
        shown = view.mapFromScene(item.sceneBoundingRect()).boundingRect()
        assert view.viewport().rect().contains(shown)
    view.resize(400, 300)
    qtbot.wait(10)
    assert view.transform().m11() < 1.0
    view.show_drawing(GraphDrawing())
    assert view.transform().m11() == 1.0


def test_the_legend_names_each_kind(qtbot: QtBot, icon_factory: IconFactory) -> None:
    legend = GraphLegend(icon_factory.colours_provider)
    qtbot.addWidget(legend)
    assert legend.texts == ["Entreprise", "Personne", "Adresse", "Établissement", "Étranger"]
    assert legend.accessibleName() == "Légende du graphe"


def test_the_graph_area_shows_the_legend_once_there_is_a_graph(
    qtbot: QtBot,
    icon_factory: IconFactory,
    scenario: PlumbersScenario,
    scenario_drawing: GraphDrawing,
) -> None:
    area = GraphArea(icon_factory.colours_provider)
    qtbot.addWidget(area)
    area.resize(800, 600)
    area.show()
    area.show_drawing(scenario_drawing)
    assert area.legend.isVisible()
    assert not area.empty_label.isVisible()
    assert area.legend.geometry().bottom() == 600 - 12 - 1
    area.show_drawing(GraphDrawing())
    assert not area.legend.isVisible()
    assert area.empty_label.isVisible()


def test_mandates_are_drawn_in_the_person_colour_and_identities_dashed() -> None:
    directs = edge_pen(COLOURS, EdgeKind.DIRECTS)
    assert (directs.color(), directs.widthF(), directs.dashPattern()) == (
        QColor(COLOURS.person),
        1.6,
        [],
    )
    structure = edge_pen(COLOURS, EdgeKind.STRUCTURE)
    assert (structure.color(), structure.widthF(), structure.dashPattern()) == (
        QColor(COLOURS.graph_edge),
        1.0,
        [],
    )
    identity = edge_pen(COLOURS, EdgeKind.IDENTITY)
    assert identity.color() == QColor(COLOURS.identity)
    assert identity.widthF() == 2.0
    assert [length * identity.widthF() for length in identity.dashPattern()] == [6.0, 4.0]


def test_the_same_person_label_is_bold_in_the_identity_colour() -> None:
    assert edge_label_colour(COLOURS, EdgeKind.IDENTITY) == QColor(COLOURS.identity)
    assert edge_label_colour(COLOURS, EdgeKind.DIRECTS) == QColor(COLOURS.muted_text)
    assert edge_label_font(EdgeKind.IDENTITY).weight() == QFont.Weight.DemiBold
    assert edge_label_font(EdgeKind.DIRECTS).weight() == QFont.Weight.Normal


def test_edges_stop_at_the_border_of_each_shape() -> None:
    circle = shape_path(NodeShape.CIRCLE, 30.0)
    point = boundary_point(circle, QPointF(100, 100), QPointF(100, 300))
    assert point.x() == pytest.approx(100)
    assert point.y() == pytest.approx(115, abs=0.01)
    diamond = shape_path(NodeShape.DIAMOND, 30.0)
    corner = boundary_point(diamond, QPointF(0, 0), QPointF(200, 0))
    assert corner.x() == pytest.approx(15, abs=0.01)


def test_edge_labels_are_never_upside_down() -> None:
    assert upright_angle(QPointF(0, 0), QPointF(10, 0)) == pytest.approx(0)
    assert upright_angle(QPointF(10, 0), QPointF(0, 0)) == pytest.approx(0)
    assert upright_angle(QPointF(0, 0), QPointF(0, 10)) == pytest.approx(90)
    assert upright_angle(QPointF(0, 10), QPointF(0, 0)) == pytest.approx(90)
    assert upright_angle(QPointF(0, 0), QPointF(-10, -10)) == pytest.approx(45)


def test_an_arrow_points_at_its_tip() -> None:
    arrow = arrow_head(QPointF(0, 100), QPointF(0, 0))
    assert arrow.at(0) == QPointF(0, 100)
    assert arrow.at(1).y() == pytest.approx(100 - ARROW_LENGTH)
    assert arrow.at(1).x() == -arrow.at(2).x()
    assert arrow_head(QPointF(5, 5), QPointF(5, 5)).isEmpty()


def test_the_view_draws_the_links_under_the_entities(
    qtbot: QtBot,
    icon_factory: IconFactory,
    scenario: PlumbersScenario,
    scenario_drawing: GraphDrawing,
) -> None:
    view = shown_view(qtbot, icon_factory, scenario_drawing)
    edges = view.graph_scene.edge_items
    assert len(edges) == len(scenario_drawing.edges) == 9
    assert all(edge.zValue() < 0 for edge in edges)
    identity = next(edge for edge in edges if edge.edge.kind is EdgeKind.IDENTITY)
    assert identity.arrow.isEmpty()
    mandate = next(
        edge
        for edge in edges
        if {edge.edge.source, edge.edge.target}
        == {
            scenario.jean,
            scenario.dupont_services,
        }
    )
    company = view.graph_scene.node_items[scenario.dupont_services]
    assert not mandate.arrow.isEmpty()
    assert mandate.end.y() == pytest.approx(company.y() - 17, abs=0.01)
    assert mandate.boundingRect().contains(mandate.middle)
    view.grab()
