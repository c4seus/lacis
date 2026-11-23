import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.theme_controller import ThemeController
from lacis.exports.formats import (
    GEXF_FORMAT,
    JSON_FORMAT,
    MALTEGO_FORMAT,
    MARKDOWN_REPORT_FORMAT,
    OBSIDIAN_FORMAT,
    ExportFormat,
)
from lacis.exports.json_export import FILTERED_VIEW, WHOLE_INVESTIGATION
from lacis.graph.filters import GraphFilter
from lacis.storage.entities import EntityKind
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.locations import documents_directory
from lacis.ui.export_dialog import ExportDialog, ExportOffer, ExportRequest
from lacis.ui.main_window import MainWindow
from lacis.ui.notifications import NotificationKind

INVESTIGATION_NAME = "faux-plombiers-31"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "Qui se cache derrière les plombiers ?")
    return library


@pytest.fixture
def scenario(library: InvestigationLibrary) -> PlumbersScenario:
    with library.open(INVESTIGATION_NAME) as opened:
        return plumbers_scenario(InvestigationBuilder(opened.connection))


@pytest.fixture
def window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
    scenario: PlumbersScenario,
) -> MainWindow:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.show()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    return window


class ExportAnswers:
    def __init__(self, request: ExportRequest | None) -> None:
        self.request = request
        self.offers: list[ExportOffer] = []

    def __call__(self, offer: ExportOffer) -> ExportRequest | None:
        self.offers.append(offer)
        return self.request


def answer_with(
    monkeypatch: pytest.MonkeyPatch, window: MainWindow, request: ExportRequest | None
) -> ExportAnswers:
    answers = ExportAnswers(request)
    monkeypatch.setattr(window, "ask_export", answers)
    return answers


def read_export(destination: Path) -> Any:
    return json.loads(destination.read_text(encoding="utf-8"))


def last_notification(window: MainWindow) -> tuple[str, NotificationKind]:
    notification = window.notification_area.notifications[-1]
    return notification.message, notification.kind


def test_the_whole_investigation_is_exported_from_the_file_menu(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "export.json"
    answers = answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, False, destination))
    window.main_menu_bar.export_actions["json"].trigger()
    assert answers.offers == [
        ExportOffer(INVESTIGATION_NAME, documents_directory(), 9, None, JSON_FORMAT)
    ]
    document = read_export(destination)
    assert document["scope"] == WHOLE_INVESTIGATION
    assert len(document["entities"]) == 9
    assert document["investigation"]["question"] == "Qui se cache derrière les plombiers ?"
    assert last_notification(window) == (
        "Enquête exportée dans export.json.",
        NotificationKind.SUCCESS,
    )


def test_the_filtered_view_exports_only_the_entities_shown(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    scenario: PlumbersScenario,
) -> None:
    hidden = frozenset({EntityKind.PERSON, EntityKind.ADDRESS, EntityKind.ESTABLISHMENT})
    window.investigation_page.graph_area.filter_chip.change(GraphFilter(hidden_kinds=hidden))
    destination = tmp_path / "vue.json"
    answers = answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, True, destination))
    window.export_investigation("json")
    companies = {scenario.acme, scenario.dupont_services, scenario.holding, scenario.invest}
    document = read_export(destination)
    exported = {entity["identifier"] for entity in document["entities"]}
    assert answers.offers[0].shown == len(exported)
    assert scenario.acme in exported
    assert exported <= companies
    assert document["scope"] == FILTERED_VIEW
    for link in document["links"]:
        assert {link["source"], link["target"]} <= exported


def test_the_whole_investigation_can_be_exported_while_a_filter_is_active(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hidden = frozenset({EntityKind.PERSON})
    window.investigation_page.graph_area.filter_chip.change(GraphFilter(hidden_kinds=hidden))
    destination = tmp_path / "tout.json"
    answers = answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, False, destination))
    window.export_investigation("json")
    assert answers.offers[0].shown is not None
    assert answers.offers[0].shown < answers.offers[0].total
    assert len(read_export(destination)["entities"]) == 9


