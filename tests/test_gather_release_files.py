import hashlib
from pathlib import Path

import pytest

from gather_release_files import gather, main, package_files, served_name

PACKAGES = {
    "debian-package": "lacis_0.2.0~rc1_all.deb",
    "fedora-45-package": "lacis-0.2.0~rc1-1.fc45.noarch.rpm",
    "source-archive": "lacis-0.2.0rc1.tar.gz",
}


def artifacts(root: Path, packages: dict[str, str] = PACKAGES) -> Path:
    for artifact, name in packages.items():
        (root / "artifacts" / artifact).mkdir(parents=True)
        (root / "artifacts" / artifact / name).write_bytes(f"fictitious {name}".encode())
    (root / "artifacts" / "release-notes").mkdir(parents=True)
    (root / "artifacts" / "release-notes" / "release-notes.md").write_text("Notes")
    return root / "artifacts"


def fingerprint(name: str) -> str:
    return hashlib.sha256(f"fictitious {name}".encode()).hexdigest()


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("lacis_0.2.0~rc1_all.deb", "lacis_0.2.0.rc1_all.deb"),
        ("lacis-0.2.0-windows-x64-setup.exe", "lacis-0.2.0-windows-x64-setup.exe"),
        ("lacis 0.2.0 (copy)~.tar.gz", "lacis.0.2.0.copy..tar.gz"),
        ("lacis-0.2.0+local@1_all.deb", "lacis-0.2.0+local@1_all.deb"),
    ],
)
def test_a_file_gets_the_name_that_github_serves_it_under(name: str, expected: str) -> None:
    assert served_name(name) == expected


def test_each_package_artifact_gives_its_single_file_without_the_notes(tmp_path: Path) -> None:
    files, problems = package_files(artifacts(tmp_path))
    assert problems == []
    assert sorted(path.name for path in files) == sorted(PACKAGES.values())


def test_an_artifact_must_hold_exactly_one_package(tmp_path: Path) -> None:
    folder = artifacts(tmp_path)
    (folder / "debian-package" / "lacis_0.2.0~rc1_amd64.buildinfo").write_text("build")
    for path in (folder / "source-archive").iterdir():
        path.unlink()
    assert package_files(folder)[1] == [
        "debian-package holds 2 files instead of one package",
        "source-archive holds 0 files instead of one package",
    ]


def test_two_packages_cannot_be_served_under_the_same_name(tmp_path: Path) -> None:
    folder = artifacts(tmp_path, {"first": "lacis_1.0~a.deb", "second": "lacis_1.0.a.deb"})
    assert package_files(folder)[1] == ["two packages are served as lacis_1.0.a.deb"]


def test_a_release_without_any_package_is_refused(tmp_path: Path) -> None:
    folder = artifacts(tmp_path, {})
    assert package_files(folder)[1] == [f"{folder} holds no package"]


def test_the_release_holds_the_served_names_and_their_fingerprints(tmp_path: Path) -> None:
    files, _ = package_files(artifacts(tmp_path))
    checksums = gather(files, tmp_path / "release")
    served = sorted(served_name(name) for name in PACKAGES.values())
    original = {served_name(name): name for name in PACKAGES.values()}
    assert checksums == "".join(f"{fingerprint(original[name])}  {name}\n" for name in served)
    assert sorted(path.name for path in (tmp_path / "release").iterdir()) == sorted(
        [*served, "SHA256SUMS"]
    )
    assert (tmp_path / "release" / "SHA256SUMS").read_text(encoding="utf-8") == checksums


def test_the_command_gathers_the_release_or_lists_the_problems(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = artifacts(tmp_path)
    assert main([str(folder), str(tmp_path / "release")]) == 0
    assert capsys.readouterr().out.count("  lacis") == len(PACKAGES)
    (folder / "debian-package" / "extra.deb").write_text("extra")
    assert main([str(folder), str(tmp_path / "other")]) == 1
    assert capsys.readouterr().out == "debian-package holds 2 files instead of one package\n"
    assert not (tmp_path / "other").exists()
    assert main([str(folder)]) == 2
    assert capsys.readouterr().out.startswith("usage:")
