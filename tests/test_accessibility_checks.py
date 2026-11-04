from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from pytestqt.qtbot import QtBot

from accessibility_checks import accessible_name, interactive_widgets_without_accessible_name


def window_with(qtbot: QtBot, *widgets: QWidget) -> QWidget:
    window = QWidget()
    layout = QVBoxLayout(window)
    for widget in widgets:
        layout.addWidget(widget)
    qtbot.addWidget(window)
    window.show()
    return window


def named_tool_button() -> QToolButton:
    button = QToolButton()
    button.setAccessibleName("Aide")
    return button


def named_field() -> QLineEdit:
    field = QLineEdit()
    field.setAccessibleName("Rechercher une entreprise")
    return field


def test_a_window_where_everything_is_named_has_no_finding(qtbot: QtBot) -> None:
    window = window_with(qtbot, QPushButton("Rechercher"), named_tool_button(), named_field())
    assert interactive_widgets_without_accessible_name(window) == []


@pytest.mark.parametrize(
    "create_unnamed_widget",
    [QToolButton, QLineEdit, QPushButton],
    ids=["icon button", "field", "button without text"],
)
def test_an_unnamed_interactive_widget_is_reported(
    qtbot: QtBot, create_unnamed_widget: Callable[[], QWidget]
) -> None:
    unnamed_widget = create_unnamed_widget()
    window = window_with(qtbot, QPushButton("Rechercher"), unnamed_widget)
    assert interactive_widgets_without_accessible_name(window) == [unnamed_widget]


def test_an_unnamed_custom_widget_that_takes_the_focus_is_reported(qtbot: QtBot) -> None:
    custom_widget = QWidget()
    custom_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    window = window_with(qtbot, custom_widget)
    assert interactive_widgets_without_accessible_name(window) == [custom_widget]


def test_a_field_named_by_its_label_is_named(qtbot: QtBot) -> None:
    label = QLabel("Nom de l'enquête")
    field = QLineEdit()
    label.setBuddy(field)
    window = window_with(qtbot, label, field)
    assert accessible_name(field) == "Nom de l'enquête"
    assert interactive_widgets_without_accessible_name(window) == []


def test_hidden_and_decorative_widgets_are_ignored(qtbot: QtBot) -> None:
    hidden_button = QToolButton()
    window = window_with(qtbot, QLabel("Lacis"), QWidget(), hidden_button)
    hidden_button.hide()
    assert interactive_widgets_without_accessible_name(window) == []
