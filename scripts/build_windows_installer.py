import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

from lacis.product import APPLICATION_ID, PRODUCT_DESCRIPTION, PRODUCT_NAME, REPOSITORY_URL
from package_versions import is_valid_version

PUBLISHER = "c4seus"
COPYRIGHT = f"Copyright (C) {PUBLISHER}, GPL-3.0-or-later"
EXECUTABLE_NAME = "lacis"
PACKAGE_DIRECTORY = Path("src/lacis")
BUILD_DIRECTORY = Path("build/windows")
OUTPUT_DIRECTORY = Path("dist")
INSTALLER_SCRIPT = Path("packaging/windows/lacis.iss")
ICON = Path("packaging/windows/lacis.ico")
INNO_SETUP_DIRECTORY = Path("Inno Setup 7")
INNO_SETUP_COMPILER = "ISCC.exe"
INSTALLATION_ROOTS = (
    ("LOCALAPPDATA", "Programs"),
    ("ProgramFiles", ""),
    ("ProgramFiles(x86)", ""),
)
WINDOWS_VERSION_PARTS = 4
USAGE = "usage: python scripts/build_windows_installer.py VERSION"
INVALID_VERSION_HINT = (
    'the version comes from `python -c "import lacis; print(lacis.__version__)"`, once '
    "Lacis is installed with `pip install -e .[windows-installer]`"
)
MISSING_COMPILER_HINT = (
    "Inno Setup 7 is missing: install it from https://jrsoftware.org/isdl.php, for the "
    "current user or for all users, then run this command again"
)

type CommandRunner = Callable[[list[str]], None]


def windows_version(version: str) -> str:
    release = re.split(r"[^\d.]", version, maxsplit=1)[0].rstrip(".")
    numbers = release.split(".")[:WINDOWS_VERSION_PARTS]
    return ".".join(numbers + ["0"] * (WINDOWS_VERSION_PARTS - len(numbers)))


def installer_name(version: str) -> str:
    return f"lacis-{version}-windows-x64-setup"


def distribution_directory(root: Path) -> Path:
    return root / BUILD_DIRECTORY / f"{EXECUTABLE_NAME}.dist"


def inno_setup_compiler(environment: Mapping[str, str]) -> Path | None:
    for variable, subdirectory in INSTALLATION_ROOTS:
        base = environment.get(variable)
        if not base:
            continue
        candidate = Path(base) / subdirectory / INNO_SETUP_DIRECTORY / INNO_SETUP_COMPILER
        if candidate.is_file():
            return candidate
    return None


def nuitka_command(root: Path, version: str) -> list[str]:
    file_version = windows_version(version)
    return [
        sys.executable,
        "-m",
        "nuitka",
        "--mode=standalone",
        "--python-flag=-m",
        "--enable-plugin=pyside6",
        "--include-package-data=lacis",
        "--include-distribution-metadata=lacis",
        "--windows-console-mode=attach",
        f"--windows-icon-from-ico={root / ICON}",
        f"--company-name={PUBLISHER}",
        f"--product-name={PRODUCT_NAME}",
        f"--file-description={PRODUCT_NAME}",
        f"--file-version={file_version}",
        f"--product-version={file_version}",
        f"--copyright={COPYRIGHT}",
        f"--output-filename={EXECUTABLE_NAME}",
        f"--output-folder-name={EXECUTABLE_NAME}",
        f"--output-dir={root / BUILD_DIRECTORY}",
        "--assume-yes-for-downloads",
        str(root / PACKAGE_DIRECTORY),
    ]


def inno_setup_command(compiler: Path, root: Path, version: str) -> list[str]:
    return [
        str(compiler),
        f"/DAppId={APPLICATION_ID}",
        f"/DAppName={PRODUCT_NAME}",
        f"/DAppDescription={PRODUCT_DESCRIPTION}",
        f"/DAppPublisher={PUBLISHER}",
        f"/DAppUrl={REPOSITORY_URL}",
        f"/DAppVersion={version}",
        f"/DAppExecutable={EXECUTABLE_NAME}.exe",
        f"/DWindowsVersion={windows_version(version)}",
        f"/DSourceDirectory={distribution_directory(root)}",
        f"/O{root / OUTPUT_DIRECTORY}",
        f"/F{installer_name(version)}",
        str(root / INSTALLER_SCRIPT),
    ]


def build(root: Path, version: str, compiler: Path, run_command: CommandRunner) -> Path:
    run_command(nuitka_command(root, version))
    run_command(inno_setup_command(compiler, root, version))
    return root / OUTPUT_DIRECTORY / f"{installer_name(version)}.exe"


def run_checked(command: list[str]) -> None:
    subprocess.run(command, check=True)


def main(
    root: Path,
    arguments: list[str],
    environment: Mapping[str, str],
    run_command: CommandRunner,
) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    version = arguments[0].removeprefix("v")
    if not is_valid_version(version):
        print(f"invalid version {version!r}: {INVALID_VERSION_HINT}")
        return 2
    compiler = inno_setup_compiler(environment)
    if compiler is None:
        print(MISSING_COMPILER_HINT)
        return 2
    installer = build(root, version, compiler, run_command)
    print(f"{installer.relative_to(root).as_posix()}: lacis {version}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:], os.environ, run_checked))
