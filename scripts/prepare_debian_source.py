import os
import shutil
import sys
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path

from package_versions import (
    MAINTAINER,
    RELEASES_URL,
    build_date,
    is_valid_version,
    package_version,
)

RECIPE_DIRECTORY = Path("packaging/debian")
PYTHON_VERSION_PLACEHOLDER = "@PYTHON_VERSION@"
SOURCE_DIRECTORY = Path("debian")
USAGE = "usage: python scripts/prepare_debian_source.py VERSION"
INVALID_VERSION_HINT = (
    "the version comes from `python3 -m hatchling version`, which needs the Debian packages "
    "python3-hatchling and python3-hatch-vcs: run it with the system Python, outside any "
    "virtual environment"
)


def changelog(version: str, date: datetime) -> str:
    return (
        f"lacis ({package_version(version)}) unstable; urgency=medium\n"
        "\n"
        f"  * Lacis {version}, described in the release notes at\n"
        f"    {RELEASES_URL}\n"
        "\n"
        f" -- {MAINTAINER}  {format_datetime(date)}\n"
    )


def prepare(root: Path, version: str, date: datetime) -> Path:
    source = root / SOURCE_DIRECTORY
    if source.exists():
        shutil.rmtree(source)
    shutil.copytree(root / RECIPE_DIRECTORY, source)
    (source / "changelog").write_text(changelog(version, date), encoding="utf-8")
    rules = source / "rules"
    recipe = rules.read_text(encoding="utf-8")
    rules.write_text(recipe.replace(PYTHON_VERSION_PLACEHOLDER, version), encoding="utf-8")
    return source


def main(root: Path, arguments: list[str], environment: dict[str, str]) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    version = arguments[0].removeprefix("v")
    if not is_valid_version(version):
        print(f"invalid version {version!r}: {INVALID_VERSION_HINT}")
        return 2
    source = prepare(root, version, build_date(environment))
    print(f"{source.relative_to(root).as_posix()}: lacis {package_version(version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:], dict(os.environ)))
