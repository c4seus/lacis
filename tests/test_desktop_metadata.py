import configparser
import tomllib
from pathlib import Path

from lacis.product import APPLICATION_ID

REPOSITORY = Path(__file__).resolve().parent.parent
LINUX_DIRECTORY = REPOSITORY / "packaging" / "linux"
DESKTOP_ENTRY = LINUX_DIRECTORY / f"{APPLICATION_ID}.desktop"


def desktop_entry() -> configparser.SectionProxy:
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # type: ignore[assignment,method-assign]
    parser.read(DESKTOP_ENTRY, encoding="utf-8")
    return parser["Desktop Entry"]


def project() -> dict[str, object]:
    with (REPOSITORY / "pyproject.toml").open("rb") as file:
        table: dict[str, object] = tomllib.load(file)["project"]
    return table


def test_the_desktop_entry_launches_the_command_with_the_application_icon() -> None:
    entry = desktop_entry()
    scripts = project()["scripts"]
    assert isinstance(scripts, dict)
    assert entry["Exec"] in scripts
    assert entry["Icon"] == APPLICATION_ID
    assert entry["Name"] == "Lacis"
    assert entry["StartupWMClass"] == "Lacis"
    assert entry["Comment[fr]"].startswith("Cartographier les entreprises françaises")
