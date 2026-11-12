import hashlib
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from package_versions import is_valid_version

PKGBUILD_TEMPLATE = Path("packaging/arch/PKGBUILD.in")
ARCH_DIRECTORY = Path("build/arch")
USAGE = "usage: python scripts/prepare_arch_package.py VERSION"
INVALID_VERSION_HINT = (
    "the version comes from `python -m hatchling version`, which needs the Arch Linux "
    "packages python-hatchling and python-hatch-vcs: run it with the system Python, outside "
    "any virtual environment"
)

type ArchiveBuilder = Callable[[Path, Path, str], None]


def source_archive_name(version: str) -> str:
    return f"lacis-{version}.tar.gz"


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pkgbuild(template: str, version: str, checksum: str) -> str:
    return template.replace("@PKGVER@", version).replace("@SHA256@", checksum)


def build_source_archive(root: Path, directory: Path, version: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", directory, root],
        check=True,
        env={**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": version},
    )


def prepare(root: Path, version: str, build_archive: ArchiveBuilder) -> Path:
    directory = root / ARCH_DIRECTORY
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    build_archive(root, directory, version)
    checksum = sha256_of(directory / source_archive_name(version))
    template = (root / PKGBUILD_TEMPLATE).read_text(encoding="utf-8")
    target = directory / "PKGBUILD"
    target.write_text(pkgbuild(template, version, checksum), encoding="utf-8")
    return target


def main(root: Path, arguments: list[str], build_archive: ArchiveBuilder) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    version = arguments[0].removeprefix("v")
    if not is_valid_version(version):
        print(f"invalid version {version!r}: {INVALID_VERSION_HINT}")
        return 2
    target = prepare(root, version, build_archive)
    print(f"{target.relative_to(root).as_posix()}: lacis {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:], build_source_archive))
