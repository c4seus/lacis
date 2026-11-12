import re
import sys
import tomllib
from pathlib import Path

import pytest

from build_windows_installer import (
    ICON,
    INNO_SETUP_COMPILER,
    INNO_SETUP_DIRECTORY,
    INSTALLER_SCRIPT,
    build,
    distribution_directory,
    inno_setup_command,
    inno_setup_compiler,
    installer_name,
    main,
    nuitka_command,
    windows_version,
)
from lacis.product import APPLICATION_ID, PRODUCT_DESCRIPTION, PRODUCT_NAME, REPOSITORY_URL

REPOSITORY = Path(__file__).resolve().parent.parent
WORKFLOW = REPOSITORY / ".github" / "workflows" / "windows-installer.yml"
COMPILER = Path("C:/Users/c4seus/AppData/Local/Programs/Inno Setup 7/ISCC.exe")
INNO_SETUP_DEFINE = re.compile(r"\{#(\w+)\}")


class RecordedCommands:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str]) -> None:
        self.commands.append(command)


def defines(command: list[str]) -> dict[str, str]:
    pairs = [argument[2:].partition("=") for argument in command if argument.startswith("/D")]
    return {name: value for name, _, value in pairs}


def installed_compiler(base: Path) -> Path:
    compiler = base / INNO_SETUP_DIRECTORY / INNO_SETUP_COMPILER
    compiler.parent.mkdir(parents=True)
    compiler.write_bytes(b"")
    return compiler


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.1.0", "0.1.0.0"),
        ("1.2", "1.2.0.0"),
        ("0.1.0rc1", "0.1.0.0"),
        ("1.2.0.post1", "1.2.0.0"),
        ("0.1.dev67+g1a2b3c4.d20261112", "0.1.0.0"),
        ("1.2.3.4.5", "1.2.3.4"),
    ],
)
def test_the_windows_version_keeps_the_four_numbers_of_the_release(
    version: str, expected: str
) -> None:
    assert windows_version(version) == expected


def test_the_installer_is_named_after_the_python_version() -> None:
    assert installer_name("0.1.0rc1") == "lacis-0.1.0rc1-windows-x64-setup"


def test_inno_setup_installed_for_the_current_user_comes_first(tmp_path: Path) -> None:
    for_the_user = installed_compiler(tmp_path / "local" / "Programs")
    installed_compiler(tmp_path / "program-files")
    environment = {
        "LOCALAPPDATA": str(tmp_path / "local"),
        "ProgramFiles": str(tmp_path / "program-files"),
    }
    assert inno_setup_compiler(environment) == for_the_user


def test_inno_setup_installed_for_all_users_is_found(tmp_path: Path) -> None:
    for_all_users = installed_compiler(tmp_path / "program-files-x86")
    environment = {
        "LOCALAPPDATA": str(tmp_path / "local"),
        "ProgramFiles": "",
        "ProgramFiles(x86)": str(tmp_path / "program-files-x86"),
    }
    assert inno_setup_compiler(environment) == for_all_users


def test_no_compiler_is_found_without_inno_setup_7(tmp_path: Path) -> None:
    (tmp_path / "Inno Setup 6").mkdir()
    (tmp_path / "Inno Setup 6" / INNO_SETUP_COMPILER).write_bytes(b"")
    assert inno_setup_compiler({"ProgramFiles": str(tmp_path)}) is None
    assert inno_setup_compiler({}) is None


def test_nuitka_compiles_the_package_with_its_data_and_metadata() -> None:
    command = nuitka_command(REPOSITORY, "0.1.0rc1")
    assert command[:3] == [sys.executable, "-m", "nuitka"]
    assert command[-1] == str(REPOSITORY / "src" / "lacis")
    for option in [
        "--mode=standalone",
        "--python-flag=-m",
        "--enable-plugin=pyside6",
        "--include-package-data=lacis",
        "--include-distribution-metadata=lacis",
        "--windows-console-mode=attach",
        "--file-version=0.1.0.0",
        f"--product-name={PRODUCT_NAME}",
        "--output-filename=lacis",
        "--output-folder-name=lacis",
        f"--windows-icon-from-ico={REPOSITORY / ICON}",
    ]:
        assert option in command
    assert (REPOSITORY / ICON).is_file()


