import configparser
import tomllib
from pathlib import Path
from xml.etree import ElementTree

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from lacis.product import APPLICATION_ID

REPOSITORY = Path(__file__).resolve().parent.parent
LINUX_DIRECTORY = REPOSITORY / "packaging" / "linux"
DESKTOP_ENTRY = LINUX_DIRECTORY / f"{APPLICATION_ID}.desktop"
METAINFO = LINUX_DIRECTORY / f"{APPLICATION_ID}.metainfo.xml"
SCREENSHOT_PREFIX = "https://raw.githubusercontent.com/c4seus/lacis/main/"


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


def test_the_metainfo_describes_the_same_application() -> None:
    component = ElementTree.parse(METAINFO).getroot()
    assert component.findtext("id") == APPLICATION_ID
    assert component.findtext("launchable") == DESKTOP_ENTRY.name
    assert component.findtext("project_license") == project()["license"]
    assert component.findtext("name") == desktop_entry()["Name"]
    assert component.findtext("provides/binary") == desktop_entry()["Exec"]


def test_the_screenshots_are_in_the_repository_at_their_declared_size() -> None:
    images = ElementTree.parse(METAINFO).getroot().findall("screenshots/screenshot/image")
    assert len(images) == 2
    for image in images:
        address = image.text or ""
        assert address.startswith(SCREENSHOT_PREFIX)
        screenshot = QImage(str(REPOSITORY / address.removeprefix(SCREENSHOT_PREFIX)))
        assert screenshot.size() == QSize(int(image.attrib["width"]), int(image.attrib["height"]))


def test_the_first_release_is_listed() -> None:
    releases = ElementTree.parse(METAINFO).getroot().findall("releases/release")
    assert [release.attrib["version"] for release in releases] == ["0.1.0"]
