import re
import subprocess
import sys
from dataclasses import dataclass

COMMIT_TYPES = ("feat", "fix", "refactor", "docs", "test", "ci", "build", "chore")
MAXIMUM_SUBJECT_LENGTH = 72
EXPECTED_ARGUMENTS = ("BASE", "HEAD")
USAGE_ERROR = 2
AUTOMATED_AUTHORS = frozenset({"dependabot[bot]"})
SUBJECT_PATTERN = re.compile(
    rf"^(?P<type>{'|'.join(COMMIT_TYPES)})\((?P<ticket>[1-9]\d*)\): (?P<description>.+)$"
)
NON_IMPERATIVE_FIRST_WORDS = frozenset(
    {
        "adds",
        "allows",
        "bumps",
        "changes",
        "creates",
        "ensures",
        "fixes",
        "handles",
        "implements",
        "improves",
        "introduces",
        "makes",
        "moves",
        "removes",
        "renames",
        "replaces",
        "sets",
        "supports",
        "updates",
        "uses",
    }
)
NON_IMPERATIVE_ENDINGS = ("ed", "ing")
IMPERATIVE_WORDS_WITH_THOSE_ENDINGS = frozenset(
    {"embed", "feed", "seed", "shred", "speed", "bring"}
)


@dataclass(frozen=True)
class Commit:
    identifier: str
    author: str
    subject: str


def subject_problems(subject: str) -> list[str]:
    if subject.startswith(("Merge ", "Revert ")):
        return []
    problems: list[str] = []
    match = SUBJECT_PATTERN.match(subject)
    if match is None:
        return [
            "the subject must read 'type(ticket): Description', with type among "
            f"{', '.join(COMMIT_TYPES)} and the GitHub issue number as ticket"
        ]
    description = match.group("description")
    if len(subject) > MAXIMUM_SUBJECT_LENGTH:
        problems.append(f"the subject is longer than {MAXIMUM_SUBJECT_LENGTH} characters")
    if not description[0].isupper():
        problems.append("the description must start with a capital letter")
    if description.endswith("."):
        problems.append("the description must not end with a period")
    if not description.isascii():
        problems.append("the description must be written in English, without accented letters")
    first_word = description.split()[0].lower()
    if first_word in NON_IMPERATIVE_FIRST_WORDS or (
        first_word.endswith(NON_IMPERATIVE_ENDINGS)
        and first_word not in IMPERATIVE_WORDS_WITH_THOSE_ENDINGS
    ):
        problems.append(
            f"the description must start with a verb in the imperative mood, not '{first_word}'"
        )
    return problems


def commits_between(base: str, head: str) -> list[Commit]:
    output = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x1f%an%x1f%s", f"{base}..{head}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [
        Commit(identifier, author, subject)
        for identifier, author, subject in (
            line.split("\x1f", 2) for line in output.splitlines() if line
        )
    ]


def main(arguments: list[str]) -> int:
    if len(arguments) != len(EXPECTED_ARGUMENTS):
        print(f"usage: check_commits.py {' '.join(EXPECTED_ARGUMENTS)}")
        return USAGE_ERROR
    failures = 0
    for commit in commits_between(*arguments):
        if commit.author in AUTOMATED_AUTHORS:
            continue
        for problem in subject_problems(commit.subject):
            failures += 1
            print(f"{commit.identifier[:12]} {commit.subject!r}: {problem}")
    if failures:
        print("See the commit convention in CONTRIBUTING.md.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
