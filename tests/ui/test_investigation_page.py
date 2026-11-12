from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.storage.entities import EntityKind
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary
from lacis.storage.notices import NoticeFamily
from lacis.storage.positions import Position, PositionStore
from lacis.ui.entity_sheet import EntitySheet
from lacis.ui.investigation_page import (
    COLUMNS_SETTING,
    Counter,
    InvestigationPage,
    noun_for,
)
from lacis.ui.main_window import MainWindow
from lacis.ui.raw_response_dialog import RawResponseDialog
from lacis.ui.review_queue import QueueRow

INVESTIGATION_NAME = "faux-plombiers-31"
QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
BURST_DATES = (date(2025, 1, 10), date(2025, 2, 1), date(2025, 3, 15))


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, QUESTION)
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        jean = builder.person("Jean", "DUPONT")
        jean_pierre = builder.person("Jean Pierre", "DUPONT")
        for position, day in enumerate(BURST_DATES):
            builder.mandate(jean, builder.company(f"SOCIETE {position}", day))
        builder.same_person(jean, jean_pierre)
    return library


@pytest.fixture
def main_window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    main_window = MainWindow(settings, theme_controller, library=library)
    qtbot.addWidget(main_window)
    main_window.resize(1440, 900)
    main_window.show()
    main_window.activateWindow()
    qtbot.waitUntil(main_window.isActiveWindow)
    main_window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: main_window.layout_job is None)
    return main_window


def counter_texts(page: InvestigationPage) -> list[str]:
    return [counter.text() for counter in page.header.all_counters()]


def test_the_header_shows_the_name_the_question_and_the_counters(
    main_window: MainWindow,
) -> None:
    header = main_window.investigation_page.header
    assert header.name_label.text() == INVESTIGATION_NAME
    assert header.question_label.text() == QUESTION
    assert counter_texts(main_window.investigation_page) == [
        "5 entités",
        "3 liens",
        "1 homonyme confirmé",
        "1 signal",
    ]
    assert header.signal_counter.number_label.property("tone") == "counter-alert"
    assert header.entity_counter.number_label.property("tone") == "counter"
    assert header.counters.accessibleName() == "Compteurs de l'enquête"
    assert header.counters.accessibleDescription() == (
        "5 entités, 3 liens, 1 homonyme confirmé, 1 signal"
    )


def test_the_header_sits_above_the_screen(main_window: MainWindow) -> None:
    page = main_window.investigation_page
    assert page.header.geometry().top() == 0
    assert page.header.width() == page.width()


