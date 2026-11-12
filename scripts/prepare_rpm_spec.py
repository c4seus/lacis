import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from package_versions import (
    MAINTAINER,
    RELEASES_URL,
    build_date,
    is_valid_version,
    package_version,
)

SPEC_TEMPLATE = Path("packaging/fedora/lacis.spec.in")
RPM_DIRECTORY = Path("build/rpm")
SPEC_NAME = "lacis.spec"
RELEASE = "1"
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
USAGE = "usage: python scripts/prepare_rpm_spec.py VERSION"
INVALID_VERSION_HINT = (
    "the version comes from `python3 -m hatchling version`, which needs the Fedora packages "
    "python3-hatchling and python3-hatch-vcs: run it with the system Python, outside any "
    "virtual environment"
)


def changelog_date(date: datetime) -> str:
    return f"{WEEKDAYS[date.weekday()]} {MONTHS[date.month - 1]} {date.day:02d} {date.year}"


def changelog(version: str, date: datetime) -> str:
    return (
        f"* {changelog_date(date)} {MAINTAINER} - {package_version(version)}-{RELEASE}\n"
        f"- Lacis {version}, described in the release notes at\n"
        f"  {RELEASES_URL}"
    )


def spec(template: str, version: str, date: datetime) -> str:
    return (
        template.replace("@VERSION@", package_version(version))
        .replace("@PYTHON_VERSION@", version)
        .replace("@CHANGELOG@", changelog(version, date))
    )


def prepare(root: Path, version: str, date: datetime) -> Path:
    directory = root / RPM_DIRECTORY
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    template = (root / SPEC_TEMPLATE).read_text(encoding="utf-8")
    target = directory / SPEC_NAME
    target.write_text(spec(template, version, date), encoding="utf-8")
    return target


def main(root: Path, arguments: list[str], environment: dict[str, str]) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    version = arguments[0].removeprefix("v")
    if not is_valid_version(version):
        print(f"invalid version {version!r}: {INVALID_VERSION_HINT}")
        return 2
    target = prepare(root, version, build_date(environment))
    print(f"{target.relative_to(root).as_posix()}: lacis {package_version(version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:], dict(os.environ)))
