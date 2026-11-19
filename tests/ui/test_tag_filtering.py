from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.tags import TagStore
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
ACME = "company:111111111"
DUPONT = "company:222222222"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.company("ACME PLOMBERIE", date(2021, 3, 1), identifier=ACME)
        builder.company("DUPONT SERVICES", date(2019, 4, 2), identifier=DUPONT)
        tags = TagStore(opened.connection)
        tags.add(ACME, "Client")
        tags.add(DUPONT, "réseau Dupont")
    return library


@pytest.fixture
def window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.show()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    return window


def shown_everywhere(window: MainWindow) -> tuple[list[str], list[str], list[str]]:
    page = window.investigation_page
    graph = sorted(page.graph_area.filter_chip.graph_filter.shown_identifiers(page.drawing))
    queue = [row.entity.identifier for row in page.queue_column.review_list.rows]
    table = sorted(page.details_panel.entities_tab.shown_identifiers())
    return graph, queue, table


def test_the_graph_menu_filters_every_view_by_tag(window: MainWindow) -> None:
    page = window.investigation_page
    chip = page.graph_area.filter_chip
    assert [action.text() for action in chip.tag_menu.actions()] == [
        "Tous les tags",
        "Client",
        "réseau Dupont",
    ]
    chip.tag_actions["client"].trigger()
    assert page.tag == "client"
    assert shown_everywhere(window) == ([ACME], [ACME], [ACME])
    assert page.details_panel.entities_tab.tag_box.currentText() == "Client"
    review_list = page.queue_column.review_list
    assert review_list.clear_filter_button is not None
    assert review_list.clear_filter_button.accessibleName() == "Tout afficher : Tag : Client"
    assert chip.text() == "Filtres · 1 entité masquée"


def test_the_entities_tab_filters_every_view_by_tag(window: MainWindow) -> None:
    page = window.investigation_page
    tab = page.details_panel.entities_tab
    tab.tag_box.setCurrentIndex(tab.tag_box.findData("réseau dupont"))
    assert page.tag == "réseau dupont"
    assert shown_everywhere(window) == ([DUPONT], [DUPONT], [DUPONT])
    assert page.graph_area.filter_chip.tag_actions["réseau dupont"].isChecked()


def test_the_review_column_shows_every_tag_again(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_by_tag("client")
    review_list = page.queue_column.review_list
    assert review_list.clear_filter_button is not None
    review_list.clear_filter_button.click()
    assert page.tag is None
    assert review_list.clear_filter_button is None
    assert shown_everywhere(window) == ([ACME, DUPONT], [ACME, DUPONT], [ACME, DUPONT])
    assert page.graph_area.filter_chip.tag_actions[None].isChecked()
    assert page.details_panel.entities_tab.tag_box.currentText() == "Tous les tags"


def test_showing_everything_in_the_graph_clears_the_tag(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_by_tag("client")
    page.graph_area.filter_chip.show_everything()
    assert page.tag is None
    assert page.queue_column.review_list.entity_filter is None


def test_a_tag_that_disappears_stops_filtering(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_by_tag("client")
    window.remove_tag(ACME, "client")
    assert page.tag is None
    assert page.graph_area.filter_chip.graph_filter.tag is None
    assert [action.text() for action in page.graph_area.filter_chip.tag_actions.values()] == [
        "Tous les tags",
        "réseau Dupont",
    ]


def test_the_filter_follows_new_tags(window: MainWindow) -> None:
    page = window.investigation_page
    page.filter_by_tag("client")
    window.add_tag(DUPONT, "client")
    assert page.tag == "client"
    assert shown_everywhere(window)[1] == [ACME, DUPONT]


def test_an_investigation_without_tags_disables_the_tag_choices(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    tmp_path: Path,
) -> None:
    library = InvestigationLibrary(tmp_path / "empty")
    library.create(INVESTIGATION_NAME, "")
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.open_investigation(INVESTIGATION_NAME)
    page = window.investigation_page
    assert not page.graph_area.filter_chip.tag_menu.isEnabled()
    assert page.graph_area.filter_chip.tag_menu.title() == "Tag : aucun dans l'enquête"
    assert not page.details_panel.entities_tab.tag_box.isEnabled()
