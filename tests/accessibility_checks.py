from PySide6.QtCore import Qt
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QAbstractButton, QWidget


def is_interactive(widget: QWidget) -> bool:
    accepts_tab_focus = bool(widget.focusPolicy() & Qt.FocusPolicy.TabFocus)
    return accepts_tab_focus or isinstance(widget, QAbstractButton)


def accessible_name(widget: QWidget) -> str:
    interface = QAccessible.queryAccessibleInterface(widget)
    return interface.text(QAccessible.Text.Name).strip() if interface is not None else ""


def widgets_in(window: QWidget) -> list[QWidget]:
    return [window, *window.findChildren(QWidget)]


def interactive_widgets_without_accessible_name(window: QWidget) -> list[QWidget]:
    return [
        widget
        for widget in widgets_in(window)
        if widget.isVisibleTo(window) and is_interactive(widget) and not accessible_name(widget)
    ]
