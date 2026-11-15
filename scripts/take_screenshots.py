import importlib
import os
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, datetime, tzinfo
from pathlib import Path
from typing import Self
from unittest.mock import patch

from PySide6.QtCore import QEventLoop, QRect, QSettings, Qt, QTimer
from PySide6.QtGui import QImage, QImageWriter
from PySide6.QtWidgets import QPushButton

from check_release import changelog_sections
from lacis.application import create_application
from lacis.collectors.environment import CollectionEnvironment, demo_collection_environment
from lacis.collectors.http_client import CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.storage.locations import CONFIGURATION_DIRECTORY_VARIABLE, DATA_DIRECTORY_VARIABLE
from lacis.ui.entity_sheet import NOTICES_TITLE
from lacis.ui.header_bar import displayed_version
from lacis.ui.main_window import DEFAULT_SIZE, MainWindow
from lacis.ui.notifications import Notification
from lacis.ui.review_queue import SAME_PERSON_TEXT

SITE_SCREENSHOTS = Path("site/src/assets/screenshots")
README_SCREENSHOTS = Path("docs/images")
CHANGELOG = Path("CHANGELOG.md")
THEMES = (ThemePreference.LIGHT, ThemePreference.DARK)
SCALE_FACTOR = "2"
TIME_ZONE = "Europe/Paris"
FROZEN_MOMENT = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)
CLOCK_MODULES = (
    "lacis.collectors.http_client",
    "lacis.graph.expansion",
    "lacis.signals.recomputation",
    "lacis.storage.homonym_decisions",
    "lacis.storage.investigations",
)
INVESTIGATION_NAME = "faux-plombiers-31"
INVESTIGATION_QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"
ADDRESS_QUERY = "12 rue des Lilas"
PLUMBERS = ("ACME PLOMBERIE", "DUPONT SERVICES")
SELECTED_COMPANY = "DUPONT SERVICES"
FOREIGN_COMPANY = "DUPONT INVEST LTD"
SETTLING_DELAY_MILLISECONDS = 300
POLLING_DELAY_MILLISECONDS = 50
SCENE_TIMEOUT_SECONDS = 60.0
LOSSLESS_QUALITY = 100
STEADY_CURSOR = 0
SECTION_MARGIN = 16


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz: tzinfo | None = None) -> Self:
        return cls.fromtimestamp(FROZEN_MOMENT.timestamp(), tz)


@dataclass(frozen=True)
class Scene:
    name: str
    prepare: Callable[[MainWindow], None]
    readme_name: str | None = None
    area: QRect | None = None


def skip_waiting(_duration: float) -> None:
    return None


def instant_demo_environment() -> CollectionEnvironment:
    timing = CollectorTiming(rate_limiters=RateLimiters(sleep=skip_waiting), sleep=skip_waiting)
    return replace(demo_collection_environment(), timing=timing)


def released_version(changelog: str) -> str:
    released = [section.name for section in changelog_sections(changelog) if section.date]
    if not released:
        raise ValueError("The changelog has no released version yet")
    return released[0]


def site_screenshot(name: str, theme: ThemePreference) -> Path:
    return SITE_SCREENSHOTS / f"{name}-{theme}.webp"


def readme_screenshot(name: str, theme: ThemePreference) -> Path:
    return README_SCREENSHOTS / f"{name}-{theme}.png"


