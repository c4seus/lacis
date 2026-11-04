from collections.abc import Callable

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from pytestqt.qtbot import QtBot

from accessibility_checks import (
    accessible_name,
    interactive_widgets_without_accessible_name,
    tab_order,
)


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


def test_the_tab_order_follows_the_focus_chain(qtbot: QtBot) -> None:
    field = named_field()
    search_button = QPushButton("Rechercher")
    help_button = named_tool_button()
    window = window_with(qtbot, field, search_button, help_button)
    assert tab_order(window) == [field, search_button, help_button]


def test_the_tab_order_follows_a_changed_focus_chain(qtbot: QtBot) -> None:
    field = named_field()
    search_button = QPushButton("Rechercher")
    help_button = named_tool_button()
    window = window_with(qtbot, field, search_button, help_button)
    QWidget.setTabOrder(field, help_button)
    assert tab_order(window) == [field, help_button, search_button]


def test_the_tab_order_skips_disabled_hidden_and_unfocusable_widgets(qtbot: QtBot) -> None:
    field = named_field()
    disabled_button = QPushButton("Rechercher")
    disabled_button.setEnabled(False)
    hidden_button = named_tool_button()
    label = QLabel("Lacis")
    window = window_with(qtbot, field, disabled_button, hidden_button, label)
    hidden_button.hide()
    assert tab_order(window) == [field]


def test_the_tab_order_matches_what_the_tab_key_does(qtbot: QtBot) -> None:
    widgets = [named_field(), QPushButton("Rechercher"), named_tool_button()]
    window = window_with(qtbot, *widgets)
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    widgets[0].setFocus()
    visited: list[QWidget] = [widgets[0]]
    for _ in range(len(widgets) - 1):
        QTest.keyClick(visited[-1], Qt.Key.Key_Tab)
        focused_widget = QApplication.focusWidget()
        assert focused_widget is not None
        visited.append(focused_widget)
    assert visited == tab_order(window)
