from pathlib import Path

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage

from build_icons import (
    HICOLOR_SIZES,
    WINDOWS_ICON,
    WINDOWS_SIZES,
    RenderedIcon,
    encoded_size,
    hicolor_icon,
    icon_file,
    icon_images,
    main,
    outdated,
    same_pixels,
    scalable_icon,
)
from lacis.design.application_icon import rendered_application_icon

REPOSITORY = Path(__file__).resolve().parent.parent


def test_the_committed_icons_match_their_masters() -> None:
    assert main(REPOSITORY, ["--check"]) == 0


def test_every_hicolor_size_is_committed_at_its_size() -> None:
    for size in HICOLOR_SIZES:
        image = QImage(str(REPOSITORY / hicolor_icon(size)))
        assert image.size() == QSize(size, size)
    assert hicolor_icon(48).as_posix() == (
        "packaging/icons/hicolor/48x48/apps/io.github.c4seus.lacis.png"
    )
    assert scalable_icon().as_posix() == (
        "packaging/icons/hicolor/scalable/apps/io.github.c4seus.lacis.svg"
    )


def test_the_windows_icon_holds_every_size_up_to_256() -> None:
    icons = icon_images((REPOSITORY / WINDOWS_ICON).read_bytes())
    assert [icon.size for icon in icons] == list(WINDOWS_SIZES)
    assert all(icon.image.size() == QSize(icon.size, icon.size) for icon in icons)


def test_an_icon_file_round_trips_its_images() -> None:
    rendered = [RenderedIcon(size, rendered_application_icon(size)) for size in (16, 256)]
    read = icon_images(icon_file(rendered))
    assert [icon.size for icon in read] == [16, 256]
    assert all(
        same_pixels(original.image, copy.image)
        for original, copy in zip(rendered, read, strict=True)
    )
    assert encoded_size(255) == 255
    assert encoded_size(256) == 0


def test_images_of_different_sizes_or_colours_differ() -> None:
    small = rendered_application_icon(16)
    assert not same_pixels(small, rendered_application_icon(24))
    altered = small.copy()
    altered.fill(0)
    assert not same_pixels(small, altered)


def test_building_writes_every_icon_and_the_check_then_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(tmp_path, []) == 0
    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == len(HICOLOR_SIZES) + 2
    assert printed[-1] == "packaging/windows/lacis.ico"
    assert outdated(tmp_path) == []


def test_the_check_names_every_stale_or_missing_icon(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main(tmp_path, [])
    stale = tmp_path / hicolor_icon(32)
    rendered_application_icon(16).scaled(32, 32).save(str(stale))
    (tmp_path / scalable_icon()).write_text("<svg/>", encoding="utf-8")
    (tmp_path / WINDOWS_ICON).write_bytes(icon_file([]))
    capsys.readouterr()
    assert main(tmp_path, ["--check"]) == 1
    assert outdated(tmp_path) == [hicolor_icon(32), scalable_icon(), WINDOWS_ICON]
    assert "run python scripts/build_icons.py" in capsys.readouterr().out
    (tmp_path / scalable_icon()).unlink()
    (tmp_path / WINDOWS_ICON).unlink()
    assert outdated(tmp_path)[-2:] == [scalable_icon(), WINDOWS_ICON]
