from typing import Protocol, override, runtime_checkable

from PySide6.QtCore import QObject
from PySide6.QtGui import (
    QAccessible,
    QAccessibleActionInterface,
    QAccessibleInterface,
    QAccessibleStateChangeEvent,
)
from PySide6.QtWidgets import QAccessibleWidget, QLabel, QPushButton, QToolButton, QWidget

SCORE_ACCESSIBLE_NAME = "Score"
PRESS_ACTION = QAccessibleActionInterface.pressAction()


@runtime_checkable
class Activatable(Protocol):
    def activate(self) -> None: ...


@runtime_checkable
class Valued(Protocol):
    def accessible_value(self) -> str: ...


@runtime_checkable
class Expandable(Protocol):
    def accessible_expanded(self) -> bool: ...


class DescribedWidget(QAccessibleWidget):
    @override
    def text(self, t: QAccessible.Text) -> str:
        widget = self.widget()
        if t is QAccessible.Text.Value and isinstance(widget, Valued):
            return widget.accessible_value()
        return super().text(t)

    @override
    def state(self) -> QAccessible.State:
        state = super().state()
        widget = self.widget()
        if isinstance(widget, Expandable):
            state.expandable = True
            state.expanded = widget.accessible_expanded()
        return state

    @override
    def actionNames(self) -> list[str]:
        names = super().actionNames()
        if isinstance(self.widget(), Activatable):
            return [PRESS_ACTION, *names]
        return names

    @override
    def doAction(self, actionName: str) -> None:
        widget = self.widget()
        if actionName == PRESS_ACTION and isinstance(widget, Activatable):
            widget.activate()
            return
        super().doAction(actionName)


def described_interface(key: str, accessible_object: QObject) -> QAccessibleInterface | None:
    role = getattr(type(accessible_object), "accessible_role", None)
    if isinstance(role, QAccessible.Role) and isinstance(accessible_object, QWidget):
        return DescribedWidget(accessible_object, role)
    return None


class AccessibleInterfaces:
    installed = False

    @classmethod
    def install(cls) -> None:
        if not cls.installed:
            QAccessible.installFactory(described_interface)
            cls.installed = True


def announce_expanded(widget: QWidget) -> None:
    changed = QAccessible.State()
    changed.expanded = True
    QAccessible.updateAccessibility(QAccessibleStateChangeEvent(widget, changed))


class ScoreLabel(QLabel):
    accessible_role = QAccessible.Role.StaticText

    def __init__(self, text: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.value = value
        self.setAccessibleName(SCORE_ACCESSIBLE_NAME)

    def accessible_value(self) -> str:
        return self.value


class DisclosureButton(QToolButton):
    accessible_role = QAccessible.Role.Button

    def __init__(self, expanded: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.expanded = expanded

    def accessible_expanded(self) -> bool:
        return self.expanded

    def activate(self) -> None:
        self.click()


class DisclosureToggle(QPushButton):
    accessible_role = QAccessible.Role.Button

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.toggled.connect(lambda: announce_expanded(self))

    def accessible_expanded(self) -> bool:
        return self.isChecked()

    def activate(self) -> None:
        self.click()
