from pathlib import Path

import pytest
from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication

from lacis.application import configure_application
from lacis.storage.locations import (
    CONFIGURATION_DIRECTORY_VARIABLE,
    DATA_DIRECTORY_VARIABLE,
    configuration_directory,
    data_directory,
    documents_directory,
    existing_directory_or_home,
    investigations_directory,
)


def test_the_data_directory_is_the_application_data_directory_of_the_platform(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_application(qapp)
    monkeypatch.delenv(DATA_DIRECTORY_VARIABLE, raising=False)
    expected_directory = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    assert data_directory() == Path(expected_directory)
    assert "Lacis" in data_directory().parts


def test_the_data_directory_can_be_overridden_for_tests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path))
    assert data_directory() == tmp_path


def test_investigations_live_in_their_own_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(DATA_DIRECTORY_VARIABLE, str(tmp_path))
    assert investigations_directory() == tmp_path / "investigations"


def test_tests_never_use_the_real_data_directory(isolated_data_directory: Path) -> None:
    assert data_directory() == isolated_data_directory


def test_the_configuration_directory_is_the_configuration_directory_of_the_platform(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    configure_application(qapp)
    monkeypatch.delenv(CONFIGURATION_DIRECTORY_VARIABLE, raising=False)
    expected_directory = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppConfigLocation
    )
    assert configuration_directory() == Path(expected_directory)
    assert "Lacis" in configuration_directory().parts


def test_tests_never_use_the_real_configuration_directory(
    isolated_configuration_directory: Path,
) -> None:
    assert configuration_directory() == isolated_configuration_directory


def test_exports_are_offered_in_the_documents_directory(qapp: QApplication) -> None:
    documents_location = QStandardPaths.StandardLocation.DocumentsLocation
    found = QStandardPaths.writableLocation(documents_location)
    assert documents_directory() == existing_directory_or_home(found)


def test_an_existing_directory_is_kept(tmp_path: Path) -> None:
    assert existing_directory_or_home(str(tmp_path)) == tmp_path


def test_a_missing_documents_directory_falls_back_to_the_home_directory(tmp_path: Path) -> None:
    assert existing_directory_or_home(str(tmp_path / "Documents")) == Path.home()
    assert existing_directory_or_home("") == Path.home()
