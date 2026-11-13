from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QTabBar,
    QTableWidget,
    QTextEdit,
    QToolButton,
    QTreeWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from lacis.design.theme_controller import ThemeController, ThemePreference
from lacis.design.tokens import DARK_THEME, LIGHT_THEME, Theme


def combo_box() -> QComboBox:
    box = QComboBox()
    box.addItems(["Profondeur 1", "Profondeur 2"])
    return box


def tab_bar() -> QTabBar:
    bar = QTabBar()
    for title in ("Fiche", "Entités", "Journal"):
        bar.addTab(title)
    return bar


def tool_button() -> QToolButton:
    button = QToolButton()
    button.setText("Étendre")
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return button


INTERACTIVE_WIDGETS: dict[str, Callable[[], QWidget]] = {
    "button": lambda: QPushButton("Rechercher"),
    "tool button": tool_button,
    "field": QLineEdit,
    "combo box": combo_box,
    "spin box": QSpinBox,
    "text editor": QTextEdit,
    "plain text editor": QPlainTextEdit,
    "list": QListWidget,
    "tree": QTreeWidget,
    "table": QTableWidget,
    "check box": lambda: QCheckBox("Entités signalées uniquement"),
    "radio button": lambda: QRadioButton("Profondeur 1"),
    "tab bar": tab_bar,
    "slider": lambda: QSlider(Qt.Orientation.Horizontal),
}


def accent_pixels(image: QImage, accent: str) -> int:
    return sum(
        1
        for row in range(image.height())
        for column in range(image.width())
        if image.pixelColor(column, row).name() == accent
    )


@pytest.mark.parametrize("create_widget", INTERACTIVE_WIDGETS.values(), ids=INTERACTIVE_WIDGETS)
@pytest.mark.parametrize(
    ("preference", "theme"),
    [(ThemePreference.LIGHT, LIGHT_THEME), (ThemePreference.DARK, DARK_THEME)],
    ids=["light", "dark"],
)
def test_the_focused_widget_shows_an_accent_border(
    qtbot: QtBot,
    theme_controller: ThemeController,
    create_widget: Callable[[], QWidget],
    preference: ThemePreference,
    theme: Theme,
) -> None:
    theme_controller.set_preference(preference)
    window = QWidget()
    other_widget = QPushButton("Autre", window)
    widget = create_widget()
    layout = QHBoxLayout(window)
    layout.addWidget(other_widget)
    layout.addWidget(widget)
    qtbot.addWidget(window)
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)

    other_widget.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(other_widget.hasFocus)
    unfocused_accent = accent_pixels(widget.grab().toImage(), theme.colours.accent)

    widget.setFocus(Qt.FocusReason.TabFocusReason)
    qtbot.waitUntil(widget.hasFocus)
    focused_accent = accent_pixels(widget.grab().toImage(), theme.colours.accent)

    assert focused_accent > unfocused_accent + widget.width()
