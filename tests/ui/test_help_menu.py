import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from pytestqt.qtbot import QtBot

from lacis.ui.help_menu import HelpMenu


@pytest.fixture
def opened_urls(monkeypatch: pytest.MonkeyPatch) -> list[QUrl]:
    urls: list[QUrl] = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(urls.append))
    return urls


def test_the_help_menu_lists_documentation_then_problem_reporting(qtbot: QtBot) -> None:
    help_menu = HelpMenu()
    qtbot.addWidget(help_menu)
    assert help_menu.title() == "Ai&de"
    assert [action.text() for action in help_menu.actions()] == [
        "&Documentation",
        "&Signaler un problème…",
    ]


def test_f1_opens_the_documentation(qtbot: QtBot, opened_urls: list[QUrl]) -> None:
    help_menu = HelpMenu()
    qtbot.addWidget(help_menu)
    assert help_menu.documentation_action.shortcut() == QKeySequence("F1")
    help_menu.documentation_action.trigger()
    assert opened_urls == [QUrl("https://github.com/c4seus/lacis#readme")]


def test_reporting_a_problem_opens_the_issue_forms(qtbot: QtBot, opened_urls: list[QUrl]) -> None:
    help_menu = HelpMenu()
    qtbot.addWidget(help_menu)
    help_menu.report_problem_action.trigger()
    assert opened_urls == [QUrl("https://github.com/c4seus/lacis/issues/new/choose")]
