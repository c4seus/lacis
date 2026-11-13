from pathlib import Path

import pytest

from check_release import (
    CHANGELOG,
    METAINFO,
    PYPROJECT,
    UNRELEASED,
    AppStreamRelease,
    ChangelogSection,
    changelog_sections,
    final_release_problems,
    is_iso_date,
    is_pre_release,
    latest_appstream_release,
    main,
    release_notes,
    release_problems,
    repository_url,
)
from lacis.product import REPOSITORY_URL

REPOSITORY = Path(__file__).resolve().parent.parent
CHANGELOG_TEXT = """# Changelog

Introduction.

## [Unreleased]

### Added

- Exports to GEXF

## [0.2.0] - 2027-03-01

### Fixed

- A crash when opening an empty investigation

[0.2.0]: https://github.com/c4seus/lacis/releases/tag/v0.2.0

## [0.1.0] - 2026-11-20

- First release
"""
METAINFO_TEXT = """<component type="desktop-application">
  <releases>
    <release version="0.2.0" date="2027-03-01" type="stable"/>
    <release version="0.1.0" date="2026-11-20"/>
  </releases>
</component>
"""
STABLE_RELEASE = AppStreamRelease("0.2.0", "2027-03-01", "stable")


def sections() -> list[ChangelogSection]:
    return changelog_sections(CHANGELOG_TEXT)


def write_repository(root: Path, changelog: str = CHANGELOG_TEXT) -> None:
    (root / METAINFO).parent.mkdir(parents=True)
    (root / METAINFO).write_text(METAINFO_TEXT, encoding="utf-8")
    (root / CHANGELOG).write_text(changelog, encoding="utf-8")
    (root / PYPROJECT).write_text(
        '[project.urls]\nHomepage = "https://example.org/lacis"\n', encoding="utf-8"
    )


def test_the_changelog_is_split_into_its_sections_without_the_link_definitions() -> None:
    assert sections() == [
        ChangelogSection(UNRELEASED, None, "### Added\n\n- Exports to GEXF"),
        ChangelogSection(
            "0.2.0", "2027-03-01", "### Fixed\n\n- A crash when opening an empty investigation"
        ),
        ChangelogSection("0.1.0", "2026-11-20", "- First release"),
    ]


def test_the_latest_appstream_release_is_the_first_one() -> None:
    assert latest_appstream_release(METAINFO_TEXT) == STABLE_RELEASE
    assert latest_appstream_release("<component><releases/></component>") is None
    without_type = (
        '<component><releases><release version="1.0.0" date="2028-01-02"/></releases></component>'
    )
    assert latest_appstream_release(without_type) == AppStreamRelease(
        "1.0.0", "2028-01-02", "stable"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-11-20", True),
        ("2026-02-30", False),
        ("20261120", False),
        ("2026-11-20T10:00", False),
        (None, False),
    ],
)
def test_only_a_calendar_date_is_an_iso_date(text: str | None, expected: bool) -> None:
    assert is_iso_date(text) is expected


def test_a_consistent_release_has_no_problem() -> None:
    assert release_problems("v0.2.0", "0.2.0", sections(), STABLE_RELEASE) == []


@pytest.mark.parametrize("tag", ["0.2.0", "v0.2", "v0.2.0-rc1", "v0.2.0.post1", "release-0.2.0"])
def test_only_a_version_tag_can_be_released(tag: str) -> None:
    expected = (
        f"{tag} is not a release tag: use vMAJOR.MINOR.PATCH, or vMAJOR.MINOR.PATCHrcN "
        "for a pre-release"
    )
    assert release_problems(tag, "0.2.0", sections(), STABLE_RELEASE) == [expected]


def test_the_tag_must_match_the_version_of_the_package() -> None:
    expected = (
        "the tag v0.2.0 does not match the version of the package, 0.2.1.dev3+g1a2b3c4: tag "
        "the commit that is built, from a clean checkout"
    )
    problems = release_problems("v0.2.0", "0.2.1.dev3+g1a2b3c4", sections(), STABLE_RELEASE)
    assert problems == [expected]


def test_a_release_needs_its_dated_section_in_the_changelog() -> None:
    assert final_release_problems("0.3.0", sections(), STABLE_RELEASE) == [
        "CHANGELOG.md has no [0.3.0] section: rename [Unreleased] to [0.3.0] - YYYY-MM-DD"
    ]
    undated = [ChangelogSection("0.2.0", "soon", ""), *sections()]
    assert final_release_problems(
        "0.2.0", undated, AppStreamRelease("0.2.0", "soon", "stable")
    ) == [
        "the [0.2.0] section of CHANGELOG.md needs a date: YYYY-MM-DD",
        "the [0.2.0] section of CHANGELOG.md is empty",
    ]


