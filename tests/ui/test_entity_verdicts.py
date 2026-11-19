import shutil
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.verdicts import EntityVerdict, Verdict, VerdictStore
from lacis.ui.main_window import MainWindow
from lacis.ui.verdict_editor import VerdictEditor

INVESTIGATION_NAME = "faux-plombiers-31"
ACME = "company:111111111"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.company("ACME PLOMBERIE", date(2021, 3, 1), identifier=ACME)
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


def verdict_editor(window: MainWindow) -> VerdictEditor:
    editor = window.investigation_page.details_panel.entity_sheet.verdict_editor
    assert editor is not None
    return editor


def stored_verdict(library: InvestigationLibrary) -> EntityVerdict | None:
    with library.open(INVESTIGATION_NAME) as opened:
        return VerdictStore(opened.connection).verdict(ACME)


def test_a_verdict_is_chosen_in_the_sheet(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    editor = verdict_editor(window)
    editor.choice.setCurrentIndex(editor.choice.findData(Verdict.SUSPECT.value))
    editor.reason.setText("Même gérant que DUPONT SERVICES.")
    editor.reason.editingFinished.emit()
    stored = stored_verdict(library)
    assert stored is not None
    assert (stored.verdict, stored.reason) == (Verdict.SUSPECT, "Même gérant que DUPONT SERVICES.")
    assert verdict_editor(window) is editor
    assert editor.decided_label.text().startswith("Décidé le ")
    sheet = window.investigation_page.details_panel.entity_sheet
    assert sheet.verdict_title is not None
    assert sheet.verdict_title.accessibleName() == "Verdict, suspect"


def test_a_verdict_is_withdrawn_in_the_sheet(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    window.save_verdict(ACME, Verdict.CONFIRMED, "")
    verdict_editor(window).choice.setCurrentIndex(0)
    assert stored_verdict(library) is None
    sheet = window.investigation_page.details_panel.entity_sheet
    assert sheet.verdict_title is not None
    assert sheet.verdict_title.accessibleName() == "Verdict, aucun"


def test_a_verdict_that_cannot_be_saved_is_reported(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    shutil.rmtree(library.directory_of(INVESTIGATION_NAME))
    window.save_verdict(ACME, Verdict.SUSPECT, "")
    assert window.notification_area.notifications[-1].message


def test_no_verdict_is_saved_outside_an_investigation(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    window.show_home()
    window.save_verdict(ACME, Verdict.SUSPECT, "")
    assert stored_verdict(library) is None
