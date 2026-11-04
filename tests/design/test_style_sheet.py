import re
from dataclasses import astuple, replace

import pytest
from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton, QWidget
from pytestqt.qtbot import QtBot

from lacis.design.style_sheet import build_style_sheet, font_family_list
from lacis.design.tokens import LIGHT_THEME, THEMES, Theme

HEXADECIMAL_COLOUR = re.compile(r"#[0-9a-fA-F]{6}\b")


def styled_widget(qtbot: QtBot, widget: QWidget, theme: Theme) -> QWidget:
    qtbot.addWidget(widget)
    widget.setStyleSheet(build_style_sheet(theme))
    widget.ensurePolished()
    return widget


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_every_colour_of_the_style_sheet_comes_from_the_tokens(theme: Theme) -> None:
    token_colours = set(astuple(theme.colours))
    style_sheet_colours = set(HEXADECIMAL_COLOUR.findall(build_style_sheet(theme)))
    assert style_sheet_colours
    assert style_sheet_colours <= token_colours


def test_changing_a_token_changes_the_style_sheet() -> None:
    changed_theme = replace(LIGHT_THEME, colours=replace(LIGHT_THEME.colours, accent="#123456"))
    changed_style_sheet = build_style_sheet(changed_theme)
    assert "#123456" in changed_style_sheet
    assert LIGHT_THEME.colours.accent not in changed_style_sheet


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_text_takes_the_colour_of_the_theme(qtbot: QtBot, theme: Theme) -> None:
    label = styled_widget(qtbot, QLabel("Lacis"), theme)
    assert label.palette().color(QPalette.ColorRole.WindowText) == QColor(theme.colours.text)


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_muted_labels_take_the_muted_colour(qtbot: QtBot, theme: Theme) -> None:
    label = QLabel("4 signaux")
    label.setProperty("tone", "muted")
    styled_label = styled_widget(qtbot, label, theme)
    assert styled_label.palette().color(QPalette.ColorRole.WindowText) == QColor(
        theme.colours.muted_text
    )


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_primary_buttons_use_the_text_colour_on_accent(qtbot: QtBot, theme: Theme) -> None:
    button = QPushButton("Rechercher")
    button.setProperty("variant", "primary")
    styled_button = styled_widget(qtbot, button, theme)
    assert styled_button.palette().color(QPalette.ColorRole.ButtonText) == QColor(
        theme.colours.text_on_accent
    )


def test_widgets_use_the_font_sizes_and_families_of_the_tokens(qtbot: QtBot) -> None:
    field = styled_widget(qtbot, QLineEdit(), LIGHT_THEME)
    assert field.font().pixelSize() == LIGHT_THEME.font_sizes.body
    assert field.font().families()[0] == "Inter"


def test_font_families_are_quoted_and_listed_in_order() -> None:
    assert font_family_list(("Inter", "Segoe UI")) == '"Inter", "Segoe UI"'


@pytest.mark.parametrize("theme", THEMES, ids=lambda theme: theme.name)
def test_qt_parses_the_style_sheet_without_warning(qtbot: QtBot, theme: Theme) -> None:
    messages: list[str] = []

    def record_message(message_type: QtMsgType, context: QMessageLogContext, message: str) -> None:
        messages.append(message)

    previous_handler = qInstallMessageHandler(record_message)
    try:
        button = styled_widget(qtbot, QPushButton("Rechercher"), theme)
        button.show()
        qtbot.waitExposed(button)
    finally:
        qInstallMessageHandler(previous_handler)
    assert not [message for message in messages if "style" in message.lower()]
