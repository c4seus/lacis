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
from lacis.storage.tags import Tag, TagStore
from lacis.ui.main_window import MainWindow
from lacis.ui.tag_editor import TagEditor

INVESTIGATION_NAME = "faux-plombiers-31"
ACME = "company:111111111"
DUPONT = "company:222222222"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        person = builder.person("Jean", "DUPONT")
        builder.mandate(
            person, builder.company("ACME PLOMBERIE", date(2021, 3, 1), identifier=ACME)
        )
        builder.mandate(
            person, builder.company("DUPONT SERVICES", date(2019, 4, 2), identifier=DUPONT)
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
    window.activateWindow()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    window.investigation_page.show_entity(ACME, "")
    return window


def tag_editor(window: MainWindow) -> TagEditor:
    editor = window.investigation_page.details_panel.entity_sheet.tag_editor
    assert editor is not None
    return editor


def stored_tags(library: InvestigationLibrary, identifier: str) -> tuple[Tag, ...]:
    with library.open(INVESTIGATION_NAME) as opened:
        return TagStore(opened.connection).tags_of(identifier)


def test_a_tag_is_added_without_rebuilding_the_sheet(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    editor = tag_editor(window)
    editor.field.setFocus()
    editor.field.setText("  Client ")
    editor.field.returnPressed.emit()
    assert stored_tags(library, ACME) == (Tag("client", "Client"),)
    assert tag_editor(window) is editor
    assert editor.field.hasFocus()
    assert [button.text() for button in editor.buttons] == ["Client ✕"]
    sheet = window.investigation_page.details_panel.entity_sheet
    assert sheet.tag_title is not None
    assert sheet.tag_title.accessibleName() == "Tags, 1"
    assert sheet.known_tags == (Tag("client", "Client"),)


def test_a_tag_used_elsewhere_is_proposed_and_keeps_its_spelling(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    window.add_tag(ACME, "réseau Dupont")
    window.investigation_page.show_entity(DUPONT, "")
    editor = tag_editor(window)
    assert editor.completions.stringList() == ["réseau Dupont"]
    window.add_tag(DUPONT, "RÉSEAU  DUPONT")
    assert stored_tags(library, DUPONT) == (Tag("réseau dupont", "réseau Dupont"),)
    assert editor.completions.stringList() == []


def test_a_tag_is_removed_from_its_chip(window: MainWindow, library: InvestigationLibrary) -> None:
    window.add_tag(ACME, "client")
    tag_editor(window).buttons[0].click()
    assert stored_tags(library, ACME) == ()
    assert tag_editor(window).buttons == []
    assert window.investigation_page.details_panel.entity_sheet.known_tags == ()


def test_a_tag_that_cannot_be_saved_is_reported(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    shutil.rmtree(library.directory_of(INVESTIGATION_NAME))
    window.add_tag(ACME, "client")
    assert window.notification_area.notifications[-1].message


def test_no_tag_is_saved_outside_an_investigation(
    window: MainWindow, library: InvestigationLibrary
) -> None:
    window.show_home()
    window.add_tag(ACME, "client")
    assert stored_tags(library, ACME) == ()
