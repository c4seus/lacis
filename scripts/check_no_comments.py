import io
import sys
import tokenize
from collections.abc import Iterable, Iterator
from pathlib import Path

ALLOWED_DIRECTIVES = ("# type: ignore", "# noqa", "# pragma: no cover")
SCANNED_DIRECTORIES = ("src", "tests", "scripts")


def comment_lines(source: str) -> Iterator[tuple[int, str]]:
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        if token.start[0] == 1 and token.string.startswith("#!"):
            continue
        if token.string.startswith(ALLOWED_DIRECTIVES):
            continue
        yield token.start[0], token.string


def python_files(root: Path, directories: Iterable[str]) -> Iterator[Path]:
    for directory in directories:
        yield from sorted((root / directory).rglob("*.py"))


def main(root: Path) -> int:
    findings = [
        f"{path.relative_to(root)}:{line}: {comment}"
        for path in python_files(root, SCANNED_DIRECTORIES)
        for line, comment in comment_lines(path.read_text(encoding="utf-8"))
    ]
    for finding in findings:
        print(finding)
    if findings:
        print(
            f"{len(findings)} comment(s) found. Lacis code carries no comments: "
            "rename or extract instead (see CONTRIBUTING.md)."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(Path.cwd()))
