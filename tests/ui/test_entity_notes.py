from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.notes import NoteStore
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
ACME = "company:111111111"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.mandate(
            builder.person("Jean", "DUPONT"),
            builder.company("ACME PLOMBERIE", date(2021, 3, 1), identifier=ACME),
        )
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
    window.investigation_page.show_entity(ACME, "")
    return window


def stored_note(library: InvestigationLibrary) -> str | None:
    with library.open(INVESTIGATION_NAME) as opened:
        note = NoteStore(opened.connection).note(ACME)
    return None if note is None else note.text


def write(window: MainWindow, text: str) -> None:
    editor = window.investigation_page.details_panel.entity_sheet.note_editor
    assert editor is not None
    editor.editor.setPlainText(text)
    editor.flush()


def test_a_note_is_saved_without_an_explicit_action(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    write(window, "Gérant de paille ?")
    assert stored_note(library) == "Gérant de paille ?"
    editor = window.investigation_page.details_panel.entity_sheet.note_editor
    assert editor is not None
    assert editor.dates_label.text().startswith("Créée le ")


def test_a_note_survives_a_restart(
    qtbot: QtBot,
    window: MainWindow,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> None:
    write(window, "Gérant de paille ?")
    window.close()
    reopened = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(reopened)
    reopened.show()
    reopened.open_investigation(INVESTIGATION_NAME)
    reopened.investigation_page.show_entity(ACME, "")
    editor = reopened.investigation_page.details_panel.entity_sheet.note_editor
    assert editor is not None
    assert editor.text() == "Gérant de paille ?"


@pytest.mark.parametrize("leave", ["show_home", "close"])
def test_leaving_the_investigation_saves_the_note_being_written(
    window: MainWindow, library: InvestigationLibrary, leave: str
) -> None:
    editor = window.investigation_page.details_panel.entity_sheet.note_editor
    assert editor is not None
    editor.editor.setPlainText("Pas encore enregistré.")
    getattr(window, leave)()
    assert stored_note(library) == "Pas encore enregistré."


def test_writing_or_erasing_a_note_reads_the_investigation_again(
    qtbot: QtBot, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[None] = []
    monkeypatch.setattr(window, "refresh_overview", lambda: calls.append(None))
    write(window, "Gérant de paille ?")
    qtbot.waitUntil(lambda: len(calls) == 1)
    write(window, "Gérant de paille.")
    qtbot.wait(20)
    assert len(calls) == 1
    write(window, "")
    qtbot.waitUntil(lambda: len(calls) == 2)


def test_a_note_that_cannot_be_saved_is_reported(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    library.delete(INVESTIGATION_NAME)
    write(window, "Perdu ?")
    assert window.notification_area.notifications[-1].message


def test_no_note_is_saved_outside_an_investigation(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    window.show_home()
    window.save_note(ACME, "Hors enquête.")
    assert stored_note(library) is None
