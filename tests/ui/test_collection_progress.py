from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAccessible
from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.collectors.environment import demo_collection_environment
from lacis.design.icons import IconFactory
from lacis.design.theme_controller import ThemeController
from lacis.graph.background import investigation_lock
from lacis.graph.progress import ExpansionProgress
from lacis.review import RunningCollection
from lacis.storage.entities import EntityKind
from lacis.storage.investigations import InvestigationLibrary
from lacis.ui import announcements
from lacis.ui.collection_progress import CollectionProgressPanel
from lacis.ui.investigation_columns import OVERLAY_MARGIN, GraphArea
from lacis.ui.main_window import MainWindow

INVESTIGATION_NAME = "faux-plombiers-31"
WAIT_MILLISECONDS = 10_000
ACME = RunningCollection("company:111111111", "Extension de ACME PLOMBERIE")
NOTICES = RunningCollection("company:222222222", "Rafraîchissement des annonces de DUPONT")

type Heard = list[tuple[str, QAccessible.AnnouncementPoliteness]]


@pytest.fixture
def panel(qtbot: QtBot) -> CollectionProgressPanel:
    panel = CollectionProgressPanel()
    qtbot.addWidget(panel)
    return panel


def test_each_running_collection_shows_its_progress_and_a_cancel_button(
    panel: CollectionProgressPanel,
) -> None:
    assert not panel.isVisibleTo(panel.parentWidget() or panel)
    panel.show_collections((ACME, NOTICES))
    assert panel.isVisibleTo(panel)
    assert panel.accessibleName() == "Collectes en cours"
    row = panel.rows[ACME.identifier]
    assert row.title_label.text() == "Extension de ACME PLOMBERIE"
    assert row.status_label.text() == "Démarrage…"
    assert row.bar.maximum() == 0
    assert row.bar.accessibleName() == "Extension de ACME PLOMBERIE"
    assert row.cancel_button.text() == "Annuler"
    assert row.cancel_button.accessibleName() == "Annuler : Extension de ACME PLOMBERIE"
    panel.show_collections((replace(ACME, progress=ExpansionProgress(4, 2)), NOTICES))
    assert panel.rows[ACME.identifier] is row
    assert row.status_label.text() == "4 requêtes, 2 nouvelles entités"
    assert row.bar.accessibleDescription() == "4 requêtes, 2 nouvelles entités"


def test_the_cancel_button_asks_once_then_waits(
    qtbot: QtBot, panel: CollectionProgressPanel
) -> None:
    panel.show_collections((ACME,))
    row = panel.rows[ACME.identifier]
    with qtbot.waitSignal(panel.cancel_requested) as requested:
        row.cancel_button.click()
    assert requested.args == [ACME.identifier]
    panel.show_collections((replace(ACME, cancelling=True),))
    assert not row.cancel_button.isEnabled()
    assert row.status_label.text() == "Annulation en cours…"


def test_the_panel_hides_once_nothing_runs(panel: CollectionProgressPanel) -> None:
    panel.show_collections((ACME, NOTICES))
    panel.show_collections((NOTICES,))
    assert list(panel.rows) == [NOTICES.identifier]
    panel.show_collections(())
    assert panel.rows == {}
    assert not panel.isVisibleTo(panel)


def test_the_panel_sits_at_the_top_right_of_the_graph(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    area = GraphArea(icon_factory)
    qtbot.addWidget(area)
    area.resize(900, 600)
    area.show()
    area.show_collections((ACME,))
    area.show_collections((ACME, NOTICES))
    panel = area.progress_panel
    assert all(row.isVisibleTo(panel) for row in panel.rows.values())
    assert panel.height() == panel.rows_layout.totalHeightForWidth(panel.width())
    assert panel.isVisible()
    assert panel.geometry().right() == area.width() - OVERLAY_MARGIN - 1
    assert panel.y() == OVERLAY_MARGIN
    row = panel.rows[ACME.identifier]
    assert row.geometry().bottom() < panel.height()
    assert row.status_label.height() >= row.status_label.sizeHint().height()
    area.grab()


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        builder.mandate(
            builder.person("Jean", "DUPONT"),
            builder.company("SOCIETE", date(2024, 5, 2), identifier="company:111111111"),
        )
    return library


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
def window(
    qtbot: QtBot,
    settings: QSettings,
    theme_controller: ThemeController,
    library: InvestigationLibrary,
) -> MainWindow:
    window = MainWindow(settings, theme_controller, demo_collection_environment(), library)
    qtbot.addWidget(window)
    window.resize(1440, 900)
    window.show()
    window.open_investigation(INVESTIGATION_NAME)
    qtbot.waitUntil(lambda: window.layout_job is None)
    return window


def select_company(window: MainWindow) -> str:
    page = window.investigation_page
    company = next(
        node.identifier
        for node in page.graph_view.drawing.nodes
        if node.kind is EntityKind.COMPANY
    )
    page.show_entity(company, "")
    return company


def test_an_expansion_shows_its_progress_and_is_announced_at_start_and_end(
    qtbot: QtBot, window: MainWindow, heard: Heard
) -> None:
    select_company(window)
    panel = window.investigation_page.graph_area.progress_panel
    heard.clear()
    window.main_menu_bar.expand_action.trigger()
    assert panel.isVisible()
    assert heard[0] == ("Extension de SOCIETE en cours…", announcements.POLITE)
    qtbot.waitUntil(lambda: not window.review_actions.expansions, timeout=WAIT_MILLISECONDS)
    assert not panel.isVisible()
    message, politeness = heard[-1]
    assert message.startswith("Extension de SOCIETE terminée : ")
    assert politeness == announcements.POLITE


def test_an_expansion_is_cancelled_from_its_progress(
    qtbot: QtBot, window: MainWindow, library: InvestigationLibrary, heard: Heard
) -> None:
    company = select_company(window)
    panel = window.investigation_page.graph_area.progress_panel
    lock = investigation_lock(window.collection_settings(INVESTIGATION_NAME))
    lock.acquire()
    try:
        window.main_menu_bar.expand_action.trigger()
        row = panel.rows[company]
        with qtbot.waitSignal(window.review_actions.changed, timeout=WAIT_MILLISECONDS):
            row.cancel_button.click()
    finally:
        lock.release()
    assert not panel.isVisible()
    assert window.main_menu_bar.expand_action.isEnabled()
    assert heard[-1] == (
        "Extension de SOCIETE annulée : rien n'a été ajouté",
        announcements.POLITE,
    )
    assert window.notification_area.notifications[-1].message == heard[-1][0]