def test_a_cancelled_export_writes_nothing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    answers = answer_with(monkeypatch, window, None)
    notified = len(window.notification_area.notifications)
    window.export_investigation("json")
    assert len(answers.offers) == 1
    assert list(tmp_path.glob("*.json")) == []
    assert len(window.notification_area.notifications) == notified


def test_an_export_that_cannot_be_written_is_reported(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "absent" / "export.json"
    answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, False, destination))
    window.export_investigation("json")
    message, kind = last_notification(window)
    assert message.startswith("Impossible d'écrire l'export : ")
    assert kind is NotificationKind.ERROR


def test_an_export_of_a_vanished_investigation_is_reported(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    library: InvestigationLibrary,
) -> None:
    shutil.rmtree(library.directory_of(INVESTIGATION_NAME))
    destination = tmp_path / "export.json"
    answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, False, destination))
    window.export_investigation("json")
    message, kind = last_notification(window)
    assert message
    assert kind is NotificationKind.ERROR
    assert not destination.exists()


def test_nothing_is_exported_outside_an_investigation(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window.show_home()
    answers = answer_with(monkeypatch, window, ExportRequest(JSON_FORMAT, False, tmp_path))
    window.export_investigation("json")
    assert answers.offers == []


@pytest.mark.parametrize(
    ("answer", "requested"),
    [(QDialog.DialogCode.Accepted, True), (QDialog.DialogCode.Rejected, False)],
)
def test_the_export_dialog_is_asked(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    answer: QDialog.DialogCode,
    requested: bool,
) -> None:
    monkeypatch.setattr(ExportDialog, "exec", lambda _dialog: answer)
    offer = ExportOffer(INVESTIGATION_NAME, tmp_path, 9, None, JSON_FORMAT)
    request = window.ask_export(offer)
    if requested:
        assert request == ExportRequest(
            JSON_FORMAT, False, tmp_path / f"{INVESTIGATION_NAME}.json"
        )
    else:
        assert request is None


def test_the_report_is_exported_from_the_file_menu(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "rapport.md"
    request = ExportRequest(MARKDOWN_REPORT_FORMAT, False, destination)
    answers = answer_with(monkeypatch, window, request)
    window.main_menu_bar.export_actions["markdown_report"].trigger()
    assert answers.offers[0].chosen_format is MARKDOWN_REPORT_FORMAT
    text = destination.read_text(encoding="utf-8")
    assert text.startswith(f"# Rapport d'enquête : {INVESTIGATION_NAME}\n")
    assert "Qui se cache derrière les plombiers ?" in text
    assert last_notification(window) == (
        "Enquête exportée dans rapport.md.",
        NotificationKind.SUCCESS,
    )


def test_the_obsidian_vault_is_exported_from_the_file_menu(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    destination = tmp_path / "coffre"
    request = ExportRequest(OBSIDIAN_FORMAT, False, destination)
    answers = answer_with(monkeypatch, window, request)
    window.main_menu_bar.export_actions["obsidian"].trigger()
    assert answers.offers[0].chosen_format is OBSIDIAN_FORMAT
    assert (destination / f"Enquête {INVESTIGATION_NAME}.md").is_file()
    assert len(list(destination.rglob("*.md"))) == 10
    assert last_notification(window) == (
        "Enquête exportée dans coffre.",
        NotificationKind.SUCCESS,
    )


@pytest.mark.parametrize("export", [GEXF_FORMAT, MALTEGO_FORMAT])
def test_the_graph_is_exported_for_gephi_and_maltego_from_the_file_menu(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, export: ExportFormat
) -> None:
    file_name = f"graphe{export.extension}"
    destination = tmp_path / file_name
    answers = answer_with(monkeypatch, window, ExportRequest(export, False, destination))
    window.main_menu_bar.export_actions[export.key].trigger()
    assert answers.offers[0].chosen_format is export
    assert "ACME PLOMBERIE" in destination.read_text(encoding="utf-8")
    assert last_notification(window) == (
        f"Enquête exportée dans {file_name}.",
        NotificationKind.SUCCESS,
    )
