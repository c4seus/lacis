from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtTest import QTest
from pytestqt.qtbot import QtBot

from lacis.design.icons import IconFactory
from lacis.storage.collection_log import RequestStatus
from lacis.storage.responses import ResponseSource
from lacis.tables import NO_SCORE_TEXT, LogRow
from lacis.ui.data_table import IDENTIFIER_ROLE, TONE_ROLE
from lacis.ui.journal_table import JournalTab, LogColumn

REQUESTED_AT = datetime(2026, 11, 2, 8, 9, 31, tzinfo=UTC)
ENDPOINT = "https://recherche-entreprises.api.gouv.fr/search"
ROWS = (
    LogRow(
        1,
        REQUESTED_AT,
        ResponseSource.COMPANY_REGISTER,
        ENDPOINT,
        200,
        timedelta(milliseconds=184),
        False,
        RequestStatus.SUCCEEDED,
        response_identifier=7,
        parameters={"q": "111111111"},
        fingerprint="a" * 64,
    ),
    LogRow(
        2,
        REQUESTED_AT + timedelta(seconds=5),
        ResponseSource.COMPANY_REGISTER,
        ENDPOINT,
        None,
        timedelta(milliseconds=2),
        True,
        RequestStatus.SUCCEEDED,
        response_identifier=7,
        parameters={"q": "111111111"},
        fingerprint="a" * 64,
    ),
    LogRow(
        3,
        REQUESTED_AT + timedelta(seconds=10),
        ResponseSource.BODACC,
        "https://bodacc-datadila.opendatasoft.com/api/records",
        503,
        timedelta(milliseconds=30),
        False,
        RequestStatus.FAILED,
        error="Le service BODACC est indisponible.",
    ),
    LogRow(
        4,
        REQUESTED_AT + timedelta(seconds=12),
        ResponseSource.BODACC,
        "https://bodacc-datadila.opendatasoft.com/api/records",
        None,
        timedelta(milliseconds=30),
        False,
        RequestStatus.FAILED,
        error="Le service BODACC est injoignable.",
    ),
)


@pytest.fixture
def tab(qtbot: QtBot, icon_factory: IconFactory) -> JournalTab:
    tab = JournalTab(icon_factory.colours_provider)
    qtbot.addWidget(tab)
    tab.resize(420, 400)
    tab.show_rows(ROWS)
    tab.show()
    return tab


def cell(tab: JournalTab, row: int, column: LogColumn, role: int = 0) -> object:
    return tab.proxy.index(row, column).data(role)


def test_the_log_shows_the_most_recent_requests_first(tab: JournalTab) -> None:
    assert [cell(tab, row, LogColumn.STATUS) for row in range(4)] == [
        "Échec",
        "503",
        NO_SCORE_TEXT,
        "200",
    ]
    assert cell(tab, 3, LogColumn.REQUEST) == "Recherche · 111111111"
    assert cell(tab, 2, LogColumn.ORIGIN) == "cache"
    assert cell(tab, 3, LogColumn.TIME) == REQUESTED_AT.astimezone().strftime("%H:%M:%S")
    assert tab.summary_label.text() == "4 requêtes · 1 servie par le cache · 2 échecs"
    tab.table.sortByColumn(LogColumn.REQUEST, Qt.SortOrder.AscendingOrder)
    assert cell(tab, 0, LogColumn.REQUEST) == "BODACC · /api/records"


def test_each_cell_is_described_for_a_screen_reader(tab: JournalTab) -> None:
    spoken = Qt.ItemDataRole.AccessibleTextRole
    assert tab.table.accessibleName() == "Journal de collecte"
    assert not tab.table.tabKeyNavigation()
    assert cell(tab, 3, LogColumn.TIME, spoken) == ROWS[0].full_time
    assert cell(tab, 3, LogColumn.STATUS, spoken) == "200, requête réussie"
    assert cell(tab, 0, LogColumn.STATUS, spoken) == "Échec, requête en échec"
    assert cell(tab, 2, LogColumn.ORIGIN, spoken) == "servie par le cache"
    assert cell(tab, 3, LogColumn.REQUEST, spoken) == "Recherche · 111111111"
    assert cell(tab, 3, LogColumn.REQUEST, Qt.ItemDataRole.ToolTipRole) == ROWS[0].description
    assert cell(tab, 3, LogColumn.STATUS, TONE_ROLE) == "active"
    assert cell(tab, 1, LogColumn.STATUS, TONE_ROLE) == "high"
    assert cell(tab, 0, LogColumn.STATUS, TONE_ROLE) == "high"
    assert cell(tab, 2, LogColumn.STATUS, TONE_ROLE) is None
    assert cell(tab, 2, LogColumn.ORIGIN, TONE_ROLE) == "information"
    assert cell(tab, 3, LogColumn.ORIGIN, TONE_ROLE) == "outline"
    assert cell(tab, 3, LogColumn.REQUEST, TONE_ROLE) is None
    assert cell(tab, 3, LogColumn.REQUEST, IDENTIFIER_ROLE) == 7
    assert cell(tab, 3, LogColumn.REQUEST, Qt.ItemDataRole.DecorationRole) is None
    model = tab.model
    assert model.data(QModelIndex()) is None
    assert model.rowCount(model.index(0, 0)) == 0
    assert model.columnCount(model.index(0, 0)) == 0
    assert [model.headerData(column, Qt.Orientation.Horizontal) for column in LogColumn] == [
        "Heure",
        "Requête",
        "Statut",
        "Origine",
    ]
    assert model.headerData(0, Qt.Orientation.Vertical) is None
    tab.table.grab()


def test_the_raw_response_of_a_request_opens_from_the_keyboard(
    qtbot: QtBot, tab: JournalTab
) -> None:
    assert not tab.raw_button.isEnabled()
    assert tab.raw_button.toolTip() == "Cette requête n'a pas enregistré de réponse."
    tab.table.selectRow(0)
    assert not tab.raw_button.isEnabled()
    tab.raw_button.click()
    tab.open_current()
    with qtbot.assertNotEmitted(tab.raw_requested):
        tab.table.activated.emit(tab.proxy.index(0, 0))
    tab.table.selectRow(3)
    assert tab.raw_button.isEnabled()
    assert tab.raw_button.toolTip() == ""
    with qtbot.waitSignal(tab.raw_requested) as requested:
        tab.raw_button.click()
    assert requested.args == [7]
    with qtbot.waitSignal(tab.raw_requested) as requested:
        tab.table.activated.emit(tab.proxy.index(3, 0))
    assert requested.args == [7]
    tab.table.setFocus()
    QTest.keyClick(tab.table, Qt.Key.Key_Up)
    assert tab.current_response() == 7
    tab.show_rows(())
    assert tab.summary_label.text() == "Aucune requête pour l'instant"
    assert not tab.raw_button.isEnabled()
