import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLineEdit, QVBoxLayout, QWidget
from pytestqt.qtbot import QtBot

from accessibility_checks import interactive_widgets_without_accessible_name, tab_order
from lacis.design.icons import IconFactory
from lacis.ui.notifications import (
    MAXIMUM_NOTIFICATIONS,
    MAXIMUM_WIDTH,
    WINDOW_MARGIN,
    NotificationArea,
    NotificationKind,
)

SHORT_DURATION_MILLISECONDS = 50
ADDED = "ACME PLOMBERIE a été ajoutée à l'enquête."
FAILED = "Le service Recherche d'entreprises est indisponible. Réessayez plus tard."


class Host(QWidget):
    def __init__(self, icon_factory: IconFactory, duration: int) -> None:
        super().__init__()
        self.field = QLineEdit(self)
        self.field.setAccessibleName("Champ de saisie")
        QVBoxLayout(self).addWidget(self.field, 0, Qt.AlignmentFlag.AlignTop)
        self.area = NotificationArea(self, icon_factory, duration)


@pytest.fixture
def host(qtbot: QtBot, icon_factory: IconFactory) -> Host:
    window = Host(icon_factory, SHORT_DURATION_MILLISECONDS)
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    window.activateWindow()
    qtbot.waitUntil(window.isActiveWindow)
    window.field.setFocus()
    return window


def test_nothing_is_shown_without_notification(host: Host) -> None:
    assert not host.area.isVisible()
    assert host.area.notifications == []


def test_a_notification_appears_at_the_bottom_centre_of_the_window(host: Host) -> None:
    notification = host.area.notify(ADDED, NotificationKind.SUCCESS)
    assert notification.isVisible()
    assert notification.message_label.text() == ADDED
    assert notification.property("kind") == "success"
    area = host.area.geometry()
    assert area.width() == MAXIMUM_WIDTH
    assert area.center().x() in {host.width() // 2, host.width() // 2 - 1}
    assert area.bottom() + 1 == host.height() - WINDOW_MARGIN


def test_a_notification_never_takes_the_keyboard_focus(host: Host) -> None:
    host.area.notify(ADDED, NotificationKind.SUCCESS)
    host.area.notify(FAILED, NotificationKind.ERROR)
    assert host.field.hasFocus()
    assert QApplication.focusWidget() is host.field


def test_its_close_button_is_reached_with_tab_and_named(host: Host) -> None:
    notification = host.area.notify(FAILED, NotificationKind.ERROR)
    assert tab_order(host)[-1] is notification.close_button
    assert notification.close_button.accessibleName() == "Fermer la notification"
    assert interactive_widgets_without_accessible_name(host) == []


def test_a_notification_disappears_after_a_delay(qtbot: QtBot, host: Host) -> None:
    notification = host.area.notify(ADDED, NotificationKind.SUCCESS)
    assert not notification.stays
    qtbot.waitUntil(lambda: host.area.notifications == [], timeout=2000)
    assert not host.area.isVisible()


def test_an_information_disappears_too(qtbot: QtBot, host: Host) -> None:
    host.area.notify("Expansion terminée : 12 entités ajoutées.")
    qtbot.waitUntil(lambda: host.area.notifications == [], timeout=2000)


def test_an_error_stays_until_dismissed(qtbot: QtBot, host: Host) -> None:
    error = host.area.notify(FAILED, NotificationKind.ERROR)
    assert error.stays
    qtbot.wait(SHORT_DURATION_MILLISECONDS * 4)
    assert host.area.notifications == [error]
    QTest.mouseClick(error.close_button, Qt.MouseButton.LeftButton)
    assert host.area.notifications == []
    assert not host.area.isVisible()


def test_an_error_is_dismissed_with_the_keyboard(host: Host) -> None:
    error = host.area.notify(FAILED, NotificationKind.ERROR)
    error.close_button.setFocus()
    QTest.keyClick(error.close_button, Qt.Key.Key_Space)
    assert host.area.notifications == []


def test_dismissing_twice_does_nothing_more(host: Host) -> None:
    error = host.area.notify(FAILED, NotificationKind.ERROR)
    kept = host.area.notify(ADDED, NotificationKind.SUCCESS)
    error.dismiss()
    host.area.remove(error)
    assert host.area.notifications == [kept]


def test_notifications_pile_up_and_the_oldest_goes_first(host: Host) -> None:
    shown = [host.area.notify(f"Message {number}") for number in range(MAXIMUM_NOTIFICATIONS + 1)]
    assert host.area.notifications == shown[1:]
    first, second, _ = host.area.notifications
    assert first.y() < second.y()


def test_notifications_follow_the_size_of_the_window(host: Host) -> None:
    host.area.notify(ADDED, NotificationKind.SUCCESS)
    host.resize(400, 500)
    host.area.place()
    area = host.area.geometry()
    assert area.width() == 400 - 2 * WINDOW_MARGIN
    assert area.bottom() + 1 == 500 - WINDOW_MARGIN
