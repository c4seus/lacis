from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from lacis.exports.formats import JSON_FORMAT, MARKDOWN_REPORT_FORMAT
from lacis.ui.export_dialog import (
    FOLDER_GIVEN_TEXT,
    MISSING_FOLDER_TEXT,
    MISSING_PATH_TEXT,
    NO_FILTER_TEXT,
    REPLACED_TEXT,
    ExportDialog,
    ExportOffer,
    PathChooser,
    save_file_name,
)

NAME = "faux-plombiers-31"


def refusing_chooser(_parent: QWidget, _title: str, _path: str, _filters: str) -> str:
    return ""


def open_dialog(
    qtbot: QtBot,
    folder: Path,
    shown: int | None = None,
    choose_path: PathChooser = refusing_chooser,
) -> ExportDialog:
    dialog = ExportDialog(ExportOffer(NAME, folder, 9, shown, JSON_FORMAT), None, choose_path)
    qtbot.addWidget(dialog)
    return dialog


def test_the_dialog_offers_the_whole_investigation_in_the_folder_given(
    qtbot: QtBot, tmp_path: Path
) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    assert dialog.windowTitle() == "Exporter l'enquête"
    assert dialog.format_box.currentData() == "json"
    assert dialog.format_box.currentText().startswith("JSON : Export complet")
    assert dialog.whole_button.isChecked()
    assert dialog.whole_button.text() == "&Toute l'enquête, 9 entités"
    assert dialog.whole_button.accessibleName() == "Contenu : Toute l'enquête, 9 entités"
    assert dialog.path_field.text() == str(tmp_path / f"{NAME}.json")
    assert dialog.export_button.isEnabled()
    assert dialog.problem_label.isHidden()
    assert dialog.format_label.buddy() is dialog.format_box
    assert dialog.destination_label.buddy() is dialog.path_field


def test_the_filtered_view_cannot_be_chosen_without_a_filter(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    button = dialog.filtered_button
    assert not button.isEnabled()
    assert button.toolTip() == NO_FILTER_TEXT
    assert button.accessibleDescription() == NO_FILTER_TEXT


def test_the_filtered_view_counts_the_entities_shown(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path, shown=1)
    assert dialog.filtered_button.isEnabled()
    assert dialog.filtered_button.text() == "La &vue filtrée, 1 entité"
    assert not dialog.request().filtered
    dialog.filtered_button.click()
    request = dialog.request()
    assert request.filtered
    assert request.export_format is JSON_FORMAT
    assert request.destination == tmp_path / f"{NAME}.json"


def test_the_extension_follows_the_format(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    dialog.path_field.setText(str(tmp_path / "rapport.txt"))
    dialog.follow_format()
    assert dialog.path_field.text() == str(tmp_path / "rapport.json")
    dialog.path_field.clear()
    dialog.follow_format()
    assert dialog.path_field.text() == ""


def test_the_destination_is_chosen_in_a_file_dialog(qtbot: QtBot, tmp_path: Path) -> None:
    asked = []

    def chooser(parent: QWidget, title: str, path: str, filters: str) -> str:
        asked.append((parent, title, path, filters))
        return str(tmp_path / "choisi.json")

    dialog = open_dialog(qtbot, tmp_path, choose_path=chooser)
    dialog.choose_button.click()
    assert asked == [
        (dialog, "Exporter l'enquête", str(tmp_path / f"{NAME}.json"), "JSON (*.json)")
    ]
    assert dialog.destination() == tmp_path / "choisi.json"


def test_a_cancelled_file_dialog_keeps_the_destination(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    dialog.choose_button.click()
    assert dialog.destination() == tmp_path / f"{NAME}.json"


@pytest.mark.parametrize(
    ("relative_path", "problem"),
    [
        ("", MISSING_PATH_TEXT),
        ("absent/export.json", MISSING_FOLDER_TEXT),
        (".", FOLDER_GIVEN_TEXT),
    ],
)
def test_a_destination_that_cannot_be_written_blocks_the_export(
    qtbot: QtBot, tmp_path: Path, relative_path: str, problem: str
) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    dialog.path_field.setText(str(tmp_path / relative_path) if relative_path else "  ")
    assert dialog.problem_label.text() == problem
    assert not dialog.problem_label.isHidden()
    assert dialog.path_field.accessibleDescription() == problem
    assert not dialog.export_button.isEnabled()


def test_an_existing_file_is_replaced_after_a_warning(qtbot: QtBot, tmp_path: Path) -> None:
    (tmp_path / f"{NAME}.json").write_text("{}", encoding="utf-8")
    dialog = open_dialog(qtbot, tmp_path)
    assert dialog.problem_label.text() == REPLACED_TEXT
    assert dialog.export_button.isEnabled()


def test_the_destination_accepts_the_home_shortcut(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    dialog.path_field.setText("~/export.json")
    assert dialog.destination() == Path.home() / "export.json"


def test_the_file_dialog_returns_the_chosen_path(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    chosen = str(tmp_path / "choisi.json")
    monkeypatch.setattr(
        "lacis.ui.export_dialog.QFileDialog.getSaveFileName",
        lambda *_arguments: (chosen, "JSON (*.json)"),
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    assert save_file_name(parent, "Exporter l'enquête", str(tmp_path), "JSON (*.json)") == chosen


def test_choosing_another_format_changes_the_extension_of_the_destination(
    qtbot: QtBot, tmp_path: Path
) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    assert [dialog.format_box.itemData(index) for index in range(2)] == [
        "markdown_report",
        "json",
    ]
    dialog.format_box.setCurrentIndex(dialog.format_box.findData("markdown_report"))
    request = dialog.request()
    assert request.export_format is MARKDOWN_REPORT_FORMAT
    assert request.destination == tmp_path / f"{NAME}.md"
