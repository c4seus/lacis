import json
import subprocess
from pathlib import Path

import pytest

from check_tests_changed import USAGE_ERROR, main, missing_tests


@pytest.mark.parametrize(
    ("paths", "labels", "expected"),
    [
        (["src/lacis/graph.py"], [], True),
        (["src/lacis/graph.py", "tests/test_graph.py"], [], False),
        (["src/lacis/graph.py"], ["no-tests-needed"], False),
        (["README.md"], [], False),
        (["tests/test_graph.py"], [], False),
        ([], [], False),
    ],
)
def test_source_changes_need_test_changes(
    paths: list[str], labels: list[str], expected: bool
) -> None:
    assert missing_tests(paths, labels) is expected


def run_git(directory: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(directory), *arguments], check=True, capture_output=True, text=True
    ).stdout.strip()


def commit_file(directory: Path, relative_path: str) -> str:
    path = directory / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(relative_path, encoding="utf-8")
    run_git(directory, "add", relative_path)
    run_git(directory, "commit", "-q", "-m", f"chore(1): Add {relative_path}")
    return run_git(directory, "rev-parse", "HEAD")


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    run_git(tmp_path, "init", "-q")
    run_git(tmp_path, "config", "user.name", "Tester")
    run_git(tmp_path, "config", "user.email", "tester@example.com")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PULL_REQUEST_LABELS", raising=False)
    return tmp_path


def test_main_fails_when_only_the_source_changes(repository: Path) -> None:
    base = commit_file(repository, "README.md")
    head = commit_file(repository, "src/lacis/graph.py")
    assert main([base, head]) == 1


def test_main_passes_with_the_exemption_label(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = commit_file(repository, "README.md")
    head = commit_file(repository, "src/lacis/graph.py")
    monkeypatch.setenv("PULL_REQUEST_LABELS", json.dumps(["no-tests-needed"]))
    assert main([base, head]) == 0


def test_main_passes_when_tests_change_too(repository: Path) -> None:
    base = commit_file(repository, "README.md")
    commit_file(repository, "src/lacis/graph.py")
    head = commit_file(repository, "tests/test_graph.py")
    assert main([base, head]) == 0


def test_main_requires_a_base_and_a_head() -> None:
    assert main(["only-one"]) == USAGE_ERROR
