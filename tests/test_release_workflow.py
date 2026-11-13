import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
REUSABLE_WORKFLOW = re.compile(r"^    uses: \./\.github/workflows/(\S+)$", re.MULTILINE)
JOB_START = re.compile(r"^  (?=[a-z][a-z-]*:$)", re.MULTILINE)
README = WORKFLOWS.parent.parent / "README.md"
PUBLISHED_FILE = re.compile(r"^          path: dist/(\S+)$", re.MULTILINE)
COMMIT_DATE = 'SOURCE_DATE_EPOCH="$(git log -1 --format=%ct)"'


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def release_jobs() -> dict[str, str]:
    jobs = workflow("release.yml").split("\njobs:\n", 1)[1]
    blocks = [block for block in JOB_START.split(jobs) if block.strip()]
    return {block.split(":", 1)[0]: block for block in blocks}


def test_a_version_tag_starts_the_release() -> None:
    assert '\non:\n  push:\n    tags: ["v*"]\n' in workflow("release.yml")


def test_the_release_builds_every_package_that_the_ci_builds() -> None:
    built_by_the_ci = REUSABLE_WORKFLOW.findall(workflow("ci.yml"))
    assert built_by_the_ci
    assert sorted(REUSABLE_WORKFLOW.findall(workflow("release.yml"))) == sorted(built_by_the_ci)


def test_the_release_is_published_only_after_every_other_job() -> None:
    jobs = release_jobs()
    others = sorted(name for name in jobs if name != "publish")
    needs = re.search(r"needs: \[(.+)\]", jobs["publish"])
    assert needs is not None
    assert sorted(needs.group(1).split(", ")) == others


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
        "needs: check\n" in job for name, job in jobs.items() if name not in ("check", "publish")
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
        for name in [*REUSABLE_WORKFLOW.findall(workflow("release.yml")), "release.yml"]
        for pattern in PUBLISHED_FILE.findall(workflow(name))
    ]
    readme = README.read_text(encoding="utf-8")
    assert len(published) == len(REUSABLE_WORKFLOW.findall(workflow("release.yml"))) + 1
    assert [pattern for pattern in published if pattern.rsplit("*", 1)[1] not in readme] == []
    assert "sha256sum --check --ignore-missing SHA256SUMS" in readme
    assert "Get-FileHash" in readme
