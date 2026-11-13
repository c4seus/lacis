import hashlib
import re
from pathlib import Path

import pytest

from prepare_arch_package import (
    ARCH_DIRECTORY,
    PKGBUILD_TEMPLATE,
    main,
    pkgbuild,
    prepare,
    sha256_of,
    source_archive_name,
)
from qt_imports import imported_qt_modules

REPOSITORY = Path(__file__).resolve().parent.parent
WORKFLOW = REPOSITORY / ".github" / "workflows" / "arch-package.yml"
QT6_BASE_MODULES = {
    "concurrent",
    "core",
    "dbus",
    "gui",
    "network",
    "opengl",
    "openglwidgets",
    "printsupport",
    "sql",
    "test",
    "widgets",
    "xml",
}
ARCHIVE_CONTENT = b"fictitious source archive"


def template() -> str:
    return (REPOSITORY / PKGBUILD_TEMPLATE).read_text(encoding="utf-8")


def pkgbuild_array(name: str) -> list[str]:
    found = re.search(rf"^{name}=\(([^)]*)\)$", template(), re.MULTILINE)
    assert found is not None
    return re.findall(r"'([^']+)'", found.group(1))


def qt6_packages(modules: set[str]) -> set[str]:
    return {f"qt6-{module}" for module in modules - QT6_BASE_MODULES}


def workflow_jobs() -> tuple[str, str]:
    build, install = WORKFLOW.read_text(encoding="utf-8").split("\n  install:\n", 1)
    return build, install


def fake_archive_builder(root: Path, directory: Path, version: str) -> None:
    (directory / source_archive_name(version)).write_bytes(ARCHIVE_CONTENT)


def write_template(root: Path, content: str) -> None:
    (root / PKGBUILD_TEMPLATE).parent.mkdir(parents=True)
    (root / PKGBUILD_TEMPLATE).write_text(content, encoding="utf-8")


def test_the_source_archive_is_named_after_the_python_version() -> None:
    assert source_archive_name("0.1.0rc1") == "lacis-0.1.0rc1.tar.gz"


def test_the_checksum_is_the_sha256_of_the_file(tmp_path: Path) -> None:
    archive = tmp_path / "lacis-0.1.0.tar.gz"
    archive.write_bytes(ARCHIVE_CONTENT)
    assert sha256_of(archive) == hashlib.sha256(ARCHIVE_CONTENT).hexdigest()


def test_the_pkgbuild_gets_the_python_version_and_the_checksum_of_the_archive() -> None:
    written = pkgbuild(template(), "0.1.0rc1", "0" * 64)
    assert re.search(r"^pkgver=0\.1\.0rc1$", written, re.MULTILINE)
    assert f"sha256sums=('{'0' * 64}')" in written
    assert 'source=("lacis-$pkgver.tar.gz")' in written
    assert "@" not in written


def test_the_package_directory_holds_only_the_archive_and_the_pkgbuild(tmp_path: Path) -> None:
    write_template(tmp_path, "pkgver=@PKGVER@\nsha256sums=('@SHA256@')\n")
    (tmp_path / ARCH_DIRECTORY / "pkg").mkdir(parents=True)
    target = prepare(tmp_path, "0.1.0", fake_archive_builder)
    assert target == tmp_path / ARCH_DIRECTORY / "PKGBUILD"
    assert sorted(path.name for path in target.parent.iterdir()) == [
        "PKGBUILD",
        "lacis-0.1.0.tar.gz",
    ]
    checksum = hashlib.sha256(ARCHIVE_CONTENT).hexdigest()
    assert target.read_text(encoding="utf-8") == f"pkgver=0.1.0\nsha256sums=('{checksum}')\n"


def test_the_command_takes_the_version_with_or_without_its_v(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_template(tmp_path, "pkgver=@PKGVER@\n")
    assert main(tmp_path, ["v0.1.0rc1"], fake_archive_builder) == 0
    assert capsys.readouterr().out == "build/arch/PKGBUILD: lacis 0.1.0rc1\n"
    assert (tmp_path / ARCH_DIRECTORY / "lacis-0.1.0rc1.tar.gz").is_file()


def test_an_invalid_version_stops_before_building_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_template(tmp_path, "pkgver=@PKGVER@\n")
    assert main(tmp_path, [""], fake_archive_builder) == 2
    assert "python-hatchling and python-hatch-vcs" in capsys.readouterr().out
    assert main(tmp_path, [], fake_archive_builder) == 2
    assert capsys.readouterr().out.startswith("usage:")
    assert not (tmp_path / ARCH_DIRECTORY).exists()


def test_the_package_depends_on_every_qt_module_that_lacis_imports() -> None:
    depends = pkgbuild_array("depends")
    needed = qt6_packages(imported_qt_modules("src"))
    assert needed == {"qt6-svg"}
    assert needed <= set(depends)
    assert {"pyside6", "python", "python-httpx", "hicolor-icon-theme"} <= set(depends)


def test_the_arch_tests_install_every_qt_module_that_the_tests_import() -> None:
    install_job = workflow_jobs()[1]
    needed = qt6_packages(imported_qt_modules("tests", "scripts"))
    assert [
        package
        for package in needed
        if package not in pkgbuild_array("depends") and package not in install_job
    ] == []


def test_the_arch_build_installs_every_dependency_of_the_package() -> None:
    build = workflow_jobs()[0]
    required = pkgbuild_array("depends") + pkgbuild_array("makedepends")
    assert required
    assert [name for name in required if not re.search(rf"\s{re.escape(name)}(\s|$)", build)] == []
