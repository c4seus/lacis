from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary
from lacis.ui.investigation_page import Counter, InvestigationPage, noun_for
from lacis.ui.main_window import MainWindow

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
