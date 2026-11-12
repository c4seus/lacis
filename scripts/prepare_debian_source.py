import os
import re
import shutil
import sys
from datetime import UTC, datetime
from email.utils import format_datetime
from pathlib import Path

RECIPE_DIRECTORY = Path("packaging/debian")
SOURCE_DIRECTORY = Path("debian")
MAINTAINER = "c4seus <c4seus@proton.me>"
RELEASES_URL = "https://github.com/c4seus/lacis/releases"
PRE_RELEASE = re.compile(r"(?<=\d)\.?(dev|a|b|rc)(?=\d)")
VERSION_PATTERN = re.compile(r"\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?(\+[\w.]+)?")
USAGE = "usage: python scripts/prepare_debian_source.py VERSION"
INVALID_VERSION_HINT = (
    "the version comes from `python3 -m hatchling version`, which needs the Debian packages "
    "python3-hatchling and python3-hatch-vcs: run it with the system Python, outside any "
    "virtual environment"
)


def debian_version(version: str) -> str:
    public, separator, local = version.partition("+")
    return PRE_RELEASE.sub(lambda match: f"~{match.group(1)}", public) + separator + local


def build_date(environment: dict[str, str]) -> datetime:
    epoch = environment.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), UTC)
    return datetime.now(UTC)


def changelog(version: str, date: datetime) -> str:
    return (
        f"lacis ({debian_version(version)}) unstable; urgency=medium\n"
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
    return source


def main(root: Path, arguments: list[str], environment: dict[str, str]) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    version = arguments[0].removeprefix("v")
    if not VERSION_PATTERN.fullmatch(version):
        print(f"invalid version {version!r}: {INVALID_VERSION_HINT}")
        return 2
    source = prepare(root, version, build_date(environment))
    print(f"{source.relative_to(root).as_posix()}: lacis {debian_version(version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:], dict(os.environ)))
