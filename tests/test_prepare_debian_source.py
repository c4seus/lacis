import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from prepare_debian_source import (
    RECIPE_DIRECTORY,
    build_date,
    changelog,
    debian_version,
    main,
    prepare,
)

REPOSITORY = Path(__file__).resolve().parent.parent
RELEASED_AT = datetime(2026, 11, 12, 16, 0, tzinfo=UTC)
QT_MODULE = re.compile(r"^(?:from|import) PySide6\.Qt(\w+)", re.MULTILINE)


def test_python_versions_become_debian_versions_that_sort_the_same_way() -> None:
    assert debian_version("0.1.0") == "0.1.0"
    assert debian_version("0.1.0rc1") == "0.1.0~rc1"
    assert debian_version("1.0.0a2") == "1.0.0~a2"
    assert debian_version("1.0.0b1") == "1.0.0~b1"
    assert debian_version("0.1.dev67+g1a2b3c4") == "0.1~dev67+g1a2b3c4"
    assert debian_version("0.1.dev67+g1a2b3c4.d20261112") == "0.1~dev67+g1a2b3c4.d20261112"
    assert debian_version("1.2.0.post1") == "1.2.0.post1"


def test_the_changelog_names_the_version_and_the_date() -> None:
    assert changelog("0.1.0", RELEASED_AT) == (
        "lacis (0.1.0) unstable; urgency=medium\n"
        "\n"
        "  * Lacis 0.1.0, described in the release notes at\n"
        "    https://github.com/c4seus/lacis/releases\n"
        "\n"
        " -- c4seus <c4seus@proton.me>  Thu, 12 Nov 2026 16:00:00 +0000\n"
    )
    long_version = changelog("0.1.dev67+g1a2b3c4.d20261112", RELEASED_AT).splitlines()
    assert max(len(line) for line in long_version) <= 80


def test_the_build_date_follows_source_date_epoch() -> None:
    assert build_date({"SOURCE_DATE_EPOCH": "1794499200"}) == datetime(
        2026, 11, 12, 16, 0, tzinfo=UTC
    )
    assert build_date({}).tzinfo is UTC


def test_the_source_directory_is_the_recipe_with_its_changelog(tmp_path: Path) -> None:
    (tmp_path / RECIPE_DIRECTORY).mkdir(parents=True)
    (tmp_path / RECIPE_DIRECTORY / "control").write_text("Source: lacis\n", encoding="utf-8")
    (tmp_path / "debian").mkdir()
    (tmp_path / "debian" / "stale").write_text("", encoding="utf-8")
    source = prepare(tmp_path, "0.1.0", RELEASED_AT)
    assert sorted(path.name for path in source.iterdir()) == ["changelog", "control"]
    assert (source / "changelog").read_text(encoding="utf-8").startswith("lacis (0.1.0)")


def test_the_command_takes_the_version_with_or_without_its_v(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / RECIPE_DIRECTORY).mkdir(parents=True)
    assert main(tmp_path, ["v0.1.0rc1"], {"SOURCE_DATE_EPOCH": "0"}) == 0
    assert capsys.readouterr().out == "debian: lacis 0.1.0~rc1\n"
    assert main(tmp_path, [], {}) == 2
    assert capsys.readouterr().out.startswith("usage:")


@pytest.mark.parametrize("version", ["", "unknown", "v", "0.1.0 ", "0.1.0-1"])
def test_an_invalid_version_stops_before_writing_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], version: str
) -> None:
    (tmp_path / RECIPE_DIRECTORY).mkdir(parents=True)
    assert main(tmp_path, [version], {}) == 2
    assert not (tmp_path / "debian").exists()
    message = capsys.readouterr().out
    assert message.startswith("invalid version ")
    assert "python3-hatchling and python3-hatch-vcs" in message


@pytest.mark.parametrize(
    "version",
    ["0.1.0", "v1.0.0", "0.1.0rc1", "1.2.0.post1", "0.1.dev67+g1a2b3c4.d20261112"],
)
def test_every_version_hatchling_gives_is_accepted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], version: str
) -> None:
    (tmp_path / RECIPE_DIRECTORY).mkdir(parents=True)
    assert main(tmp_path, [version], {"SOURCE_DATE_EPOCH": "0"}) == 0
    assert (tmp_path / "debian" / "changelog").is_file()


def imported_qt_modules(*directories: str) -> set[str]:
    return {
        module.lower()
        for directory in directories
        for path in (REPOSITORY / directory).rglob("*.py")
        for module in QT_MODULE.findall(path.read_text(encoding="utf-8"))
    }


def test_the_package_depends_on_every_qt_module_that_lacis_imports() -> None:
    imported = imported_qt_modules("src")
    control = (REPOSITORY / RECIPE_DIRECTORY / "control").read_text(encoding="utf-8")
    declared = set(re.findall(r"python3-pyside6\.qt(\w+) \(>= 6\.8\)", control))
    assert imported == declared == {"core", "gui", "svg", "widgets"}
    assert "python3-httpx" in control


def test_the_debian_tests_install_every_qt_module_that_the_tests_import() -> None:
    control = (REPOSITORY / RECIPE_DIRECTORY / "control").read_text(encoding="utf-8")
    workflow = (REPOSITORY / ".github" / "workflows" / "debian-package.yml").read_text(
        encoding="utf-8"
    )
    installed = set(re.findall(r"python3-pyside6\.qt(\w+)", control + workflow))
    assert imported_qt_modules("tests", "scripts") <= installed
    assert "test" in installed
