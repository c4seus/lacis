from pathlib import Path

import pytest
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from lacis.exports.formats import JSON_FORMAT, MARKDOWN_REPORT_FORMAT, OBSIDIAN_FORMAT
from lacis.ui.export_dialog import (
    FILE_GIVEN_TEXT,
    FOLDER_GIVEN_TEXT,
    MISSING_FOLDER_TEXT,
    MISSING_PATH_TEXT,
    MISSING_VAULT_TEXT,
    NEW_FOLDER_TEXT,
    NO_FILTER_TEXT,
    NOT_EMPTY_TEXT,
    REPLACED_TEXT,
    ExportDialog,
    ExportOffer,
    FolderChooser,
    PathChooser,
    existing_folder,
    save_file_name,
)

NAME = "faux-plombiers-31"


def refusing_chooser(_parent: QWidget, _title: str, _path: str, _filters: str) -> str:
    return ""


def refusing_folder_chooser(_parent: QWidget, _title: str, _path: str) -> str:
    return ""


def choose_vault(dialog: ExportDialog) -> None:
    dialog.format_box.setCurrentIndex(dialog.format_box.findData("obsidian"))


def open_dialog(
    qtbot: QtBot,
    folder: Path,
    shown: int | None = None,
    choose_path: PathChooser = refusing_chooser,
    choose_folder: FolderChooser = refusing_folder_chooser,
) -> ExportDialog:
    offer = ExportOffer(NAME, folder, 9, shown, JSON_FORMAT)
    dialog = ExportDialog(offer, None, choose_path, choose_folder)
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
    assert [dialog.format_box.itemData(index) for index in range(3)] == [
        "markdown_report",
        "json",
        "obsidian",
    ]
    dialog.format_box.setCurrentIndex(dialog.format_box.findData("markdown_report"))
    request = dialog.request()
    assert request.export_format is MARKDOWN_REPORT_FORMAT
    assert request.destination == tmp_path / f"{NAME}.md"


def test_the_obsidian_vault_is_a_folder_named_after_the_investigation(
    qtbot: QtBot, tmp_path: Path
) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    choose_vault(dialog)
    assert dialog.destination() == tmp_path / NAME
    assert dialog.choose_button.accessibleName() == "Choisir le dossier de destination"
    assert dialog.problem_label.text() == NEW_FOLDER_TEXT
    assert dialog.export_button.isEnabled()
    request = dialog.request()
    assert request.export_format is OBSIDIAN_FORMAT
    assert request.destination == tmp_path / NAME
    dialog.format_box.setCurrentIndex(dialog.format_box.findData("json"))
    assert dialog.destination() == tmp_path / f"{NAME}.json"
    assert dialog.choose_button.accessibleName() == "Choisir le fichier de destination"


def test_a_name_with_dots_keeps_them_when_the_format_changes(qtbot: QtBot, tmp_path: Path) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    dialog.path_field.setText(str(tmp_path / "enquête.v2.json"))
    choose_vault(dialog)
    assert dialog.destination() == tmp_path / "enquête.v2"
    dialog.format_box.setCurrentIndex(dialog.format_box.findData("markdown_report"))
    assert dialog.destination() == tmp_path / "enquête.v2.md"


def test_an_empty_folder_can_receive_the_vault(qtbot: QtBot, tmp_path: Path) -> None:
    (tmp_path / NAME).mkdir()
    dialog = open_dialog(qtbot, tmp_path)
    choose_vault(dialog)
    assert dialog.problem_label.isHidden()
    assert dialog.export_button.isEnabled()


@pytest.mark.parametrize(
    ("prepare", "problem"),
    [
        ("non-empty", NOT_EMPTY_TEXT),
        ("file", FILE_GIVEN_TEXT),
        ("missing parent", MISSING_FOLDER_TEXT),
        ("empty path", MISSING_VAULT_TEXT),
    ],
)
def test_a_vault_destination_that_cannot_be_used_blocks_the_export(
    qtbot: QtBot, tmp_path: Path, prepare: str, problem: str
) -> None:
    dialog = open_dialog(qtbot, tmp_path)
    choose_vault(dialog)
    vault = tmp_path / NAME
    if prepare == "non-empty":
        vault.mkdir()
        (vault / "note.md").write_text("", encoding="utf-8")
        dialog.check_destination()
    elif prepare == "file":
        vault.write_text("", encoding="utf-8")
        dialog.check_destination()
    elif prepare == "missing parent":
        dialog.path_field.setText(str(tmp_path / "absent" / NAME))
    else:
        dialog.path_field.setText(" ")
    assert dialog.problem_label.text() == problem
    assert not dialog.export_button.isEnabled()


def test_the_vault_folder_is_chosen_in_a_folder_dialog(qtbot: QtBot, tmp_path: Path) -> None:
    asked = []

    def chooser(parent: QWidget, title: str, path: str) -> str:
        asked.append((parent, title, path))
        return str(tmp_path / "coffre")

    dialog = open_dialog(qtbot, tmp_path, choose_folder=chooser)
    choose_vault(dialog)
    dialog.choose_button.click()
    assert asked == [(dialog, "Exporter l'enquête", str(tmp_path / NAME))]
    assert dialog.destination() == tmp_path / "coffre"


def test_the_folder_dialog_returns_the_chosen_folder(
    qtbot: QtBot, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "lacis.ui.export_dialog.QFileDialog.getExistingDirectory",
        lambda *_arguments: str(tmp_path),
    )
    parent = QWidget()
    qtbot.addWidget(parent)
    assert existing_folder(parent, "Exporter l'enquête", str(tmp_path)) == str(tmp_path)
