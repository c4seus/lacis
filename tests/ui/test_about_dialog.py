from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, QUrl
from pytestqt.qtbot import QtBot

from accessibility_checks import interactive_widgets_without_accessible_name
from lacis import __version__
from lacis.application import main
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.product import BUNDLED_ASSETS, RESOURCE_DIRECTORY, BundledAsset
from lacis.ui.about_dialog import AboutDialog, license_address
from lacis.ui.main_window import MainWindow


def open_about_dialog(qtbot: QtBot, icon_factory: IconFactory) -> AboutDialog:
    dialog = AboutDialog(icon_factory)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def all_texts(dialog: AboutDialog) -> str:
    return "\n".join(
        label.text()
        for label in [
            dialog.name_label,
            dialog.version_label,
            dialog.description_label,
            dialog.license_label,
            dialog.source_code_label,
            *dialog.bundled_asset_labels,
        ]
    )


def test_the_dialog_is_titled_about_lacis(qtbot: QtBot, icon_factory: IconFactory) -> None:
    assert open_about_dialog(qtbot, icon_factory).windowTitle() == "À propos de Lacis"


def test_the_dialog_shows_the_same_version_as_the_command(
    qtbot: QtBot, icon_factory: IconFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit):
        main(["lacis", "--version"])
    command_version = capsys.readouterr().out.strip().removeprefix("Lacis ")
    dialog = open_about_dialog(qtbot, icon_factory)
    assert dialog.version_label.text() == f"Version {command_version}"
    assert command_version == __version__


def test_the_dialog_states_the_license_and_the_source_code(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    texts = all_texts(open_about_dialog(qtbot, icon_factory))
    assert "GNU General Public License v3.0 ou ultérieure" in texts
    assert "https://www.gnu.org/licenses/gpl-3.0.html" in texts
    assert "https://github.com/c4seus/lacis" in texts


def test_the_dialog_lists_every_bundled_asset_with_its_license(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    dialog = open_about_dialog(qtbot, icon_factory)
    assert len(dialog.bundled_asset_labels) == len(BUNDLED_ASSETS)
    for asset, label in zip(BUNDLED_ASSETS, dialog.bundled_asset_labels, strict=True):
        assert asset.name in label.text()
        assert asset.license_name in label.text()
        assert label.openExternalLinks()


def test_local_licenses_open_the_bundled_license_file() -> None:
    local_assets = [
        asset for asset in BUNDLED_ASSETS if not asset.license_location.startswith("https://")
    ]
    assert local_assets
    for asset in local_assets:
        address = license_address(asset)
        assert address.isLocalFile()
        assert Path(address.toLocalFile()).is_file()


def test_web_licenses_open_their_web_page() -> None:
    web_asset = BundledAsset("Logo", "Lacis", "GPL", "https://www.gnu.org/licenses/gpl-3.0.html")
    assert license_address(web_asset) == QUrl("https://www.gnu.org/licenses/gpl-3.0.html")


def test_the_asset_list_matches_the_license_list_of_the_repository() -> None:
    license_list = (RESOURCE_DIRECTORY / "LICENSES.md").read_text(encoding="utf-8")
    assert "Inter 4.1" in license_list
    assert "SIL Open Font License 1.1" in license_list
    assert "Lacis logo" in license_list


def test_the_close_button_closes_the_dialog(qtbot: QtBot, icon_factory: IconFactory) -> None:
    dialog = open_about_dialog(qtbot, icon_factory)
    with qtbot.waitSignal(dialog.rejected):
        dialog.button_box.rejected.emit()
    assert not dialog.isVisible()


def test_every_interactive_widget_of_the_dialog_has_a_name(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    dialog = open_about_dialog(qtbot, icon_factory)
    assert interactive_widgets_without_accessible_name(dialog) == []


def test_the_help_menu_opens_the_about_dialog(
    qtbot: QtBot, settings: QSettings, theme_controller: ThemeController
) -> None:
    main_window = MainWindow(settings, theme_controller)
    qtbot.addWidget(main_window)
    main_window.show()
    main_window.header_bar.help_menu.about_action.trigger()
    about_dialog = main_window.about_dialog
    assert about_dialog is not None
    qtbot.waitExposed(about_dialog)
    assert about_dialog.isVisible()
    assert about_dialog.parent() is main_window
    main_window.header_bar.help_menu.about_action.trigger()
    assert main_window.about_dialog is about_dialog