def test_counters_update_after_each_change_of_the_investigation(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.person("Lucie", "BERNARD")
    main_window.refresh_overview()
    assert counter_texts(main_window.investigation_page)[0] == "6 entités"


def test_an_invalid_signal_configuration_leaves_the_signal_count_unknown(
    main_window: MainWindow, isolated_configuration_directory: Path
) -> None:
    isolated_configuration_directory.mkdir(parents=True)
    (isolated_configuration_directory / "signals.toml").write_text("[rules.inconnue]\n")
    main_window.refresh_overview()
    counter = main_window.investigation_page.header.signal_counter
    assert counter.text() == "? signaux"
    assert counter.number_label.property("tone") == "counter"
    assert counter.toolTip().startswith("Le fichier ")


def test_an_investigation_removed_meanwhile_is_notified(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    library.rename(INVESTIGATION_NAME, "ailleurs")
    main_window.refresh_overview()
    [notification] = main_window.notification_area.notifications
    assert notification.message == f"L'enquête « {INVESTIGATION_NAME} » est introuvable."


def test_an_unreadable_investigation_is_notified(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    (library.directory_of(INVESTIGATION_NAME) / DATABASE_FILE_NAME).write_bytes(
        b"pas une base SQLite"
    )
    main_window.refresh_overview()
    [notification] = main_window.notification_area.notifications
    assert notification.message == "La base de données de cette enquête est illisible."


def test_the_search_field_has_the_focus_once_opened(main_window: MainWindow) -> None:
    assert main_window.header_bar.search_field.hasFocus()


def test_the_breadcrumb_leads_back_to_the_investigations(main_window: MainWindow) -> None:
    main_window.header_bar.breadcrumb.links[0].click()
    assert main_window.pages.currentWidget() is main_window.home_screen
    main_window.follow_breadcrumb(1)
    assert main_window.pages.currentWidget() is main_window.home_screen


def test_the_file_menu_closes_the_investigation(main_window: MainWindow) -> None:
    close_action = main_window.main_menu_bar.close_investigation_action
    assert close_action.isEnabled()
    close_action.trigger()
    assert main_window.current_investigation is None
    assert main_window.pages.currentWidget() is main_window.home_screen
    assert not close_action.isEnabled()
    main_window.refresh_overview()


def test_counts_are_singular_up_to_one(qtbot: QtBot) -> None:
    counter = Counter("lien", "liens")
    qtbot.addWidget(counter)
    counter.show_count(0)
    assert counter.text() == "0 lien"
    counter.show_count(2)
    assert counter.text() == "2 liens"
    assert noun_for(None, "signal", "signaux") == "signaux"


def column_widths(page: InvestigationPage) -> list[int]:
    return page.columns.sizes()


def test_the_screen_has_the_queue_the_graph_and_the_details_in_columns(
    main_window: MainWindow,
) -> None:
    page = main_window.investigation_page
    assert [page.columns.widget(index) for index in range(page.columns.count())] == [
        page.queue_column,
        page.graph_area,
        page.details_panel,
    ]
    assert page.columns.geometry().top() == page.header.geometry().bottom() + 1
    assert page.queue_column.summary_label.text() == "1 signal, 0 homonyme, 5 pistes"


def test_the_columns_match_the_design_target_at_1440_by_900(main_window: MainWindow) -> None:
    queue, graph, details = column_widths(main_window.investigation_page)
    assert queue == pytest.approx(320, abs=20)
    assert details == pytest.approx(420, abs=30)
    assert graph > queue + details - 100


def test_the_columns_stay_usable_at_1024_by_640(qtbot: QtBot, main_window: MainWindow) -> None:
    main_window.resize(1024, 640)
    qtbot.waitUntil(lambda: main_window.width() == 1024)
    page = main_window.investigation_page
    for column in (page.queue_column, page.graph_area, page.details_panel):
        assert column.isVisible()
        assert column.width() >= column.minimumWidth()
    assert sum(column_widths(page)) <= page.width()


def test_resized_columns_are_remembered_between_sessions(
    qtbot: QtBot, main_window: MainWindow, settings: QSettings, icon_factory: IconFactory
) -> None:
    page = main_window.investigation_page
    page.columns.setSizes([400, 600, 440])
    page.columns.splitterMoved.emit(400, 1)
    remembered = page.columns.sizes()
    next_page = InvestigationPage(settings, icon_factory)
    qtbot.addWidget(next_page)
    next_page.resize(page.size())
    next_page.show()
    assert next_page.columns.sizes() == remembered


def test_an_unreadable_column_state_falls_back_to_the_default_widths(
    qtbot: QtBot, settings: QSettings, icon_factory: IconFactory
) -> None:
    pages = []
    for stored in (None, b"pas un etat"):
        settings.setValue(COLUMNS_SETTING, stored)
        page = InvestigationPage(settings, icon_factory)
        qtbot.addWidget(page)
        page.resize(1440, 760)
        page.show()
        pages.append(page)
    default, fallback = pages
    assert fallback.columns.sizes() == default.columns.sizes()
    assert default.columns.sizes()[0] == pytest.approx(320, abs=20)


def test_the_queue_column_collapses_into_a_rail_and_expands_again(
    main_window: MainWindow,
) -> None:
    page = main_window.investigation_page
    assert page.queue_column.isVisible()
    assert not page.queue_rail.isVisible()
    page.queue_column.collapse_button.click()
    assert not page.queue_column.isVisible()
    assert page.queue_rail.isVisible()
    assert page.queue_rail.count_label.text() == "1"
    assert page.queue_rail.expand_button.hasFocus()
    assert page.graph_area.width() > 900
    page.queue_rail.expand_button.click()
    assert page.queue_column.isVisible()
    assert not page.queue_rail.isVisible()
    assert page.queue_column.collapse_button.hasFocus()
    assert page.queue_column.width() == pytest.approx(320, abs=20)


def test_collapsing_twice_or_expanding_twice_changes_nothing(main_window: MainWindow) -> None:
    page = main_window.investigation_page
    page.expand_queue()
    assert page.queue_column.isVisible()
    page.collapse_queue()
    page.collapse_queue()
    assert page.is_queue_collapsed()


def test_the_view_menu_collapses_and_expands_the_queue(main_window: MainWindow) -> None:
    action = main_window.main_menu_bar.queue_action
    assert action.isEnabled()
    assert action.isChecked()
    assert action.shortcut() == QKeySequence("Ctrl+1")
    action.trigger()
    assert main_window.investigation_page.is_queue_collapsed()
    main_window.investigation_page.queue_rail.expand_button.click()
    assert action.isChecked()
    main_window.show_home()
    assert not action.isEnabled()


def test_a_collapsed_queue_is_remembered_between_sessions(
    qtbot: QtBot, main_window: MainWindow, settings: QSettings, icon_factory: IconFactory
) -> None:
    main_window.investigation_page.collapse_queue()
    next_page = InvestigationPage(settings, icon_factory)
    qtbot.addWidget(next_page)
    next_page.show()
    assert next_page.is_queue_collapsed()
    assert next_page.queue_rail.isVisible()


def test_the_collapsed_screen_stays_usable_at_1024_by_640(
    qtbot: QtBot, main_window: MainWindow
) -> None:
    main_window.resize(1024, 640)
    qtbot.waitUntil(lambda: main_window.width() == 1024)
    page = main_window.investigation_page
    page.collapse_queue()
    assert page.graph_area.width() >= page.graph_area.minimumWidth()
    assert page.details_panel.width() >= page.details_panel.minimumWidth()


def test_the_graph_of_the_investigation_is_drawn_and_selectable(main_window: MainWindow) -> None:
    page = main_window.investigation_page
    scene = page.graph_view.graph_scene
    assert len(scene.node_items) == 5
    assert page.graph_area.legend.isVisible()
    jean = next(
        identifier
        for identifier, item in scene.node_items.items()
        if item.node.label.startswith("Jean DUPONT")
    )
    assert scene.node_items[jean].node.severity is not None
    page.show_entity(jean, "Jean DUPONT")
    assert page.selected_entity == jean
    main_window.show_home()
    main_window.open_investigation(INVESTIGATION_NAME)
    assert page.selected_entity is None
    assert scene.selected_identifier() is None


def stored_positions(library: InvestigationLibrary) -> dict[str, Position]:
    with library.open(INVESTIGATION_NAME) as opened:
        return PositionStore(opened.connection).positions()


def test_the_graph_is_laid_out_in_the_background_once_opened(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    scene = main_window.investigation_page.graph_view.graph_scene
    positions = stored_positions(library)
    assert set(positions) == set(scene.node_items)
    for identifier, item in scene.node_items.items():
        assert item.node.placed
        assert item.point == (positions[identifier].x, positions[identifier].y)


def test_new_entities_are_laid_out_without_moving_the_others(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    before = stored_positions(library)
    company = next(identifier for identifier in before if identifier.startswith("company:"))
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        newcomer = builder.person("Marie", "MARTIN")
        builder.mandate(newcomer, company)
    main_window.refresh_overview()
    assert main_window.layout_job is not None
    qtbot.waitUntil(lambda: main_window.layout_job is None)
    after = stored_positions(library)
    assert {identifier: after[identifier] for identifier in before} == before
    item = main_window.investigation_page.graph_view.graph_scene.node_items[newcomer]
    assert item.node.placed


def test_entities_moved_by_the_investigator_are_remembered(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    page = main_window.investigation_page
    identifier = next(iter(page.graph_view.graph_scene.node_items))
    page.graph_view.entities_moved.emit({identifier: (-300.0, 45.5)})
    qtbot.waitUntil(lambda: not main_window.move_jobs)
    assert stored_positions(library)[identifier] == Position(-300.0, 45.5, True)
    main_window.refresh_overview()
    assert page.graph_view.graph_scene.node_items[identifier].point == (-300.0, 45.5)


def test_a_move_in_an_investigation_removed_meanwhile_is_notified(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    page = main_window.investigation_page
    identifier = next(iter(page.graph_view.graph_scene.node_items))
    library.rename(INVESTIGATION_NAME, "ailleurs")
    page.graph_view.entities_moved.emit({identifier: (0.0, 0.0)})
    qtbot.waitUntil(lambda: not main_window.move_jobs)
    [notification] = main_window.notification_area.notifications
    assert notification.message == f"L'enquête « {INVESTIGATION_NAME} » est introuvable."


def test_leaving_the_investigation_stops_its_layout(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    with library.open(INVESTIGATION_NAME) as opened:
        opened.connection.execute("DELETE FROM entity_position")
        opened.connection.commit()
    main_window.refresh_overview()
    job = main_window.layout_job
    assert job is not None
    main_window.show_home()
    assert main_window.layout_job is None
    assert not job.is_running()


def test_a_move_is_saved_before_leaving_the_investigation(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    page = main_window.investigation_page
    identifier = next(iter(page.graph_view.graph_scene.node_items))
    page.graph_view.entities_moved.emit({identifier: (12.0, 34.0)})
    main_window.show_home()
    assert main_window.move_jobs == []
    assert stored_positions(library)[identifier] == Position(12.0, 34.0, True)


def test_the_view_menu_zooms_and_fits_the_graph(main_window: MainWindow) -> None:
    menu_bar = main_window.main_menu_bar
    view = main_window.investigation_page.graph_view
    assert all(action.isEnabled() for action in menu_bar.graph_actions)
    fitted = view.zoom
    menu_bar.zoom_in_action.trigger()
    assert view.zoom > fitted
    menu_bar.zoom_out_action.trigger()
    menu_bar.zoom_out_action.trigger()
    assert view.zoom < fitted
    menu_bar.fit_action.trigger()
    assert view.zoom == pytest.approx(fitted)
    main_window.show_home()
    assert not any(action.isEnabled() for action in menu_bar.graph_actions)


def test_laying_out_again_keeps_the_moved_entities(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    page = main_window.investigation_page
    moved, other = list(page.graph_view.graph_scene.node_items)[:2]
    page.graph_view.entities_moved.emit({moved: (-999.0, -999.0)})
    qtbot.waitUntil(lambda: not main_window.move_jobs)
    with library.open(INVESTIGATION_NAME) as opened:
        PositionStore(opened.connection).save({other: Position(4321.0, 4321.0)})
    page.graph_view.zoom_in()
    main_window.main_menu_bar.layout_action.trigger()
    assert main_window.layout_job is not None
    qtbot.waitUntil(lambda: main_window.layout_job is None)
    positions = stored_positions(library)
    assert positions[moved] == Position(-999.0, -999.0, True)
    assert (positions[other].x, positions[other].y) != (4321.0, 4321.0)
    assert page.graph_view.follows_fit


def test_the_layout_button_lays_out_again(qtbot: QtBot, main_window: MainWindow) -> None:
    area = main_window.investigation_page.graph_area
    area.zoom_toolbar.layout_button.click()
    assert main_window.layout_job is not None
    qtbot.waitUntil(lambda: main_window.layout_job is None)


def queue_rows(main_window: MainWindow) -> list[QueueRow]:
    return main_window.investigation_page.queue_column.review_list.rows


def test_the_queue_shows_signals_homonyms_and_leads(main_window: MainWindow) -> None:
    review_list = main_window.investigation_page.queue_column.review_list
    assert review_list.group_titles == [
        "Rafale de créations · moyenne",
        "Homonymes à vérifier",
        "Pistes non étendues",
    ]
    assert [label.text() for label in review_list.empty_labels] == [
        "Aucun rapprochement en attente"
    ]
    assert len(review_list.expand_buttons) == 5


def test_choosing_an_entity_in_the_queue_selects_it_everywhere(
    main_window: MainWindow,
) -> None:
    page = main_window.investigation_page
    row = queue_rows(main_window)[0]
    QTest.mouseClick(row, Qt.MouseButton.LeftButton)
    identifier = row.entity.identifier
    assert page.selected_entity == identifier
    assert page.graph_view.selected_identifier == identifier
    assert row.property("selected")
    details = page.details_panel.entity_sheet.details
    assert details is not None
    assert details.identifier == identifier
    page.graph_view.graph_scene.select(None)
    assert not row.property("selected")
    assert page.details_panel.entity_sheet.details is None


def test_choosing_an_entity_hidden_by_a_filter_shows_it_again(
    main_window: MainWindow,
) -> None:
    page = main_window.investigation_page
    chip = page.graph_area.filter_chip
    chip.kind_actions[EntityKind.COMPANY].setChecked(False)
    lead = next(row for row in queue_rows(main_window) if row.entity.kind is EntityKind.COMPANY)
    QTest.mouseClick(lead, Qt.MouseButton.LeftButton)
    assert not chip.graph_filter.is_active
    assert page.graph_view.selected_identifier == lead.entity.identifier


def test_a_homonym_decided_in_the_queue_can_be_undone(
    qtbot: QtBot, main_window: MainWindow, library: InvestigationLibrary
) -> None:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.person("Marie", "DUPONT")
        builder.person("Marie Claire", "DUPONT")
    main_window.refresh_overview()
    review_list = main_window.investigation_page.queue_column.review_list
    same, _different = review_list.decision_buttons
    same.click()
    assert main_window.investigation_page.header.homonym_counter.text() == (
        "2 homonymes confirmés"
    )
    assert review_list.decision_buttons == []
    menu_bar = main_window.main_menu_bar
    menu_bar.undo_action.trigger()
    assert len(review_list.decision_buttons) == 2
    main_window.show_home()
    assert not menu_bar.undo_action.isEnabled()


def test_a_lead_is_expanded_from_the_queue(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    review_list = window.investigation_page.queue_column.review_list
    identifier, button = next(iter(review_list.expand_buttons.items()))
    button.click()
    assert identifier in window.review_actions.expansions
    assert not review_list.expand_buttons[identifier].isEnabled()
    qtbot.waitUntil(lambda: not window.review_actions.expansions, timeout=10_000)
    assert len(window.notification_area.notifications) == 2
    assert review_list.expand_buttons[identifier].isEnabled() or identifier not in (
        review_list.expand_buttons
    )


def sheet_of(main_window: MainWindow) -> EntitySheet:
    return main_window.investigation_page.details_panel.entity_sheet


def select_first_company(main_window: MainWindow) -> str:
    page = main_window.investigation_page
    company = next(
        node.identifier
        for node in page.graph_view.drawing.nodes
        if node.kind is EntityKind.COMPANY
    )
    page.show_entity(company, "")
    return company


def test_the_details_follow_the_selection_and_the_refreshes(main_window: MainWindow) -> None:
    company = select_first_company(main_window)
    sheet = sheet_of(main_window)
    assert sheet.details is not None
    assert sheet.details.identifier == company
    main_window.refresh_overview()
    assert sheet.details is not None
    assert sheet.details.identifier == company
    main_window.show_details("company:100000009")
    assert sheet.details is None


def test_the_raw_response_of_a_source_opens_in_a_dialog(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    select_first_company(main_window)
    sheet = sheet_of(main_window)
    sheet.source_rows[0].raw_button.click()
    [dialog] = main_window.findChildren(RawResponseDialog)
    assert dialog.isVisible()
    assert dialog.text_view.toPlainText() == "{}"
    dialog.reject()
    with library.open(INVESTIGATION_NAME) as opened:
        opened.connection.execute("UPDATE response SET body = ?", (b'{"faux": 1}',))
        opened.connection.commit()
    sheet.source_rows[0].raw_button.click()
    [notification] = main_window.notification_area.notifications
    assert "a été modifiée depuis sa collecte" in notification.message


def test_details_of_an_investigation_removed_meanwhile_are_not_shown(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    library.rename(INVESTIGATION_NAME, "ailleurs")
    main_window.show_details("company:100000000")
    main_window.show_raw_response(1)
    messages = [
        notification.message for notification in main_window.notification_area.notifications
    ]
    assert messages == [f"L'enquête « {INVESTIGATION_NAME} » est introuvable."] * 2
    main_window.show_home()
    main_window.show_raw_response(1)
    main_window.show_details("company:100000000")
    assert sheet_of(main_window).details is None


def test_copying_from_the_sheet_is_confirmed(main_window: MainWindow) -> None:
    select_first_company(main_window)
    sheet = sheet_of(main_window)
    sheet.copy_button.click()
    [notification] = main_window.notification_area.notifications
    assert notification.message.endswith("copié dans le presse-papiers.")


def test_an_entity_is_expanded_again_from_its_sheet(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    company = select_first_company(window)
    sheet_of(window).depth_menu.actions()[1].trigger()
    assert company in window.review_actions.expansions
    qtbot.waitUntil(lambda: not window.review_actions.expansions, timeout=10_000)


def test_the_notices_of_a_company_are_refreshed_from_its_sheet(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    company = select_first_company(window)
    sheet = sheet_of(window)
    assert sheet.refresh_button is not None
    sheet.refresh_button.click()
    assert company in window.review_actions.expansions
    assert sheet.refresh_button is not None
    assert not sheet.refresh_button.isEnabled()
    qtbot.waitUntil(lambda: not window.review_actions.expansions, timeout=10_000)
    messages = [notification.message for notification in window.notification_area.notifications]
    assert messages[0].startswith("Rafraîchissement des annonces de SOCIETE")
    assert messages[-1].startswith("Annonces de SOCIETE")
    assert sheet.refresh_button is not None
    assert sheet.refresh_button.isEnabled()


def test_the_raw_response_of_a_notice_opens_in_a_dialog(
    main_window: MainWindow, library: InvestigationLibrary
) -> None:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        company = builder.company("SOCIETE ANNONCEE", date(2024, 5, 2))
        builder.notice(company, NoticeFamily.REMOVAL, date(2025, 6, 1), "Radiation")
        opened.connection.commit()
    main_window.refresh_overview()
    main_window.investigation_page.show_entity(company, "")
    sheet = sheet_of(main_window)
    assert sheet.timeline is not None
    sheet.timeline.items[0].raw_button.click()
    [dialog] = main_window.findChildren(RawResponseDialog)
    assert dialog.isVisible()


def test_choosing_a_row_of_the_entities_table_selects_the_entity_in_the_graph(
    main_window: MainWindow,
) -> None:
    page = main_window.investigation_page
    panel = page.details_panel
    tabs = panel.tabs
    assert [tabs.tabText(index) for index in range(tabs.count())][2:] == ["Entités 5", "Journal"]
    entities = panel.entities_tab
    entities.sort_box.setCurrentText("Nom")
    entities.table.selectRow(0)
    first = entities.selected_identifier()
    assert first is not None
    assert page.graph_view.selected_identifier == first
    details = sheet_of(main_window).details
    assert details is not None
    assert details.identifier == first
    company = select_first_company(main_window)
    assert entities.selected_identifier() == company
    main_window.refresh_overview()
    assert entities.selected_identifier() == company
