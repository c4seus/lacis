import subprocess
from pathlib import Path

import pytest

from check_commits import USAGE_ERROR, commits_between, main, subject_problems


@pytest.mark.parametrize(
    "subject",
    [
        "feat(25): Add the entity search panel",
        "fix(3): Keep the selection when the theme changes",
        "refactor(12): Extract the graph layout into its own module",
        "docs(1): Add the README and the contributing guide",
        "test(8): Cover the homonym confidence levels",
        "ci(1): Check commit messages against the convention",
        "build(40): Build the Debian package",
        "chore(2): Embed the application icon",
        "Merge branch 'main' into feature",
    ],
)
def test_valid_subjects_have_no_problem(subject: str) -> None:
    assert subject_problems(subject) == []


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("Add the search panel", "the subject must read"),
        ("feature(25): Add the search panel", "the subject must read"),
        ("feat: Add the search panel", "the subject must read"),
        ("feat(#25): Add the search panel", "the subject must read"),
        ("feat(0): Add the search panel", "the subject must read"),
        ("feat(25):Add the search panel", "the subject must read"),
        ("feat(25): add the search panel", "capital letter"),
        ("feat(25): Add the search panel.", "period"),
        ("feat(25): Ajouter le panneau d'entité", "English"),
        ("feat(25): Added the search panel", "imperative"),
        ("feat(25): Adding the search panel", "imperative"),
        ("feat(25): Adds the search panel", "imperative"),
        ("feat(25): " + "Add " * 20, "longer than"),
    ],
)
def test_invalid_subjects_are_explained(subject: str, expected: str) -> None:
    assert any(expected in problem for problem in subject_problems(subject))


def run_git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit(directory: Path, subject: str) -> str:
    (directory / "file.txt").write_text(subject, encoding="utf-8")
    run_git(directory, "add", "file.txt")
    run_git(directory, "commit", "-q", "-m", subject)
    return run_git(directory, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.name", "Tester")
    run_git(tmp_path, "config", "user.email", "tester@example.com")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_commits_between_lists_the_new_commits(repository: Path) -> None:
    base = commit(repository, "docs(1): Add the README")
    head = commit(repository, "ci(1): Add the workflow")
    assert [item.subject for item in commits_between(base, head)] == ["ci(1): Add the workflow"]


def test_main_fails_on_a_badly_named_commit(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = commit(repository, "docs(1): Add the README")
    commit(repository, "ci(1): Add the workflow")
    head = commit(repository, "wip")
    assert main([base, head]) == 1
    assert "'wip'" in capsys.readouterr().out


def test_main_passes_on_well_named_commits(repository: Path) -> None:
    base = commit(repository, "docs(1): Add the README")
    head = commit(repository, "ci(1): Add the workflow")
    assert main([base, head]) == 0


def test_main_requires_a_base_and_a_head() -> None:
    assert main([]) == USAGE_ERROR