def test_a_release_needs_the_same_stable_release_in_the_appstream_metadata() -> None:
    assert final_release_problems("0.2.0", sections(), None) == [
        "the latest release of the AppStream metadata must be 0.2.0"
    ]
    older = AppStreamRelease("0.1.0", "2026-11-20", "stable")
    assert final_release_problems("0.2.0", sections(), older) == [
        "the latest release of the AppStream metadata must be 0.2.0"
    ]
    draft = AppStreamRelease("0.2.0", "2027-02-27", "development")
    assert final_release_problems("0.2.0", sections(), draft) == [
        "the AppStream release 0.2.0 must have the date of CHANGELOG.md, 2027-03-01",
        'the AppStream release 0.2.0 must have the type "stable", not "development"',
    ]


def test_a_pre_release_needs_the_unreleased_changes_only() -> None:
    draft = AppStreamRelease("0.2.0", "2027-02-27", "development")
    assert release_problems("v0.3.0rc1", "0.3.0rc1", sections(), draft) == []
    released = [section for section in sections() if section.name != UNRELEASED]
    assert release_problems("v0.3.0rc1", "0.3.0rc1", released, draft) == [
        "CHANGELOG.md needs a non-empty [Unreleased] section for the pre-release v0.3.0rc1"
    ]


def test_a_pre_release_is_told_apart_by_its_candidate_number() -> None:
    assert is_pre_release("v0.3.0rc2")
    assert not is_pre_release("v0.3.0")
    assert not is_pre_release("0.3.0rc2")


def test_the_notes_come_from_the_section_of_the_release() -> None:
    notes = release_notes("v0.2.0", sections(), "https://example.org/lacis")
    assert notes == (
        "### Fixed\n\n- A crash when opening an empty investigation\n\n"
        "To install Lacis and verify a download with `SHA256SUMS`, follow the "
        "[installation instructions](https://example.org/lacis#installation).\n"
    )
    assert release_notes("v0.3.0rc1", sections(), "https://example.org/lacis").startswith(
        "### Added\n\n- Exports to GEXF\n\n"
    )


def test_the_repository_url_is_the_homepage_of_the_project() -> None:
    assert repository_url(REPOSITORY) == REPOSITORY_URL


def test_the_command_writes_the_notes_of_a_consistent_release(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_repository(tmp_path)
    assert main(tmp_path, ["v0.2.0", "0.2.0", "build/release-notes.md"]) == 0
    assert capsys.readouterr().out == (
        "v0.2.0: release of lacis 0.2.0, notes in build/release-notes.md\n"
    )
    notes = (tmp_path / "build" / "release-notes.md").read_text(encoding="utf-8")
    assert notes.endswith("(https://example.org/lacis#installation).\n")


def test_the_command_lists_the_problems_and_writes_no_notes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_repository(tmp_path, CHANGELOG_TEXT.replace("## [0.2.0] - 2027-03-01", "## [0.2.0]"))
    assert main(tmp_path, ["v0.2.0", "0.2.0", "notes.md"]) == 1
    assert capsys.readouterr().out.splitlines() == [
        "the [0.2.0] section of CHANGELOG.md needs a date: YYYY-MM-DD"
    ]
    assert not (tmp_path / "notes.md").exists()
    assert main(tmp_path, ["v0.2.0"]) == 2
    assert capsys.readouterr().out.startswith("usage:")


def test_the_changelog_of_the_repository_lists_dated_versions_newest_first() -> None:
    found = changelog_sections((REPOSITORY / CHANGELOG).read_text(encoding="utf-8"))
    released = [section for section in found if section.name != UNRELEASED]
    assert found
    assert all(section.notes for section in found)
    assert all(is_iso_date(section.date) for section in released)
    versions = [tuple(int(part) for part in section.name.split(".")) for section in released]
    assert versions == sorted(versions, reverse=True)


def test_a_stable_appstream_release_matches_the_changelog_of_the_repository() -> None:
    appstream = latest_appstream_release((REPOSITORY / METAINFO).read_text(encoding="utf-8"))
    found = changelog_sections((REPOSITORY / CHANGELOG).read_text(encoding="utf-8"))
    assert appstream is not None
    if appstream.kind == "stable":
        assert final_release_problems(appstream.version, found, appstream) == []
    else:
        assert found[0].name == UNRELEASED
