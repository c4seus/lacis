import pytest
from PySide6.QtGui import QColor, QImage
from pytestqt.qtbot import QtBot

from lacis import __version__
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme
from lacis.ui.header_bar import HEADER_BAR_HEIGHT, HeaderBar, displayed_version


def open_header_bar(qtbot: QtBot, icon_factory: IconFactory) -> HeaderBar:
    header_bar = HeaderBar(icon_factory)
    header_bar.resize(1440, HEADER_BAR_HEIGHT)
    qtbot.addWidget(header_bar)
    header_bar.show()
    qtbot.waitExposed(header_bar)
    return header_bar


def opaque_colours(image: QImage) -> set[str]:
    return {
        image.pixelColor(column, row).name()
        for row in range(image.height())
        for column in range(image.width())
        if image.pixelColor(column, row).alpha() == 255
    }


def test_the_header_bar_shows_the_brand(qtbot: QtBot, icon_factory: IconFactory) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    assert header_bar.brand_label.text() == "Lacis"
    assert header_bar.logo_mark.isVisible()


def test_the_header_bar_keeps_its_height(qtbot: QtBot, icon_factory: IconFactory) -> None:
    assert open_header_bar(qtbot, icon_factory).height() == HEADER_BAR_HEIGHT


def test_the_breadcrumb_starts_on_the_investigations(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    breadcrumb = header_bar.breadcrumb
    assert [label.text() for label in breadcrumb.step_labels] == ["Enquêtes"]
    assert breadcrumb.step_labels[0].property("tone") == "current"


def test_the_breadcrumb_shows_the_trail_with_the_current_step_last(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    breadcrumb = header_bar.breadcrumb
    breadcrumb.set_trail(["Enquêtes", "faux-plombiers-31"])
    assert [label.text() for label in breadcrumb.step_labels] == [
        "Enquêtes",
        "faux-plombiers-31",
    ]
    assert [label.property("tone") for label in breadcrumb.step_labels] == ["muted", "current"]
    assert breadcrumb.accessibleName() == "Fil d'Ariane"
    assert breadcrumb.accessibleDescription() == "Enquêtes / faux-plombiers-31"
    assert breadcrumb.trail_layout.count() == 3


def test_the_version_is_shown_without_its_local_part(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    assert header_bar.version_label.text() == displayed_version(__version__)
    assert "+" not in header_bar.version_label.text()


@pytest.mark.parametrize(
    ("version", "expected_text"),
    [
        ("0.1.0", "v0.1.0"),
        ("0.2.0rc1", "v0.2.0rc1"),
        ("0.1.dev28+g27593705e.d20261104", "v0.1.dev28"),
    ],
)
def test_displayed_versions_drop_the_commit_and_date(version: str, expected_text: str) -> None:
    assert displayed_version(version) == expected_text


@pytest.mark.parametrize(
    ("preference", "theme"),
    [(ThemePreference.LIGHT, LIGHT_THEME), (ThemePreference.DARK, DARK_THEME)],
    ids=["light", "dark"],
)
def test_the_header_bar_follows_the_theme(
    qtbot: QtBot,
    theme_controller: ThemeController,
    icon_factory: IconFactory,
    preference: ThemePreference,
    theme: Theme,
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    theme_controller.set_preference(preference)
    header_image = header_bar.grab().toImage()
    assert header_image.pixelColor(header_bar.width() // 2, 4) == QColor(theme.colours.surface)
    logo_colours = opaque_colours(header_bar.logo_mark.grab().toImage())
    assert theme.colours.company in logo_colours