def pause(milliseconds: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def wait_until(condition: Callable[[], bool], description: str) -> None:
    deadline = time.monotonic() + SCENE_TIMEOUT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError(f"The demo mode did not {description} in time")
        pause(POLLING_DELAY_MILLISECONDS)


def is_idle(window: MainWindow) -> bool:
    return (
        not window.review_actions.expansions
        and window.layout_job is None
        and not window.move_jobs
        and window.register_search.search_job is None
        and not window.register_search.adding_jobs
    )


def settle(window: MainWindow) -> None:
    pause(SETTLING_DELAY_MILLISECONDS)
    wait_until(lambda: is_idle(window), "finish its collections and its layout")
    pause(SETTLING_DELAY_MILLISECONDS)


def fill_the_new_investigation(window: MainWindow) -> None:
    window.home_screen.start_creation()
    window.home_screen.new_investigation_panel.fields.fill(
        INVESTIGATION_NAME, INVESTIGATION_QUESTION
    )
    settle(window)


def search_the_address_of_the_plumbers(window: MainWindow) -> None:
    window.home_screen.new_investigation_panel.create_investigation()
    wait_until(
        lambda: window.current_investigation == INVESTIGATION_NAME, "open the new investigation"
    )
    window.header_bar.search_field.setText(ADDRESS_QUERY)
    window.register_search.search_now()
    wait_until(lambda: bool(window.search_popup.rows), "find the plumbers of the address")
    settle(window)


def add_the_plumbers(window: MainWindow) -> dict[str, str]:
    rows = [row for row in window.search_popup.rows if row.result.title in PLUMBERS]
    for row in rows:
        window.register_search.choose(row)
        settle(window)
    window.register_search.close()
    window.header_bar.search_field.clear()
    return {row.result.title: row.result.identifier for row in rows}


def confirm_the_homonym(window: MainWindow) -> None:
    buttons = window.investigation_page.findChildren(QPushButton)
    same_person = [
        button for button in buttons if button.text() == SAME_PERSON_TEXT and button.isVisible()
    ]
    if not same_person:
        raise LookupError("The demo mode proposed no homonym to confirm")
    same_person[0].click()
    settle(window)


def entity_identifier(window: MainWindow, label: str) -> str:
    node_items = window.investigation_page.graph_view.graph_scene.node_items
    for identifier, item in node_items.items():
        if item.node.label == label:
            return identifier
    raise LookupError(f"The demo mode has no entity named {label}")


def show_the_entity(window: MainWindow, label: str) -> None:
    window.investigation_page.show_entity(entity_identifier(window, label), label)
    settle(window)


def keep_the_view(window: MainWindow) -> None:
    settle(window)


def expand_the_plumbers(window: MainWindow) -> None:
    companies = add_the_plumbers(window)
    for title, identifier in companies.items():
        window.review_actions.expand(identifier, title)
        settle(window)


def investigate_the_plumbers(window: MainWindow) -> None:
    confirm_the_homonym(window)
    window.lay_out_again()
    settle(window)
    show_the_entity(window, SELECTED_COMPANY)
    window.investigation_page.graph_view.fit()
    window.content_area.setFocus()
    settle(window)


def scroll_to_the_notices(window: MainWindow) -> None:
    sheet = window.investigation_page.details_panel.entity_sheet
    titles = [
        title
        for title in sheet.section_titles
        if title.title_label.text() == NOTICES_TITLE.upper()
    ]
    if not titles:
        raise LookupError("The demo mode showed no BODACC notice")
    sheet.verticalScrollBar().setValue(titles[0].y() - SECTION_MARGIN)
    settle(window)


def show_the_foreign_company(window: MainWindow) -> None:
    show_the_entity(window, FOREIGN_COMPANY)


SCENES = (
    Scene("new-investigation", fill_the_new_investigation, area=QRect(180, 96, 1080, 284)),
    Scene("register-search", search_the_address_of_the_plumbers, area=QRect(470, 26, 676, 272)),
    Scene("homonym-review", expand_the_plumbers, area=QRect(0, 138, 320, 300)),
    Scene("unexpanded-leads", keep_the_view, area=QRect(0, 440, 320, 310)),
    Scene("main-window", investigate_the_plumbers, readme_name="screenshot"),
    Scene("graph", keep_the_view, area=QRect(321, 138, 698, 762)),
    Scene("warning-signal", keep_the_view, area=QRect(1020, 172, 405, 388)),
    Scene("bodacc-notices", scroll_to_the_notices, area=QRect(1020, 256, 405, 330)),
    Scene("foreign-entity", show_the_foreign_company, area=QRect(1020, 176, 420, 300)),
)


def clear_the_view(window: MainWindow) -> None:
    for notification in window.findChildren(Notification):
        notification.dismiss()
    pause(SETTLING_DELAY_MILLISECONDS)


def save_image(image: QImage, path: Path, quality: int = -1) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    writer = QImageWriter(str(path))
    writer.setQuality(quality)
    if not writer.write(image):
        raise OSError(f"Cannot write {path}: {writer.errorString()}")
    return path


def cropped(image: QImage, area: QRect | None) -> QImage:
    if area is None:
        return image
    scale = image.devicePixelRatio()
    return image.copy(
        round(area.x() * scale),
        round(area.y() * scale),
        round(area.width() * scale),
        round(area.height() * scale),
    )


def readme_image(image: QImage) -> QImage:
    readme = image.scaled(
        DEFAULT_SIZE,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    readme.setDevicePixelRatio(1)
    return readme


def capture(window: MainWindow, themes: ThemeController, scene: Scene, root: Path) -> list[Path]:
    written = []
    for theme in THEMES:
        themes.set_preference(theme)
        clear_the_view(window)
        image = cropped(window.grab().toImage(), scene.area)
        written.append(
            save_image(image, root / site_screenshot(scene.name, theme), LOSSLESS_QUALITY)
        )
        if scene.readme_name is not None:
            written.append(
                save_image(readme_image(image), root / readme_screenshot(scene.readme_name, theme))
            )
    return written


def take_screenshots(
    window: MainWindow, themes: ThemeController, version: str, root: Path
) -> list[Path]:
    window.header_bar.version_label.setText(displayed_version(version))
    window.resize(DEFAULT_SIZE)
    window.show()
    written = []
    for scene in SCENES:
        scene.prepare(window)
        written.extend(capture(window, themes, scene, root))
    return written


@contextmanager
def frozen_clock() -> Iterator[None]:
    with ExitStack() as patches:
        for name in CLOCK_MODULES:
            patches.enter_context(
                patch.object(importlib.import_module(name), "datetime", FrozenDatetime)
            )
        yield


def reset_time_zone() -> None:
    if hasattr(time, "tzset"):
        time.tzset()


@contextmanager
def time_zone(name: str) -> Iterator[None]:
    try:
        with patch.dict(os.environ, {"TZ": name}):
            reset_time_zone()
            yield
    finally:
        reset_time_zone()


@contextmanager
def isolated_demo() -> Iterator[QSettings]:
    with tempfile.TemporaryDirectory(
        prefix="lacis-screenshots-", ignore_cleanup_errors=True
    ) as directory:
        isolated = Path(directory)
        variables = {
            DATA_DIRECTORY_VARIABLE: str(isolated / "data"),
            CONFIGURATION_DIRECTORY_VARIABLE: str(isolated / "configuration"),
        }
        with patch.dict(os.environ, variables), frozen_clock(), time_zone(TIME_ZONE):
            yield QSettings(str(isolated / "settings.ini"), QSettings.Format.IniFormat)


def can_write_webp() -> bool:
    return b"webp" in QImageWriter.supportedImageFormats()


def main(root: Path) -> int:
    version = released_version((root / CHANGELOG).read_text(encoding="utf-8"))
    with patch.dict(os.environ, {"QT_QPA_PLATFORM": "offscreen", "QT_SCALE_FACTOR": SCALE_FACTOR}):
        application = create_application(["lacis"])
    if not can_write_webp():
        print("Qt cannot write WebP images here: install the image format plugins of Qt")
        return 1
    flash_time = application.styleHints().cursorFlashTime()
    application.styleHints().setCursorFlashTime(STEADY_CURSOR)
    with isolated_demo() as settings:
        themes = ThemeController(application, settings)
        window = MainWindow(settings, themes, instant_demo_environment())
        try:
            for path in take_screenshots(window, themes, version, root):
                print(path.relative_to(root).as_posix())
        finally:
            window.close()
            window.deleteLater()
            application.styleHints().colorSchemeChanged.disconnect(
                themes.follow_system_colour_scheme
            )
            application.styleHints().setColorScheme(Qt.ColorScheme.Unknown)
            application.setStyleSheet("")
            application.styleHints().setCursorFlashTime(flash_time)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(__file__).resolve().parent.parent))
