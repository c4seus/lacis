import pytest
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QWidget
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


def test_the_search_field_explains_what_can_be_searched(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    assert header_bar.search_field.placeholderText() == (
        "Dénomination, SIREN, SIRET, dirigeant ou adresse"
    )
    assert header_bar.search_field.accessibleName() == "Rechercher une entreprise"


def test_the_search_icon_sits_inside_the_field_before_the_text(
    qtbot: QtBot, icon_factory: IconFactory, theme_controller: ThemeController
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    theme_controller.set_preference(ThemePreference.LIGHT)
    search_icon = header_bar.search_icon
    assert search_icon.parent() is header_bar.search_field
    assert search_icon.geometry().right() < header_bar.search_field.textMargins().left() + 12
    assert search_icon.geometry().center().y() == pytest.approx(
        header_bar.search_field.height() / 2, abs=1
    )
    assert LIGHT_THEME.colours.faint_text in opaque_colours(search_icon.grab().toImage())


def test_the_search_button_is_the_primary_button(qtbot: QtBot, icon_factory: IconFactory) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    assert header_bar.search_button.text() == "Rechercher"
    assert header_bar.search_button.property("variant") == "primary"


def test_the_search_stays_inactive_until_the_search_is_available(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    assert not header_bar.search_field.isEnabled()
    assert not header_bar.search_button.isEnabled()
    header_bar.set_search_enabled(True)
    assert header_bar.search_field.isEnabled()
    assert header_bar.search_button.isEnabled()


def horizontal_span(header_bar: HeaderBar, widget: QWidget) -> tuple[int, int]:
    top_left = widget.mapTo(header_bar, widget.rect().topLeft())
    top_right = widget.mapTo(header_bar, widget.rect().topRight())
    return top_left.x(), top_right.x()


def test_the_search_sits_between_the_breadcrumb_and_the_version(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    header_bar = open_header_bar(qtbot, icon_factory)
    _, breadcrumb_right = horizontal_span(header_bar, header_bar.breadcrumb)
    search_left, search_right = horizontal_span(header_bar, header_bar.search_field)
    button_left, button_right = horizontal_span(header_bar, header_bar.search_button)
    version_left, _ = horizontal_span(header_bar, header_bar.version_label)
    assert breadcrumb_right < search_left < search_right < button_left
    assert button_right < version_left
