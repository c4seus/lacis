import shutil
import sys
from pathlib import Path

APPLICATION_ID = "io.github.c4seus.lacis"
SHARE_DIRECTORY = Path("usr/share")
DESKTOP_ENTRY = Path("packaging/linux") / f"{APPLICATION_ID}.desktop"
METAINFO = Path("packaging/linux") / f"{APPLICATION_ID}.metainfo.xml"
HICOLOR_DIRECTORY = Path("packaging/icons/hicolor")
USAGE = "usage: python scripts/stage_desktop_files.py DESTINATION"


def staged_files(root: Path) -> dict[Path, Path]:
    files = {
        DESKTOP_ENTRY: SHARE_DIRECTORY / "applications" / DESKTOP_ENTRY.name,
        METAINFO: SHARE_DIRECTORY / "metainfo" / METAINFO.name,
    }
    for icon in sorted((root / HICOLOR_DIRECTORY).rglob(f"{APPLICATION_ID}.*")):
        source = icon.relative_to(root)
        files[source] = SHARE_DIRECTORY / "icons" / source.relative_to(HICOLOR_DIRECTORY.parent)
    return files


def stage(root: Path, destination: Path) -> list[Path]:
    staged = []
    for source, target in staged_files(root).items():
        (destination / target).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / source, destination / target)
        staged.append(target)
    return staged


def main(root: Path, arguments: list[str]) -> int:
    if len(arguments) != 1:
        print(USAGE)
        return 2
    for target in stage(root, Path(arguments[0])):
        print(target.as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:]))
