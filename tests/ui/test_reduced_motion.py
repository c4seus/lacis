from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, QSettings
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from graph_scenario import plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.design.motion import REDUCED_MOTION_SETTING_KEY
from lacis.design.theme_controller import ThemeController
from lacis.review import RunningCollection
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui.collection_progress import CollectionProgressPanel
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
EXPANSION = RunningCollection("company:100000001", "Extension de ACME PLOMBERIE")
MOVED_BY = QPointF(120, -80)


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        plumbers_scenario(InvestigationBuilder(opened.connection))
    return library


@pytest.fixture(params=[False, True], ids=["animations", "reduced motion"])
def reduced(request: pytest.FixtureRequest) -> bool:
    return bool(request.param)


@pytest.fixture
def main_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    reduced: bool,
) -> Iterator[MainWindow]:
    main_window = MainWindow(settings, theme_controller, library=library)
    qtbot.addWidget(main_window)
    main_window.resize(1440, 900)
    main_window.show()
    qtbot.waitExposed(main_window)
    main_window.main_menu_bar.reduced_motion_action.setChecked(reduced)
    main_window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: main_window.layout_job is None)
    yield main_window
    main_window.motion.stop()


def test_the_view_menu_reduces_motion_and_remembers_it(
    main_window: MainWindow, settings: QSettings, reduced: bool
) -> None:
    action = main_window.main_menu_bar.reduced_motion_action
    assert action.isCheckable()
    assert action.isChecked() is reduced
    assert main_window.motion.reduced is reduced
    assert settings.value(REDUCED_MOTION_SETTING_KEY, False, type=bool) is reduced


def test_zooming_and_fitting_take_effect_at_once(main_window: MainWindow) -> None:
    view = main_window.investigation_page.graph_view
    menu_bar = main_window.main_menu_bar
    fitted = view.zoom
    menu_bar.zoom_in_action.trigger()
    zoomed = view.zoom
    assert zoomed > fitted
    QApplication.processEvents()
    assert view.zoom == zoomed
    menu_bar.fit_action.trigger()
    assert view.zoom == pytest.approx(fitted)
    QApplication.processEvents()
    assert view.zoom == pytest.approx(fitted)


def test_a_new_layout_puts_the_entities_in_place_at_once(main_window: MainWindow) -> None:
    view = main_window.investigation_page.graph_view
    drawing = view.drawing
    moved = replace(
        drawing,
        nodes=tuple(
            replace(node, x=node.x + MOVED_BY.x(), y=node.y + MOVED_BY.y())
            for node in drawing.nodes
        ),
    )
    view.show_drawing(moved)
    for node in moved.nodes:
        assert view.graph_scene.node_items[node.identifier].pos() == QPointF(node.x, node.y)


def test_the_progress_of_a_collection_stops_moving_with_reduced_motion(
    main_window: MainWindow, reduced: bool
) -> None:
    panel = main_window.investigation_page.graph_area.progress_panel
    panel.show_collections((EXPANSION,))
    row = panel.rows[EXPANSION.identifier]
    assert row.bar.isVisible() is not reduced
    assert row.status_label.isVisible()
    main_window.main_menu_bar.reduced_motion_action.setChecked(not reduced)
    assert row.bar.isVisible() is reduced


def test_new_rows_follow_the_motion_of_the_panel(qtbot: QtBot) -> None:
    panel = CollectionProgressPanel()
    qtbot.addWidget(panel)
    panel.reduce_motion(True)
    panel.show_collections((EXPANSION,))
    panel.show()
    assert not panel.rows[EXPANSION.identifier].bar.isVisible()
    panel.reduce_motion(False)
    assert panel.rows[EXPANSION.identifier].bar.isVisible()
