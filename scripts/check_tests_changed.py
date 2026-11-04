import json
import os
import subprocess
import sys
from collections.abc import Iterable

SOURCE_DIRECTORY = "src/"
TESTS_DIRECTORY = "tests/"
EXEMPTION_LABEL = "no-tests-needed"
EXPECTED_ARGUMENTS = ("BASE", "HEAD")
USAGE_ERROR = 2


def missing_tests(changed_paths: Iterable[str], labels: Iterable[str]) -> bool:
    paths = list(changed_paths)
    touches_source = any(path.startswith(SOURCE_DIRECTORY) for path in paths)
    touches_tests = any(path.startswith(TESTS_DIRECTORY) for path in paths)
    return touches_source and not touches_tests and EXEMPTION_LABEL not in set(labels)


def changed_paths_between(base: str, head: str) -> list[str]:
    output = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...{head}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [line for line in output.splitlines() if line]


def labels_from_environment() -> list[str]:
    return [str(label) for label in json.loads(os.environ.get("PULL_REQUEST_LABELS", "[]"))]


def main(arguments: list[str]) -> int:
    if len(arguments) != len(EXPECTED_ARGUMENTS):
        print(f"usage: check_tests_changed.py {' '.join(EXPECTED_ARGUMENTS)}")
        return USAGE_ERROR
    if missing_tests(changed_paths_between(*arguments), labels_from_environment()):
        print(
            f"This pull request changes {SOURCE_DIRECTORY} without changing {TESTS_DIRECTORY}. "
            f"Add or update tests, or ask a maintainer for the '{EXEMPTION_LABEL}' label "
            "with a justification in the review."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
