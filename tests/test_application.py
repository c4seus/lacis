import runpy
import sys

import pytest
from PySide6.QtCore import QLocale
from PySide6.QtWidgets import QApplication

from lacis import __version__
from lacis.application import (
    APPLICATION_NAME,
    ORGANIZATION_NAME,
    configure_application,
    create_application,
    main,
)


def test_the_application_has_its_name_organisation_and_version(qapp: QApplication) -> None:
    configure_application(qapp)
    assert qapp.applicationName() == APPLICATION_NAME
    assert qapp.applicationDisplayName() == APPLICATION_NAME
    assert qapp.organizationName() == ORGANIZATION_NAME
    assert qapp.applicationVersion() == __version__


def test_the_application_speaks_french(qapp: QApplication) -> None:
    configure_application(qapp)
    assert QLocale().language() == QLocale.Language.French
    assert QLocale().territory() == QLocale.Country.France


def test_creating_the_application_reuses_the_running_one(qapp: QApplication) -> None:
    assert create_application(["lacis"]) is qapp


def test_the_version_option_prints_the_version_and_exits(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_information:
        main(["lacis", "--version"])
    assert exit_information.value.code == 0
    assert capsys.readouterr().out.strip() == f"Lacis {__version__}"


def test_python_m_lacis_runs_the_same_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["lacis", "--version"])
    with pytest.raises(SystemExit) as exit_information:
        runpy.run_module("lacis", run_name="__main__")
    assert exit_information.value.code == 0
    assert capsys.readouterr().out.strip() == f"Lacis {__version__}"


def test_an_unknown_option_is_refused(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_information:
        main(["lacis", "--unknown"])
    assert exit_information.value.code == 2
    assert "--unknown" in capsys.readouterr().err


def test_the_command_without_option_starts_the_application(qapp: QApplication) -> None:
    assert main(["lacis"]) == 0
    assert qapp.applicationName() == APPLICATION_NAME
