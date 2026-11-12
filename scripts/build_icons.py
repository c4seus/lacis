import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage, QImageReader, QImageWriter

from lacis.design.application_icon import (
    APPLICATION_ICON_DIRECTORY,
    LARGE_MASTER,
    rendered_application_icon,
)
from lacis.product import APPLICATION_ID

HICOLOR_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)
WINDOWS_SIZES = (16, 24, 32, 48, 64, 256)
HICOLOR_DIRECTORY = Path("packaging/icons/hicolor")
WINDOWS_ICON = Path("packaging/windows/lacis.ico")
ICON_DIRECTORY_HEADER = struct.Struct("<HHH")
ICON_DIRECTORY_ENTRY = struct.Struct("<BBBBHHII")
ICON_TYPE = 1
COLOUR_PLANES = 1
BITS_PER_PIXEL = 32
LARGEST_ENCODED_SIZE = 256
TOLERATED_CHANNEL_DIFFERENCE = 2


@dataclass(frozen=True)
class RenderedIcon:
    size: int
    image: QImage


def hicolor_icon(size: int) -> Path:
    return HICOLOR_DIRECTORY / f"{size}x{size}" / "apps" / f"{APPLICATION_ID}.png"


def scalable_icon() -> Path:
    return HICOLOR_DIRECTORY / "scalable" / "apps" / f"{APPLICATION_ID}.svg"


def png_bytes(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    QImageWriter(buffer, QByteArray(b"PNG")).write(image)
    buffer.close()
    return bytes(data.data())


def encoded_size(size: int) -> int:
    return 0 if size >= LARGEST_ENCODED_SIZE else size


def icon_file(icons: list[RenderedIcon]) -> bytes:
    images = [png_bytes(icon.image) for icon in icons]
    offset = ICON_DIRECTORY_HEADER.size + ICON_DIRECTORY_ENTRY.size * len(icons)
    entries = []
    for icon, image in zip(icons, images, strict=True):
        side = encoded_size(icon.size)
        entries.append(
            ICON_DIRECTORY_ENTRY.pack(
                side, side, 0, 0, COLOUR_PLANES, BITS_PER_PIXEL, len(image), offset
            )
        )
        offset += len(image)
    header = ICON_DIRECTORY_HEADER.pack(0, ICON_TYPE, len(icons))
    return header + b"".join(entries) + b"".join(images)


def icon_images(data: bytes) -> list[RenderedIcon]:
    _reserved, _kind, count = ICON_DIRECTORY_HEADER.unpack_from(data)
    icons = []
    for position in range(count):
        width, _height, _colours, _reserved_byte, _planes, _bits, length, offset = (
            ICON_DIRECTORY_ENTRY.unpack_from(
                data, ICON_DIRECTORY_HEADER.size + position * ICON_DIRECTORY_ENTRY.size
            )
        )
        encoded = QBuffer()
        encoded.setData(QByteArray(data[offset : offset + length]))
        image = QImageReader(encoded, QByteArray(b"PNG")).read()
        icons.append(RenderedIcon(width or LARGEST_ENCODED_SIZE, image))
    return icons


def build(root: Path) -> list[Path]:
    written = []
    for size in HICOLOR_SIZES:
        target = root / hicolor_icon(size)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(png_bytes(rendered_application_icon(size)))
        written.append(target)
    scalable = root / scalable_icon()
    scalable.parent.mkdir(parents=True, exist_ok=True)
    scalable.write_bytes((APPLICATION_ICON_DIRECTORY / LARGE_MASTER).read_bytes())
    windows_icon = root / WINDOWS_ICON
    windows_icon.parent.mkdir(parents=True, exist_ok=True)
    windows_icon.write_bytes(
        icon_file([RenderedIcon(size, rendered_application_icon(size)) for size in WINDOWS_SIZES])
    )
    return [*written, scalable, windows_icon]


def pixel_bytes(image: QImage) -> bytes:
    return bytes(image.convertToFormat(QImage.Format.Format_ARGB32).constBits())


def same_pixels(first: QImage, second: QImage) -> bool:
    if first.size() != second.size():
        return False
    return all(
        abs(first_byte - second_byte) <= TOLERATED_CHANNEL_DIFFERENCE
        for first_byte, second_byte in zip(pixel_bytes(first), pixel_bytes(second), strict=True)
    )


def same_windows_icon(root: Path, data: bytes) -> bool:
    icons = icon_images(data)
    if [icon.size for icon in icons] != list(WINDOWS_SIZES):
        return False
    return all(same_pixels(icon.image, rendered_application_icon(icon.size)) for icon in icons)


def outdated(root: Path) -> list[Path]:
    stale = [
        hicolor_icon(size)
        for size in HICOLOR_SIZES
        if not same_pixels(QImage(str(root / hicolor_icon(size))), rendered_application_icon(size))
    ]
    scalable = root / scalable_icon()
    master = APPLICATION_ICON_DIRECTORY / LARGE_MASTER
    if not scalable.is_file() or scalable.read_bytes() != master.read_bytes():
        stale.append(scalable_icon())
    windows_icon = root / WINDOWS_ICON
    if not windows_icon.is_file() or not same_windows_icon(root, windows_icon.read_bytes()):
        stale.append(WINDOWS_ICON)
    return stale


def main(root: Path, arguments: list[str]) -> int:
    if arguments == ["--check"]:
        stale = outdated(root)
        for path in stale:
            print(f"{path} does not match its master: run python scripts/build_icons.py")
        return 1 if stale else 0
    for path in build(root):
        print(path.relative_to(root))
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent, sys.argv[1:]))
