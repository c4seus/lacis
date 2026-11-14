import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

import take_screenshots
from lacis.collectors import http_client
from lacis.graph import expansion
from lacis.signals import recomputation
from lacis.storage import homonym_decisions, investigations
from lacis.ui.main_window import DEFAULT_SIZE
from take_screenshots import (
    FROZEN_MOMENT,
    SCENES,
    THEMES,
    TIME_ZONE,
    frozen_clock,
    instant_demo_environment,
    main,
    readme_image,
    readme_screenshot,
    released_version,
    save_image,
    site_screenshot,
    time_zone,
)

CHANGELOG_TEXT = """# Changelog

## [Unreleased]

### Added

- A feature still in development.

## [0.2.0] - 2027-01-04

### Added

- A released feature.

## [0.1.0] - 2026-11-13

### Added

- The first release.
"""
UNRELEASED_CHANGELOG = """# Changelog

## [Unreleased]

### Added

- The first feature.
"""


def expected_screenshots() -> list[str]:
    expected = []
    for scene in SCENES:
        for theme in THEMES:
            expected.append(site_screenshot(scene.name, theme).as_posix())
            if scene.readme_name is not None:
                expected.append(readme_screenshot(scene.readme_name, theme).as_posix())
    return expected


def test_the_screenshots_show_the_last_released_version() -> None:
    assert released_version(CHANGELOG_TEXT) == "0.2.0"


def test_a_changelog_without_release_has_no_version_to_show() -> None:
    with pytest.raises(ValueError, match="no released version"):
        released_version(UNRELEASED_CHANGELOG)


def test_the_screenshots_of_a_scene_are_named_after_it_and_its_theme() -> None:
    assert expected_screenshots() == [
        "site/src/assets/screenshots/main-window-light.webp",
        "docs/images/screenshot-light.png",
        "site/src/assets/screenshots/main-window-dark.webp",
        "docs/images/screenshot-dark.png",
    ]


def test_the_screenshots_only_show_the_fictitious_data_of_the_demo() -> None:
    environment = instant_demo_environment()
    assert environment.demo
    assert isinstance(environment.transport, httpx.MockTransport)


def test_the_clock_of_the_demo_is_frozen_then_given_back() -> None:
    with frozen_clock():
        assert http_client.current_time() == FROZEN_MOMENT
        assert expansion.current_time() == FROZEN_MOMENT
        assert recomputation.utc_now() == FROZEN_MOMENT
        assert homonym_decisions.current_time() == FROZEN_MOMENT
        assert investigations.current_time() == FROZEN_MOMENT
    assert datetime.now(UTC) - expansion.current_time() < timedelta(minutes=1)


@pytest.mark.skipif(not hasattr(time, "tzset"), reason="the time zone is fixed on Windows")
def test_the_demo_runs_in_the_time_zone_of_paris_then_gives_the_zone_back() -> None:
    zone_before = os.environ.get("TZ")
    with time_zone(TIME_ZONE):
        assert FROZEN_MOMENT.astimezone().utcoffset() == timedelta(hours=1)
    assert os.environ.get("TZ") == zone_before


def test_the_readme_gets_the_screenshot_at_the_default_size_of_the_window() -> None:
    image = QImage(DEFAULT_SIZE * 2, QImage.Format.Format_RGB32)
    image.setDevicePixelRatio(2)
    readme = readme_image(image)
    assert readme.size() == DEFAULT_SIZE
    assert readme.devicePixelRatio() == 1


def test_an_image_that_cannot_be_written_stops_the_screenshots(tmp_path: Path) -> None:
    image = QImage(QSize(4, 4), QImage.Format.Format_RGB32)
    with pytest.raises(OSError, match="Cannot write"):
        save_image(image, tmp_path / "screenshot.unknown")


def test_the_screenshots_need_qt_to_write_webp(
    qapp: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG_TEXT, encoding="utf-8")
    monkeypatch.setattr(take_screenshots, "can_write_webp", lambda: False)
    assert main(tmp_path) == 1
    assert "cannot write WebP" in capsys.readouterr().out
    assert not (tmp_path / "site").exists()


def test_the_demo_writes_every_screenshot_of_the_site_and_the_readme(
    qapp: QApplication, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    if not take_screenshots.can_write_webp():
        pytest.skip("this Qt has no WebP writer")
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG_TEXT, encoding="utf-8")
    assert main(tmp_path) == 0
    assert capsys.readouterr().out.split() == expected_screenshots()
    for theme in THEMES:
        site_image = tmp_path / site_screenshot("main-window", theme)
        readme_image_path = tmp_path / readme_screenshot("screenshot", theme)
        assert site_image.read_bytes()[8:16] == b"WEBPVP8L"
        assert QImage(str(site_image)).size() == DEFAULT_SIZE
        assert QImage(str(readme_image_path)).size() == DEFAULT_SIZE
    light, dark = (tmp_path / site_screenshot("main-window", theme) for theme in THEMES)
    assert light.read_bytes() != dark.read_bytes()
