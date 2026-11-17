import re
from pathlib import Path

from workflows import workflow, workflow_jobs

REUSABLE_WORKFLOW = re.compile(r"^    uses: \./\.github/workflows/(\S+)$", re.MULTILINE)
WEBSITE_WORKFLOW = "website.yml"
AFTER_THE_BUILDS = ("publish", "website")
README = Path(__file__).resolve().parent.parent / "README.md"
PUBLISHED_FILE = re.compile(r"^          path: dist/(\S+)$", re.MULTILINE)
COMMIT_DATE = 'SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"'


def package_workflows(name: str) -> list[str]:
    return [
        reusable
        for reusable in REUSABLE_WORKFLOW.findall(workflow(name))
        if reusable != WEBSITE_WORKFLOW
    ]


def release_jobs() -> dict[str, str]:
    return workflow_jobs("release.yml")


def test_a_version_tag_starts_the_release() -> None:
    assert '\non:\n  push:\n    tags: ["v*"]\n' in workflow("release.yml")


def test_the_release_builds_every_package_that_the_ci_builds() -> None:
    built_by_the_ci = package_workflows("ci.yml")
    assert built_by_the_ci
    assert sorted(package_workflows("release.yml")) == sorted(built_by_the_ci)


def test_the_release_is_published_only_after_every_build() -> None:
    jobs = release_jobs()
    builds = sorted(name for name in jobs if name not in AFTER_THE_BUILDS)
    needs = re.search(r"needs: \[(.+)\]", jobs["publish"])
    assert needs is not None
    assert sorted(needs.group(1).split(", ")) == builds


def test_only_the_publication_can_write_to_the_repository() -> None:
    assert "\npermissions:\n  contents: read\n" in workflow("release.yml")
    writers = [name for name, job in release_jobs().items() if "contents: write" in job]
    assert writers == ["publish"]


def test_the_tag_is_checked_before_anything_is_built() -> None:
    jobs = release_jobs()
    check = 'python scripts/check_release.py "$GITHUB_REF_NAME" "$VERSION" build/release-notes.md'
    assert check in jobs["check"]
    assert "git merge-base --is-ancestor HEAD origin/main" in jobs["check"]
    assert all(
        "needs: check\n" in job
        for name, job in jobs.items()
        if name not in ("check", *AFTER_THE_BUILDS)
    )


def test_the_notes_of_the_changelog_and_sha256sums_reach_the_release() -> None:
    publish = release_jobs()["publish"]
    assert "--notes-file artifacts/release-notes/release-notes.md" in publish
    assert "python3 scripts/gather_release_files.py artifacts release" in publish
    assert 'gh release create "$GITHUB_REF_NAME" release/*' in publish


def test_the_source_archive_is_built_from_the_date_of_its_commit() -> None:
    source = release_jobs()["source"]
    assert f"{COMMIT_DATE}\n" in source
    assert "export SOURCE_DATE_EPOCH\n" in source


def test_the_readme_describes_every_file_of_the_release_and_how_to_verify_it() -> None:
    published = [
        pattern
        for name in [*package_workflows("release.yml"), "release.yml"]
        for pattern in PUBLISHED_FILE.findall(workflow(name))
    ]
    readme = README.read_text(encoding="utf-8")
    assert len(published) == len(package_workflows("release.yml")) + 1
    assert [pattern for pattern in published if pattern.rsplit("*", 1)[1] not in readme] == []
    assert "sha256sum --check --ignore-missing SHA256SUMS" in readme
    assert "Get-FileHash" in readme
