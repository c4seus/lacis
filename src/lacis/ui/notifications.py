from enum import StrEnum

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from lacis.design.icons import IconFactory
from lacis.ui import announcements
from lacis.ui.header_bar import create_icon_button

NOTIFICATION_DURATION_MILLISECONDS = 6000
MAXIMUM_NOTIFICATIONS = 3
MAXIMUM_WIDTH = 480
WINDOW_MARGIN = 24
NOTIFICATION_SPACING = 8
CLOSE_TEXT = "Fermer la notification"
CLOSE_TOOLTIP = "Fermer"


class NotificationKind(StrEnum):
    SUCCESS = "success"
    INFORMATION = "information"
    ERROR = "error"


class Notification(QFrame):
    dismissed = Signal(QFrame)

    def __init__(
        self,
        message: str,
        kind: NotificationKind,
        icon_factory: IconFactory,
        duration_milliseconds: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.message = message
        self.kind = kind
        self.setObjectName("notification")
        self.setProperty("kind", kind.value)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAccessibleName(message)
        self.message_label = QLabel(message, self)
        self.message_label.setWordWrap(True)
        self.close_button = create_icon_button(
            icon_factory.icon("close"), CLOSE_TEXT, CLOSE_TOOLTIP, self
        )
        self.close_button.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.close_button.clicked.connect(self.dismiss)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 8, 8)
        layout.setSpacing(10)
        layout.addWidget(self.message_label, 1)
        layout.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.expiry = QTimer(self)
        self.expiry.setSingleShot(True)
        self.expiry.setInterval(duration_milliseconds)
        self.expiry.timeout.connect(self.dismiss)
        if kind is not NotificationKind.ERROR:
            self.expiry.start()

    @property
    def stays(self) -> bool:
        return not self.expiry.isActive()

    def dismiss(self) -> None:
        self.expiry.stop()
        self.dismissed.emit(self)


class NotificationArea(QWidget):
    def __init__(
        self,
        host: QWidget,
        icon_factory: IconFactory,
        duration_milliseconds: int = NOTIFICATION_DURATION_MILLISECONDS,
    ) -> None:
        super().__init__(host)
        self.host = host
        self.icon_factory = icon_factory
        self.duration_milliseconds = duration_milliseconds
        self.notifications: list[Notification] = []
        self.setObjectName("notificationArea")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.stack = QVBoxLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(NOTIFICATION_SPACING)
        self.hide()

    def notify(
        self, message: str, kind: NotificationKind = NotificationKind.INFORMATION
    ) -> Notification:
        notification = Notification(
            message, kind, self.icon_factory, self.duration_milliseconds, self
        )
        notification.dismissed.connect(self.remove)
        self.stack.addWidget(notification)
        self.notifications.append(notification)
        while len(self.notifications) > MAXIMUM_NOTIFICATIONS:
            self.remove(self.notifications[0])
        politeness = (
            announcements.ASSERTIVE if kind is NotificationKind.ERROR else announcements.POLITE
        )
        announcements.announce(notification, message, politeness)
        notification.show()
        self.place()
        return notification

    def remove(self, notification: QFrame) -> None:
        if notification not in self.notifications:
            return
        self.notifications.remove(notification)
        self.stack.removeWidget(notification)
        notification.hide()
        notification.deleteLater()
        self.place()

    def place(self) -> None:
        if not self.notifications:
            self.hide()
            return
        width = min(MAXIMUM_WIDTH, max(self.host.width() - 2 * WINDOW_MARGIN, 0))
        self.stack.activate()
        height_for_width = self.stack.totalHeightForWidth(width)
        height = height_for_width if height_for_width > 0 else self.sizeHint().height()
        left = (self.host.width() - width) // 2
        top = self.host.height() - height - WINDOW_MARGIN
        self.setGeometry(left, top, width, height)
        self.show()
        self.raise_()
