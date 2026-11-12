import sqlite3

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QAccessible, QMouseEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.filters import GraphFilter
from lacis.storage.entities import EntityKind
from lacis.ui import announcements
from lacis.ui.graph_controls import FilterChip, ZoomToolbar
from lacis.ui.graph_view import MAXIMUM_SCALE, MINIMUM_SCALE, MOVE_STEP, ZOOM_STEP, GraphView
from lacis.ui.investigation_columns import GraphArea

type Announcement = tuple[str, QAccessible.AnnouncementPoliteness]


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


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> list[Announcement]:
    messages: list[Announcement] = []

    def record(
        widget: QWidget,
        message: str,
        politeness: QAccessible.AnnouncementPoliteness = announcements.ASSERTIVE,
    ) -> None:
        messages.append((message, politeness))

    monkeypatch.setattr(announcements, "announce", record)
    return messages


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


def test_the_arrows_move_from_entity_to_linked_entity(
    view: GraphView, scenario: PlumbersScenario, heard: list[Announcement]
) -> None:
    press(view, Qt.Key.Key_Down)
    assert view.selected_identifier in {scenario.jean, scenario.jean_pierre}
    view.select(scenario.acme)
    press(view, Qt.Key.Key_Down)
    assert view.selected_identifier == scenario.acme_office
    press(view, Qt.Key.Key_Down)
    assert view.selected_identifier == scenario.address
    press(view, Qt.Key.Key_Down)
    assert view.selected_identifier == scenario.address
    assert heard[-1] == ("Aucune entité liée dans cette direction", announcements.POLITE)
    assert heard[-2][0].startswith("12 RUE DES LILAS 31000 TOULOUSE, adresse")


def test_escape_clears_the_selection(view: GraphView, scenario: PlumbersScenario) -> None:
    view.select(scenario.acme)
    press(view, Qt.Key.Key_Escape)
    assert view.selected_identifier is None
    press(view, Qt.Key.Key_Escape)
    assert view.selected_identifier is None


def test_alt_and_the_arrows_move_the_selected_entity(
    qtbot: QtBot, view: GraphView, scenario: PlumbersScenario
) -> None:
    with qtbot.assertNotEmitted(view.entities_moved, wait=10):
        press(view, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    view.select(scenario.holding)
    item = view.graph_scene.node_items[scenario.holding]
    start = item.point
    with qtbot.waitSignal(view.entities_moved) as moved:
        press(view, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
    assert item.point == (start[0] + MOVE_STEP, start[1])
    assert moved.args == [{scenario.holding: item.point}]
    press(view, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
    assert item.point == (start[0] + MOVE_STEP, start[1] - MOVE_STEP)


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


def test_filters_hide_entities_and_their_links(
    area: GraphArea, view: GraphView, scenario: PlumbersScenario
) -> None:
    chip = area.filter_chip
    assert chip.text() == "Filtres · tous les types"
    chip.kind_actions[EntityKind.ESTABLISHMENT].setChecked(False)
    assert chip.text() == "Filtres · 2 entités masquées"
    assert chip.accessibleDescription() == "2 entités masquées"
    items = view.graph_scene.node_items
    assert not items[scenario.acme_office].isVisible()
    assert items[scenario.acme].isVisible()
    hidden_edges = [edge for edge in view.graph_scene.edge_items if not edge.isVisible()]
    assert len(hidden_edges) == 4
    assert view.accessibleDescription().endswith(", 2 entités masquées")


def test_flagged_entities_only_keeps_the_ringed_ones(
    area: GraphArea, view: GraphView, scenario: PlumbersScenario
) -> None:
    view.select(scenario.holding)
    area.filter_chip.flagged_action.setChecked(True)
    shown = {
        identifier for identifier, item in view.graph_scene.node_items.items() if item.isVisible()
    }
    assert shown == {scenario.acme, scenario.dupont_services, scenario.jean, scenario.jean_pierre}
    assert view.selected_identifier is None
    assert area.filter_chip.text() == "Filtres · 5 entités masquées"
    view.select(scenario.acme)
    press(view, Qt.Key.Key_Down)
    assert view.selected_identifier == scenario.acme


def test_show_everything_resets_the_filters(area: GraphArea, view: GraphView) -> None:
    chip = area.filter_chip
    assert not chip.show_everything_action.isEnabled()
    chip.kind_actions[EntityKind.PERSON].setChecked(False)
    chip.flagged_action.setChecked(True)
    assert chip.show_everything_action.isEnabled()
    chip.show_everything_action.trigger()
    assert chip.graph_filter == GraphFilter()
    assert all(action.isChecked() for action in chip.kind_actions.values())
    assert not chip.flagged_action.isChecked()
    assert all(item.isVisible() for item in view.graph_scene.node_items.values())
    assert chip.text() == "Filtres · tous les types"


def test_the_filter_choices_count_the_entities(area: GraphArea) -> None:
    chip = area.filter_chip
    assert [action.text() for action in chip.kind_actions.values()] == [
        "Entreprises (3)",
        "Personnes (2)",
        "Adresses (1)",
        "Établissements (2)",
        "Entreprises étrangères (1)",
    ]
    assert chip.flagged_action.text() == "Entités signalées seulement (4)"


def test_a_filter_keeps_applying_to_a_redrawn_graph(
    area: GraphArea, view: GraphView, drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    area.filter_chip.kind_actions[EntityKind.ADDRESS].setChecked(False)
    area.show_drawing(drawing)
    assert not view.graph_scene.node_items[scenario.address].isVisible()
    assert area.filter_chip.text() == "Filtres · 1 entité masquée"


def test_the_layout_button_asks_for_a_new_layout(qtbot: QtBot, area: GraphArea) -> None:
    with qtbot.waitSignal(area.layout_requested):
        area.zoom_toolbar.layout_button.click()


def test_the_controls_show_only_with_a_graph(area: GraphArea) -> None:
    assert area.filter_chip.isVisible()
    assert area.zoom_toolbar.isVisible()
    assert area.legend.isVisible()
    area.show_drawing(GraphDrawing())
    assert not area.filter_chip.isVisible()
    assert not area.zoom_toolbar.isVisible()
    assert area.empty_label.isVisible()


def test_every_control_is_reachable_with_the_keyboard(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    toolbar = ZoomToolbar(icon_factory)
    chip = FilterChip(icon_factory)
    qtbot.addWidget(toolbar)
    qtbot.addWidget(chip)
    controls: list[QWidget] = [*toolbar.buttons, chip]
    assert all(control.focusPolicy() & Qt.FocusPolicy.TabFocus for control in controls)
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
    assert chip.accessibleName() == "Filtres du graphe"


def test_the_graph_takes_the_keyboard_focus(view: GraphView) -> None:
    assert view.focusPolicy() & Qt.FocusPolicy.TabFocus
