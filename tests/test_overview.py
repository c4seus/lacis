import sqlite3
from datetime import date
from pathlib import Path

import pytest

from investigation_builder import InvestigationBuilder
from lacis.overview import overview_of, read_overview
from lacis.signals.configuration import SignalConfigurationError
from lacis.signals.engine import SignalEngine
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import InvestigationLibrary

BURST_DATES = (date(2025, 1, 10), date(2025, 2, 1), date(2025, 3, 15))


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


def test_an_empty_investigation_has_nothing_to_count(
    investigation_connection: sqlite3.Connection,
) -> None:
    overview = overview_of(investigation_connection, SignalEngine.configured())
    assert (
        overview.entities,
        overview.links,
        overview.confirmed_homonyms,
        overview.pending_homonyms,
        overview.leads,
        overview.signals,
    ) == (0, 0, 0, 0, 0, 0)


def test_the_overview_counts_entities_links_homonyms_leads_and_signals(
    builder: InvestigationBuilder,
) -> None:
    jean = builder.person("Jean", "DUPONT")
    jean_pierre = builder.person("Jean Pierre", "DUPONT")
    marie = builder.person("Marie", "DUPONT")
    marie_claire = builder.person("Marie Claire", "DUPONT")
    builder.person("Paul", "MARTIN")
    builder.person("Paul Louis", "MARTIN")
    for position, day in enumerate(BURST_DATES):
        builder.mandate(jean, builder.company(f"SOCIETE {position}", day))
    builder.same_person(jean, jean_pierre)
    HomonymDecisionStore(builder.connection).record(
        marie, marie_claire, HomonymDecision.DIFFERENT_PERSON
    )
    overview = overview_of(builder.connection, SignalEngine.configured())
    assert overview.entities == 9
    assert overview.links == 3
    assert overview.confirmed_homonyms == 1
    assert overview.pending_homonyms == 1
    assert overview.leads == 9
    assert overview.signals == 1
    assert overview.signal_problem == ""


def test_an_overview_without_engine_has_no_signal_count(
    investigation_connection: sqlite3.Connection,
) -> None:
    overview = overview_of(investigation_connection, None, "Réglages invalides.")
    assert overview.signals is None
    assert overview.report is None
    assert overview.signal_problem == "Réglages invalides."


def test_an_overview_is_read_from_an_investigation_of_the_library(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", "Qui se cache derrière les plombiers ?")
    assert read_overview(library, "faux-plombiers-31").signals == 0

    def refused() -> SignalEngine:
        raise SignalConfigurationError("Le fichier signals.toml n'est pas valide.")

    overview = read_overview(library, "faux-plombiers-31", refused)
    assert overview.signals is None
    assert overview.signal_problem == "Le fichier signals.toml n'est pas valide."
