import re
import tomllib
from pathlib import Path

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
