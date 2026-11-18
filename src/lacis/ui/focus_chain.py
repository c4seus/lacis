from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget


def focusable_descendants(container: QWidget) -> list[QWidget]:
    return [
        widget
        for widget in container.findChildren(QWidget)
        if widget.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]


def place_after(anchor: QWidget, container: QWidget) -> None:
    policy = anchor.focusPolicy()
    anchor.setFocusPolicy(Qt.FocusPolicy.TabFocus)
    previous = anchor
    for widget in focusable_descendants(container):
        QWidget.setTabOrder(previous, widget)
        previous = widget
    anchor.setFocusPolicy(policy)
