import fnmatch
import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from prepare_rpm_spec import (
    RPM_DIRECTORY,
    SPEC_NAME,
    SPEC_TEMPLATE,
    changelog,
    changelog_date,
    main,
    prepare,
    spec,
)
from stage_desktop_files import staged_files

REPOSITORY = Path(__file__).resolve().parent.parent
RELEASED_AT = datetime(2026, 11, 12, 16, 0, tzinfo=UTC)
FEDORA_MACROS = {
    "%{_bindir}": "usr/bin",
    "%{_datadir}": "usr/share",
    "%{_metainfodir}": "usr/share/metainfo",
    "%{_mandir}": "usr/share/man",
}


def expand_macros(line: str) -> str:
    for macro, directory in FEDORA_MACROS.items():
        line = line.replace(macro, directory)
    return line


def template() -> str:
    return (REPOSITORY / SPEC_TEMPLATE).read_text(encoding="utf-8")


def test_the_changelog_date_is_written_in_english_whatever_the_locale() -> None:
    assert changelog_date(RELEASED_AT) == "Thu Nov 12 2026"
    assert changelog_date(datetime(2027, 1, 4, tzinfo=UTC)) == "Mon Jan 04 2027"


def test_the_changelog_names_the_version_and_its_release() -> None:
    assert changelog("0.1.dev67+g1a2b3c4", RELEASED_AT) == (
        "* Thu Nov 12 2026 c4seus <c4seus@proton.me> - 0.1~dev67+g1a2b3c4-1\n"
        "- Lacis 0.1.dev67+g1a2b3c4, described in the release notes at\n"
        "  https://github.com/c4seus/lacis/releases"
    )


def test_the_spec_gets_the_rpm_version_and_builds_the_python_version() -> None:
    written = spec(template(), "0.1.0rc1", RELEASED_AT)
    assert re.search(r"^Version: +0\.1\.0~rc1$", written, re.MULTILINE)
    assert "export SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0rc1\n" in written
    assert written.rstrip().endswith("https://github.com/c4seus/lacis/releases")
    assert "@" not in written.replace("c4seus@proton.me", "")


def test_the_spec_is_written_in_a_clean_build_directory(tmp_path: Path) -> None:
    (tmp_path / SPEC_TEMPLATE).parent.mkdir(parents=True)
    (tmp_path / SPEC_TEMPLATE).write_text("Version: @VERSION@\n", encoding="utf-8")
    (tmp_path / RPM_DIRECTORY / "RPMS").mkdir(parents=True)
    target = prepare(tmp_path, "0.1.0", RELEASED_AT)
    assert target == tmp_path / RPM_DIRECTORY / SPEC_NAME
    assert [path.name for path in target.parent.iterdir()] == [SPEC_NAME]
    assert target.read_text(encoding="utf-8") == "Version: 0.1.0\n"


def test_the_command_checks_the_version_before_writing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / SPEC_TEMPLATE).parent.mkdir(parents=True)
    (tmp_path / SPEC_TEMPLATE).write_text("@VERSION@", encoding="utf-8")
    assert main(tmp_path, ["v0.1.0rc1"], {"SOURCE_DATE_EPOCH": "0"}) == 0
    assert capsys.readouterr().out == "build/rpm/lacis.spec: lacis 0.1.0~rc1\n"
    assert main(tmp_path, [""], {}) == 2
    assert "python3-hatchling and python3-hatch-vcs" in capsys.readouterr().out
    assert main(tmp_path, [], {}) == 2
    assert capsys.readouterr().out.startswith("usage:")


def test_the_package_depends_on_the_pyside6_of_fedora_instead_of_the_wheel() -> None:
    lines = template().splitlines()
    assert "Requires:       python3dist(pyside6) >= 6.8" in lines
    assert lines[0] == r"%global __requires_exclude ^python3\\.[0-9]+dist\\(pyside6-essentials\\)"


def test_the_fedora_build_installs_every_build_requirement() -> None:
    workflow = (REPOSITORY / ".github" / "workflows" / "fedora-package.yml").read_text(
        encoding="utf-8"
    )
    required = re.findall(r"^BuildRequires: +(\S+)$", template(), re.MULTILINE)
    assert required
    assert [name for name in required if name not in workflow] == []


def test_every_staged_file_is_listed_in_the_files_of_the_package() -> None:
    listed = template().split("%files\n", 1)[1].split("%changelog", 1)[0].splitlines()
    expanded = [expand_macros(line) for line in listed]
    patterns = [line.rstrip("*") + "*" for line in expanded if line.startswith("usr/")]
    staged = [target.as_posix() for target in staged_files(REPOSITORY).values()]
    assert [
        target
        for target in staged
        if not any(fnmatch.fnmatch(target, pattern) for pattern in patterns)
    ] == []
