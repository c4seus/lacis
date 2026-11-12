import sqlite3

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.ui.graph_controls import ZoomToolbar
from lacis.ui.graph_view import MAXIMUM_SCALE, MINIMUM_SCALE, ZOOM_STEP, GraphView
from lacis.ui.investigation_columns import GraphArea


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


@pytest.fixture
def area(qtbot: QtBot, icon_factory: IconFactory, drawing: GraphDrawing) -> GraphArea:
    area = GraphArea(icon_factory)
    qtbot.addWidget(area)
    area.resize(900, 640)
    area.show()
    qtbot.waitExposed(area)
    area.show_drawing(drawing)
    return area


@pytest.fixture
def view(area: GraphArea) -> GraphView:
    return area.graph_view


def press(view: GraphView, key: Qt.Key, modifier: Qt.KeyboardModifier | None = None) -> None:
    QTest.keyClick(view, key, modifier or Qt.KeyboardModifier.NoModifier)


def scroll_position(view: GraphView) -> tuple[int, int]:
    return (view.horizontalScrollBar().value(), view.verticalScrollBar().value())


def send_mouse(view: GraphView, kind: QEvent.Type, position: QPoint, held: bool) -> None:
    event = QMouseEvent(
        kind,
        QPointF(position),
        QPointF(view.viewport().mapToGlobal(position)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton if held else Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(view.viewport(), event)


def wheel(view: GraphView, steps: int) -> None:
    position = QPointF(view.viewport().rect().center())
    event = QWheelEvent(
        position,
        QPointF(view.viewport().mapToGlobal(position.toPoint())),
        QPoint(),
        QPoint(0, 120 * steps),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(view.viewport(), event)


def test_the_buttons_zoom_in_zoom_out_and_fit(area: GraphArea, view: GraphView) -> None:
    fitted = view.zoom
    area.zoom_toolbar.zoom_in_button.click()
    assert view.zoom == pytest.approx(fitted * ZOOM_STEP)
    assert not view.follows_fit
    area.zoom_toolbar.zoom_out_button.click()
    area.zoom_toolbar.zoom_out_button.click()
    assert view.zoom == pytest.approx(fitted / ZOOM_STEP)
    area.zoom_toolbar.fit_button.click()
    assert view.zoom == pytest.approx(fitted)
    assert view.follows_fit


def test_the_zoom_stays_within_its_limits(view: GraphView) -> None:
    for _ in range(40):
        view.zoom_in()
    assert view.zoom == pytest.approx(MAXIMUM_SCALE)
    for _ in range(60):
        view.zoom_out()
    assert view.zoom == pytest.approx(MINIMUM_SCALE)


def test_the_mouse_wheel_zooms(view: GraphView) -> None:
    fitted = view.zoom
    wheel(view, 1)
    assert view.zoom == pytest.approx(fitted * ZOOM_STEP)
    wheel(view, -2)
    assert view.zoom == pytest.approx(fitted / ZOOM_STEP)
    wheel(view, 0)
    assert view.zoom == pytest.approx(fitted / ZOOM_STEP)


def test_the_keys_zoom_like_the_buttons(view: GraphView) -> None:
    fitted = view.zoom
    press(view, Qt.Key.Key_Plus)
    assert view.zoom == pytest.approx(fitted * ZOOM_STEP)
    press(view, Qt.Key.Key_Equal)
    press(view, Qt.Key.Key_Minus)
    assert view.zoom == pytest.approx(fitted * ZOOM_STEP)
    press(view, Qt.Key.Key_0)
    assert view.zoom == pytest.approx(fitted)


def test_dragging_the_background_pans_the_graph(view: GraphView) -> None:
    before = scroll_position(view)
    start = QPoint(5, 5)
    send_mouse(view, QEvent.Type.MouseButtonPress, start, held=True)
    send_mouse(view, QEvent.Type.MouseMove, QPoint(45, 35), held=True)
    send_mouse(view, QEvent.Type.MouseMove, QPoint(85, 65), held=True)
    send_mouse(view, QEvent.Type.MouseButtonRelease, QPoint(85, 65), held=False)
    after = scroll_position(view)
    assert after[0] < before[0]
    assert after[1] < before[1]
    assert not view.follows_fit


def test_shift_and_the_arrows_pan_the_graph(view: GraphView) -> None:
    before = scroll_position(view)
    press(view, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    press(view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    after = scroll_position(view)
    assert after[0] > before[0]
    assert after[1] > before[1]
    assert view.selected_identifier is None


def test_other_keys_keep_their_usual_meaning(view: GraphView, scenario: PlumbersScenario) -> None:
    view.select(scenario.acme)
    press(view, Qt.Key.Key_A)
    assert view.selected_identifier == scenario.acme


def test_a_redrawn_graph_keeps_the_zoom_chosen_by_the_investigator(
    view: GraphView, drawing: GraphDrawing
) -> None:
    view.zoom_in()
    zoomed = view.zoom
    view.show_drawing(drawing)
    assert view.zoom == pytest.approx(zoomed)
    view.fit()
    view.show_drawing(drawing)
    assert view.follows_fit


def test_the_layout_button_asks_for_a_new_layout(qtbot: QtBot, area: GraphArea) -> None:
    with qtbot.waitSignal(area.layout_requested):
        area.zoom_toolbar.layout_button.click()


def test_the_controls_show_only_with_a_graph(area: GraphArea) -> None:
    assert area.zoom_toolbar.isVisible()
    assert area.legend.isVisible()
    area.show_drawing(GraphDrawing())
    assert not area.zoom_toolbar.isVisible()
    assert area.empty_label.isVisible()


def test_every_control_is_reachable_with_the_keyboard(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    toolbar = ZoomToolbar(icon_factory)
    qtbot.addWidget(toolbar)
    assert all(button.focusPolicy() & Qt.FocusPolicy.TabFocus for button in toolbar.buttons)
    assert [button.toolTip() for button in toolbar.buttons] == [
        "Zoom avant (Ctrl++)",
        "Zoom arrière (Ctrl+-)",
        "Ajuster à la fenêtre (Ctrl+0)",
        "Réorganiser le graphe (Ctrl+Maj+R)",
    ]
    assert [button.accessibleName() for button in toolbar.buttons] == [
        "Zoom avant",
        "Zoom arrière",
        "Ajuster à la fenêtre",
        "Réorganiser le graphe",
    ]


def test_the_graph_takes_the_keyboard_focus(view: GraphView) -> None:
    assert view.focusPolicy() & Qt.FocusPolicy.TabFocus
