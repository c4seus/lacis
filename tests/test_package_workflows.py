from pathlib import Path

import pytest

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
COMMIT_DATE = 'SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"'


def build_job(workflow: str) -> str:
    return (WORKFLOWS / workflow).read_text(encoding="utf-8").split("\n  install:\n", 1)[0]


@pytest.mark.parametrize(
    "workflow", ["debian-package.yml", "fedora-package.yml", "arch-package.yml"]
)
def test_every_linux_package_is_built_from_the_date_of_its_commit(workflow: str) -> None:
    build = build_job(workflow)
    assert f"{COMMIT_DATE}\n" in build
    assert "export SOURCE_DATE_EPOCH\n" in build


@pytest.mark.parametrize(
    "workflow", ["debian-package.yml", "fedora-package.yml", "arch-package.yml"]
)
def test_git_trusts_the_workspace_before_root_reads_the_commit(workflow: str) -> None:
    build = build_job(workflow)
    trust = 'git config --global --add safe.directory "$GITHUB_WORKSPACE"'
    assert trust in build
    assert build.index(trust) < build.index(COMMIT_DATE)


def test_the_arch_build_hands_the_date_of_the_commit_to_makepkg() -> None:
    assert 'su builder --command "SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH make arch"' in build_job(
        "arch-package.yml"
    )
