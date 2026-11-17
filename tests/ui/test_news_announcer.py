import pytest
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from lacis.review import ReviewNews
from lacis.ui import announcements
from lacis.ui.news_announcer import NewsAnnouncer

type Heard = list[tuple[str, QAccessible.AnnouncementPoliteness]]

PHOENIX = ReviewNews(frozenset({("phoenix_scheme", "company:1")}))
BURST = ReviewNews(frozenset({("creation_burst", "person:1")}))
HOMONYM = ReviewNews(homonyms=frozenset({("person:1", "person:2")}))


@pytest.fixture
def heard(monkeypatch: pytest.MonkeyPatch) -> Heard:
    messages: Heard = []

    def record(
        widget: QWidget,
        message: str,
        politeness: QAccessible.AnnouncementPoliteness = announcements.ASSERTIVE,
    ) -> None:
        messages.append((message, politeness))

    monkeypatch.setattr(announcements, "announce", record)
    return messages


@pytest.fixture
def announcer(qtbot: QtBot) -> NewsAnnouncer:
    widget = QWidget()
    qtbot.addWidget(widget)
    return NewsAnnouncer(widget, delay_milliseconds=20)


def test_news_found_close_together_are_announced_once_and_politely(
    qtbot: QtBot, announcer: NewsAnnouncer, heard: Heard
) -> None:
    announcer.add(PHOENIX)
    announcer.add(BURST)
    announcer.add(HOMONYM)
    assert heard == []
    qtbot.waitUntil(lambda: heard != [])
    assert heard == [
        (
            "À examiner : 2 nouveaux signaux d'alerte et 1 nouvel homonyme à vérifier.",
            announcements.POLITE,
        )
    ]


def test_nothing_new_is_not_announced(
    qtbot: QtBot, announcer: NewsAnnouncer, heard: Heard
) -> None:
    announcer.add(ReviewNews())
    assert not announcer.timer.isActive()
    announcer.flush()
    assert heard == []


def test_forgotten_news_are_never_announced(
    qtbot: QtBot, announcer: NewsAnnouncer, heard: Heard
) -> None:
    announcer.add(PHOENIX)
    announcer.forget()
    qtbot.wait(60)
    assert heard == []
