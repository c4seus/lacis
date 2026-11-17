from typing import Protocol, override, runtime_checkable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAccessible, QAccessibleActionInterface, QAccessibleInterface
from PySide6.QtWidgets import QAccessibleWidget, QLabel, QWidget

SCORE_ACCESSIBLE_NAME = "Score"
PRESS_ACTION = QAccessibleActionInterface.pressAction()


@runtime_checkable
class Activatable(Protocol):
    def activate(self) -> None: ...


@runtime_checkable
class Valued(Protocol):
    def accessible_value(self) -> str: ...


class DescribedWidget(QAccessibleWidget):
    @override
    def text(self, t: QAccessible.Text) -> str:
        widget = self.widget()
        if t is QAccessible.Text.Value and isinstance(widget, Valued):
            return widget.accessible_value()
        return super().text(t)

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


class ScoreLabel(QLabel):
    accessible_role = QAccessible.Role.StaticText

    def __init__(self, text: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.value = value
        self.setAccessibleName(SCORE_ACCESSIBLE_NAME)

    def accessible_value(self) -> str:
        return self.value