def test_inno_setup_gets_the_product_from_lacis_and_the_compiled_folder() -> None:
    command = inno_setup_command(COMPILER, REPOSITORY, "0.1.0rc1")
    assert command[0] == str(COMPILER)
    assert command[-1] == str(REPOSITORY / INSTALLER_SCRIPT)
    assert defines(command) == {
        "AppId": APPLICATION_ID,
        "AppName": PRODUCT_NAME,
        "AppDescription": PRODUCT_DESCRIPTION,
        "AppPublisher": "c4seus",
        "AppUrl": REPOSITORY_URL,
        "AppVersion": "0.1.0rc1",
        "AppExecutable": "lacis.exe",
        "WindowsVersion": "0.1.0.0",
        "SourceDirectory": str(REPOSITORY / "build" / "windows" / "lacis.dist"),
    }
    assert f"/O{REPOSITORY / 'dist'}" in command
    assert "/Flacis-0.1.0rc1-windows-x64-setup" in command


def test_every_value_that_the_installer_script_uses_is_defined() -> None:
    script = (REPOSITORY / INSTALLER_SCRIPT).read_text(encoding="utf-8")
    used = set(INNO_SETUP_DEFINE.findall(script))
    assert used == set(defines(inno_setup_command(COMPILER, REPOSITORY, "0.1.0")))
    assert "PrivilegesRequired=lowest\n" in script
    assert 'MessagesFile: "compiler:Languages\\French.isl"' in script


def test_the_installer_script_keeps_the_data_of_the_user() -> None:
    script = (REPOSITORY / INSTALLER_SCRIPT).read_text(encoding="utf-8")
    assert "[UninstallDelete]" not in script
    assert "{localappdata}" not in script.lower()


def test_the_build_compiles_then_wraps_the_compiled_folder(tmp_path: Path) -> None:
    recorded = RecordedCommands()
    installer = build(tmp_path, "0.1.0", COMPILER, recorded)
    assert installer == tmp_path / "dist" / "lacis-0.1.0-windows-x64-setup.exe"
    assert recorded.commands == [
        nuitka_command(tmp_path, "0.1.0"),
        inno_setup_command(COMPILER, tmp_path, "0.1.0"),
    ]
    assert distribution_directory(tmp_path) == tmp_path / "build" / "windows" / "lacis.dist"


def test_the_command_builds_the_installer_with_or_without_the_v(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    installed_compiler(tmp_path / "Programs")
    recorded = RecordedCommands()
    assert main(tmp_path, ["v0.1.0"], {"LOCALAPPDATA": str(tmp_path)}, recorded) == 0
    assert capsys.readouterr().out == "dist/lacis-0.1.0-windows-x64-setup.exe: lacis 0.1.0\n"
    assert len(recorded.commands) == 2


def test_the_command_stops_before_compiling_on_a_wrong_setup(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    recorded = RecordedCommands()
    assert main(tmp_path, [], {}, recorded) == 2
    assert capsys.readouterr().out.startswith("usage:")
    assert main(tmp_path, [""], {}, recorded) == 2
    assert "pip install -e .[windows-installer]" in capsys.readouterr().out
    assert main(tmp_path, ["0.1.0"], {"LOCALAPPDATA": str(tmp_path)}, recorded) == 2
    assert capsys.readouterr().out.startswith("Inno Setup 7 is missing")
    assert recorded.commands == []


def test_the_windows_build_uses_the_inno_setup_version_that_the_script_looks_for() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    pinned = re.search(r'INNO_SETUP_VERSION: "(\d+)\.\d+\.\d+"', workflow)
    assert pinned is not None
    assert Path(f"Inno Setup {pinned.group(1)}") == INNO_SETUP_DIRECTORY
    assert re.search(r"INNO_SETUP_SHA256: [0-9a-f]{64}\n", workflow)


def test_the_windows_build_installs_nuitka_with_lacis() -> None:
    project = tomllib.loads((REPOSITORY / "pyproject.toml").read_text(encoding="utf-8"))
    requirements = project["project"]["optional-dependencies"]["windows-installer"]
    assert [requirement for requirement in requirements if requirement.startswith("nuitka")]
    assert '-e ".[windows-installer]"' in WORKFLOW.read_text(encoding="utf-8")
