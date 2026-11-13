import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from xml.etree import ElementTree

CHANGELOG = Path("CHANGELOG.md")
METAINFO = Path("packaging/linux/io.github.c4seus.lacis.metainfo.xml")
PYPROJECT = Path("pyproject.toml")
UNRELEASED = "Unreleased"
STABLE = "stable"
RELEASE_TAG = re.compile(r"v(?P<version>(?P<release>\d+\.\d+\.\d+)(?P<candidate>rc\d+)?)")
SECTION_HEADING = re.compile(r"## \[(?P<name>[^\]]+)\](?: - (?P<date>\S+))?")
SECTION_START = re.compile(r"^(?=## )", re.MULTILINE)
LINK_DEFINITION = re.compile(r"\[[^\]]+\]: \S+")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
INSTALLATION_NOTE = (
    "To install Lacis and verify a download with `SHA256SUMS`, follow the "
    "[installation instructions]({url}#installation)."
)
EXPECTED_ARGUMENTS = ("TAG", "VERSION", "NOTES")
NOT_A_RELEASE_TAG = (
    "{tag} is not a release tag: use vMAJOR.MINOR.PATCH, or vMAJOR.MINOR.PATCHrcN "
    "for a pre-release"
)
MISSING_SECTION = (
    "CHANGELOG.md has no [{release}] section: rename [Unreleased] to [{release}] - YYYY-MM-DD"
)
USAGE = f"usage: python scripts/check_release.py {' '.join(EXPECTED_ARGUMENTS)}"


@dataclass(frozen=True)
class ChangelogSection:
    name: str
    date: str | None
    notes: str


@dataclass(frozen=True)
class AppStreamRelease:
    version: str
    date: str
    kind: str


def changelog_sections(changelog: str) -> list[ChangelogSection]:
    sections: list[ChangelogSection] = []
    for block in SECTION_START.split(changelog):
        heading, _, body = block.partition("\n")
        found = SECTION_HEADING.fullmatch(heading.strip())
        if found is None:
            continue
        lines = [line for line in body.splitlines() if not LINK_DEFINITION.fullmatch(line)]
        sections.append(ChangelogSection(found["name"], found["date"], "\n".join(lines).strip()))
    return sections


def section_named(sections: list[ChangelogSection], name: str) -> ChangelogSection | None:
    return next((section for section in sections if section.name == name), None)


def latest_appstream_release(metainfo: str) -> AppStreamRelease | None:
    release = ElementTree.fromstring(metainfo).find("releases/release")
    if release is None:
        return None
    return AppStreamRelease(
        release.get("version", ""), release.get("date", ""), release.get("type", STABLE)
    )


def is_iso_date(text: str | None) -> bool:
    if text is None or ISO_DATE.fullmatch(text) is None:
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


def pre_release_problems(tag: str, sections: list[ChangelogSection]) -> list[str]:
    section = section_named(sections, UNRELEASED)
    if section is None or not section.notes:
        return [f"CHANGELOG.md needs a non-empty [{UNRELEASED}] section for the pre-release {tag}"]
    return []


def final_release_problems(
    release: str, sections: list[ChangelogSection], appstream: AppStreamRelease | None
) -> list[str]:
    section = section_named(sections, release)
    if section is None:
        return [MISSING_SECTION.format(release=release)]
    problems: list[str] = []
    if not is_iso_date(section.date):
        problems.append(f"the [{release}] section of CHANGELOG.md needs a date: YYYY-MM-DD")
    if not section.notes:
        problems.append(f"the [{release}] section of CHANGELOG.md is empty")
    if appstream is None or appstream.version != release:
        problems.append(f"the latest release of the AppStream metadata must be {release}")
        return problems
    if is_iso_date(section.date) and appstream.date != section.date:
        problems.append(
            f"the AppStream release {release} must have the date of CHANGELOG.md, {section.date}"
        )
    if appstream.kind != STABLE:
        problems.append(
            f'the AppStream release {release} must have the type "{STABLE}", '
            f'not "{appstream.kind}"'
        )
    return problems


def release_problems(
    tag: str,
    version: str,
    sections: list[ChangelogSection],
    appstream: AppStreamRelease | None,
) -> list[str]:
    found = RELEASE_TAG.fullmatch(tag)
    if found is None:
        return [NOT_A_RELEASE_TAG.format(tag=tag)]
    problems: list[str] = []
    if version != found["version"]:
        problems.append(
            f"the tag {tag} does not match the version of the package, {version}: tag the "
            "commit that is built, from a clean checkout"
        )
    if found["candidate"]:
        return problems + pre_release_problems(tag, sections)
    return problems + final_release_problems(found["release"], sections, appstream)


def is_pre_release(tag: str) -> bool:
    found = RELEASE_TAG.fullmatch(tag)
    return found is not None and found["candidate"] is not None


def release_notes(tag: str, sections: list[ChangelogSection], repository_url: str) -> str:
    found = RELEASE_TAG.fullmatch(tag)
    name = found["release"] if found is not None and not is_pre_release(tag) else UNRELEASED
    section = section_named(sections, name)
    notes = section.notes if section is not None else ""
    return f"{notes}\n\n{INSTALLATION_NOTE.format(url=repository_url)}\n"


def repository_url(root: Path) -> str:
    project = tomllib.loads((root / PYPROJECT).read_text(encoding="utf-8"))
    return str(project["project"]["urls"]["Homepage"])


def main(root: Path, arguments: list[str]) -> int:
    if len(arguments) != len(EXPECTED_ARGUMENTS):
        print(USAGE)
        return 2
    tag, version, notes = arguments
    sections = changelog_sections((root / CHANGELOG).read_text(encoding="utf-8"))
    appstream = latest_appstream_release((root / METAINFO).read_text(encoding="utf-8"))
    problems = release_problems(tag, version, sections, appstream)
    for problem in problems:
        print(problem)
    if problems:
        return 1
    target = root / notes
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(release_notes(tag, sections, repository_url(root)), encoding="utf-8")
    kind = "pre-release" if is_pre_release(tag) else "release"
    print(f"{tag}: {kind} of lacis {version}, notes in {notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:]))
