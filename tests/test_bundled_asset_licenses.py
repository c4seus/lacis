from pathlib import Path

import lacis

RESOURCE_DIRECTORY = Path(lacis.__file__).resolve().parent / "resources"
LICENSE_LIST = RESOURCE_DIRECTORY / "LICENSES.md"
LICENSE_TEXTS = {"fonts/OFL.txt"}


def bundled_assets() -> set[str]:
    return {
        path.relative_to(RESOURCE_DIRECTORY).as_posix()
        for path in RESOURCE_DIRECTORY.rglob("*")
        if path.is_file() and path != LICENSE_LIST
    }


def test_every_bundled_asset_is_listed_with_its_license() -> None:
    license_list = LICENSE_LIST.read_text(encoding="utf-8")
    unlisted_assets = {
        asset for asset in bundled_assets() - LICENSE_TEXTS if f"`{asset}`" not in license_list
    }
    assert not unlisted_assets


def test_every_listed_license_text_is_bundled() -> None:
    assert LICENSE_TEXTS.issubset(bundled_assets())
