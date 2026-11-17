from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QWidget

from lacis.review import ReviewNews
from lacis.ui import announcements

GROUPING_MILLISECONDS = 1000


class NewsAnnouncer(QObject):
    def __init__(self, widget: QWidget, delay_milliseconds: int = GROUPING_MILLISECONDS) -> None:
        super().__init__(widget)
        self.widget = widget
        self.pending = ReviewNews()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(delay_milliseconds)
        self.timer.timeout.connect(self.flush)

    def add(self, news: ReviewNews) -> None:
        if not news.message:
            return
        self.pending = self.pending | news
        self.timer.start()

    def forget(self) -> None:
        self.timer.stop()
        self.pending = ReviewNews()

    def flush(self) -> None:
        message = self.pending.message
        self.pending = ReviewNews()
        if message:
            announcements.announce(self.widget, message, announcements.POLITE)
