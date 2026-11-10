from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent
from PySide6.QtWidgets import QWidget

POLITE = QAccessible.AnnouncementPoliteness.Polite
ASSERTIVE = QAccessible.AnnouncementPoliteness.Assertive


def announce(
    widget: QWidget, message: str, politeness: QAccessible.AnnouncementPoliteness = ASSERTIVE
) -> None:
    announcement = QAccessibleAnnouncementEvent(widget, message)
    announcement.setPoliteness(politeness)
    QAccessible.updateAccessibility(announcement)
