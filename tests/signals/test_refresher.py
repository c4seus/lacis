from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from investigation_builder import InvestigationBuilder
from lacis.history import InvestigationHistory
from lacis.identity.decision_commands import RecordDecisionCommand
from lacis.signals.configuration import SignalConfigurationError
from lacis.signals.engine import SignalEngine
from lacis.signals.refresher import SignalRefresher
from lacis.signals.store import SignalReport, SignalStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import DATABASE_FILE_NAME, InvestigationLibrary

INVESTIGATION_NAME = "faux-plombiers-31"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "Qui se cache derrière les plombiers ?")
    return library


def refreshed_report(qtbot: QtBot, refresher: SignalRefresher) -> SignalReport:
    with qtbot.waitSignal(refresher.refreshed) as refreshed:
        refresher.refresh()
    [report] = refreshed.args
    assert isinstance(report, SignalReport)
    return report


def test_a_refresh_gives_the_current_signals(qtbot: QtBot, library: InvestigationLibrary) -> None:
    refresher = SignalRefresher(library, INVESTIGATION_NAME)
    report = refreshed_report(qtbot, refresher)
    with library.open(INVESTIGATION_NAME) as opened:
        assert report.revision == SignalStore(opened.connection).revision()


def test_each_homonym_decision_recomputes_the_signals(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        jean = builder.person("Jean", "DUPONT")
        jean_pierre = builder.person("Jean Pierre", "DUPONT")
        opened.connection.commit()
        refresher = SignalRefresher(library, INVESTIGATION_NAME)
        history = InvestigationHistory()
        refresher.follow(history)
        before = refreshed_report(qtbot, refresher)
        with qtbot.waitSignal(refresher.refreshed) as refreshed:
            history.record(
                RecordDecisionCommand(
                    HomonymDecisionStore(opened.connection),
                    jean,
                    jean_pierre,
                    HomonymDecision.SAME_PERSON,
                )
            )
        [after] = refreshed.args
        assert after.revision > before.revision
        with qtbot.waitSignal(refresher.refreshed) as undone:
            history.undo()
        assert undone.args[0].revision > after.revision


def test_a_configuration_problem_is_reported(qtbot: QtBot, library: InvestigationLibrary) -> None:
    def refused() -> SignalEngine:
        raise SignalConfigurationError("Le fichier signals.toml n'est pas valide.")

    refresher = SignalRefresher(library, INVESTIGATION_NAME, refused)
    with qtbot.waitSignal(refresher.failed) as failed:
        refresher.refresh()
    assert failed.args == ["Le fichier signals.toml n'est pas valide."]


def test_a_missing_investigation_is_reported(qtbot: QtBot, library: InvestigationLibrary) -> None:
    refresher = SignalRefresher(library, "absente")
    with qtbot.waitSignal(refresher.failed) as failed:
        refresher.refresh()
    assert failed.args == ["L'enquête « absente » est introuvable."]


def test_an_unreadable_investigation_is_reported(
    qtbot: QtBot, library: InvestigationLibrary
) -> None:
    (library.directory_of(INVESTIGATION_NAME) / DATABASE_FILE_NAME).write_bytes(b"pas SQLite")
    refresher = SignalRefresher(library, INVESTIGATION_NAME)
    with qtbot.waitSignal(refresher.failed) as failed:
        refresher.refresh()
    assert failed.args == ["La base de données de cette enquête est illisible."]
