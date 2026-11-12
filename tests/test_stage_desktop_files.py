from pathlib import Path

import pytest

from lacis.product import APPLICATION_ID
from stage_desktop_files import APPLICATION_ID as STAGED_APPLICATION_ID
from stage_desktop_files import main, stage, staged_files

REPOSITORY = Path(__file__).resolve().parent.parent


def test_the_staged_files_use_the_application_id() -> None:
    assert STAGED_APPLICATION_ID == APPLICATION_ID


def test_the_desktop_files_land_where_desktops_look_for_them(tmp_path: Path) -> None:
    staged = {target.as_posix() for target in stage(REPOSITORY, tmp_path)}
    assert {
        "usr/share/applications/io.github.c4seus.lacis.desktop",
        "usr/share/metainfo/io.github.c4seus.lacis.metainfo.xml",
        "usr/share/icons/hicolor/16x16/apps/io.github.c4seus.lacis.png",
        "usr/share/icons/hicolor/512x512/apps/io.github.c4seus.lacis.png",
        "usr/share/icons/hicolor/scalable/apps/io.github.c4seus.lacis.svg",
    } <= staged
    assert len(staged) == len(staged_files(REPOSITORY)) == 11
    assert all((tmp_path / target).is_file() for target in staged)


def test_the_command_stages_into_its_destination(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(REPOSITORY, [str(tmp_path)]) == 0
    assert "usr/share/applications/io.github.c4seus.lacis.desktop" in capsys.readouterr().out
    assert main(REPOSITORY, []) == 2
    assert capsys.readouterr().out.startswith("usage:")
