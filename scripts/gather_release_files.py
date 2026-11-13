import hashlib
import re
import shutil
import sys
from pathlib import Path

NOTES_ARTIFACT = "release-notes"
CHECKSUMS = "SHA256SUMS"
UNSERVED_CHARACTERS = re.compile(r"[^A-Za-z0-9._+@-]+")
EXPECTED_ARGUMENTS = ("ARTIFACTS", "RELEASE")
USAGE = f"usage: python scripts/gather_release_files.py {' '.join(EXPECTED_ARGUMENTS)}"


def served_name(name: str) -> str:
    return UNSERVED_CHARACTERS.sub(".", name)


def package_files(artifacts: Path) -> tuple[list[Path], list[str]]:
    files: list[Path] = []
    problems: list[str] = []
    directories = sorted(path for path in artifacts.iterdir() if path.is_dir())
    for directory in directories:
        if directory.name == NOTES_ARTIFACT:
            continue
        found = sorted(path for path in directory.iterdir() if path.is_file())
        if len(found) == 1:
            files.extend(found)
        else:
            problems.append(f"{directory.name} holds {len(found)} files instead of one package")
    if not files and not problems:
        problems.append(f"{artifacts} holds no package")
    names = [served_name(path.name) for path in files]
    problems.extend(
        f"two packages are served as {name}"
        for name in sorted(set(names))
        if names.count(name) > 1
    )
    return files, problems


def sha256_of(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def gather(files: list[Path], release: Path) -> str:
    release.mkdir(parents=True)
    copies = sorted(release / served_name(path.name) for path in files)
    for path in files:
        shutil.copyfile(path, release / served_name(path.name))
    checksums = "".join(f"{sha256_of(copy)}  {copy.name}\n" for copy in copies)
    (release / CHECKSUMS).write_text(checksums, encoding="utf-8")
    return checksums


def main(arguments: list[str]) -> int:
    if len(arguments) != len(EXPECTED_ARGUMENTS):
        print(USAGE)
        return 2
    artifacts, release = (Path(argument) for argument in arguments)
    files, problems = package_files(artifacts)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    print(gather(files, release), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
