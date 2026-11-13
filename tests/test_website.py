import re
import tomllib
from pathlib import Path

from workflows import workflow, workflow_jobs

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
APPLICATION_ICON = ROOT / "packaging/icons/hicolor/scalable/apps/io.github.c4seus.lacis.svg"


def site_configuration() -> str:
    return (SITE / "astro.config.mjs").read_text(encoding="utf-8")


def test_the_website_is_served_at_the_address_of_the_project() -> None:
    assert '    site: "https://c4seus.github.io",\n    base: "/lacis",\n' in site_configuration()


def test_the_website_has_a_single_locale_in_french_at_its_root() -> None:
    locales = re.search(r"\n( +)locales: \{\n(.*?)\n\1\},\n", site_configuration(), re.DOTALL)
    assert locales is not None
    assert locales.group(2).strip() == 'root: { label: "Français", lang: "fr" },'


def test_the_build_of_the_website_fails_on_a_broken_internal_link() -> None:
    assert "plugins: [starlightLinksValidator()]," in site_configuration()


def test_the_favicon_of_the_website_is_the_icon_of_the_application() -> None:
    assert (SITE / "public/favicon.svg").read_bytes() == APPLICATION_ICON.read_bytes()


def test_the_website_pins_the_major_version_of_node() -> None:
    assert re.fullmatch(r"[1-9]\d*\n", (SITE / ".node-version").read_text(encoding="utf-8"))


def test_the_source_archive_of_the_package_leaves_the_website_out() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"] == ["/site"]


def test_the_ci_builds_the_website_with_its_version_of_node_and_checks_its_links() -> None:
    website = workflow_jobs("ci.yml")["website"]
    assert "node-version-file: site/.node-version\n" in website
    assert "cache-dependency-path: site/package-lock.json\n" in website
    assert "run: make site\n" in website
    assert "uses: lycheeverse/lychee-action@" in website
    assert "args: --config site/lychee.toml --no-progress site/dist\n" in website


def test_a_failure_of_the_website_fails_the_ci() -> None:
    assert "      - website\n" in workflow_jobs("ci.yml")["ci-passed"]


def test_the_external_link_check_leaves_the_pages_of_the_website_to_its_build() -> None:
    link_check = tomllib.loads((SITE / "lychee.toml").read_text(encoding="utf-8"))
    assert link_check["base_url"] == "https://c4seus.github.io/"
    assert "^https://c4seus\\.github\\.io/" in link_check["exclude"]


def test_the_website_can_be_published_by_the_release_or_by_hand() -> None:
    assert "\non:\n  workflow_call:\n  workflow_dispatch:\n" in workflow("website.yml")


def test_the_published_website_is_built_like_in_the_ci() -> None:
    build = workflow_jobs("website.yml")["build"]
    assert "node-version-file: site/.node-version\n" in build
    assert "run: make site\n" in build
    assert "path: site/dist\n" in build


def test_only_the_deployment_of_the_website_can_write_to_github_pages() -> None:
    assert "\npermissions:\n  contents: read\n" in workflow("website.yml")
    writers = [name for name, job in workflow_jobs("website.yml").items() if "pages: write" in job]
    assert writers == ["deploy"]
    assert "      name: github-pages\n" in workflow_jobs("website.yml")["deploy"]


def test_the_website_is_published_after_each_final_release_only() -> None:
    website = workflow_jobs("release.yml")["website"]
    assert "    needs: publish\n" in website
    assert "    if: ${{ !contains(github.ref_name, 'rc') }}\n" in website
    assert "      pages: write\n      id-token: write\n" in website
    assert "    uses: ./.github/workflows/website.yml\n" in website


def test_dependabot_updates_the_dependencies_of_the_website_on_develop() -> None:
    updates = "  - package-ecosystem: npm\n    directory: /site\n    target-branch: develop\n"
    assert updates in (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
