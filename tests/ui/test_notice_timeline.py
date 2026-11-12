import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from pytestqt.qtbot import QtBot

from graph_scenario import PlumbersScenario, plumbers_scenario
from investigation_builder import COURT, InvestigationBuilder
from lacis.design.icons import IconFactory
from lacis.details import NoticeLine, entity_details
from lacis.storage.notices import NoticeFamily, NoticeRole
from lacis.ui.entity_sheet import EntitySheet
from lacis.ui.notice_timeline import NoticeTimeline

REMOVAL = NoticeLine(
    "A202300000001",
    NoticeFamily.REMOVAL,
    date(2023, 1, 20),
    "Radiation du registre du commerce et des sociétés",
    COURT,
    "",
    4,
    NoticeRole.SUBJECT,
)
SALE = NoticeLine(
    "A202200000002",
    NoticeFamily.SALE,
    date(2022, 3, 1),
    "Vente du fonds",
    COURT,
    "",
    5,
    NoticeRole.PREVIOUS_OWNER,
    datetime(2026, 11, 12, 10, 0, tzinfo=UTC),
)
CLOSING = NoticeLine(
    "A202200000003",
    NoticeFamily.INSOLVENCY,
    date(2022, 12, 5),
    "Clôture pour insuffisance d'actif",
    COURT,
    "Jugement du 28/11/2022",
    6,
    NoticeRole.SUBJECT,
)


@pytest.fixture
def timeline(qtbot: QtBot, icon_factory: IconFactory) -> NoticeTimeline:
    timeline = NoticeTimeline((REMOVAL, CLOSING, SALE), icon_factory.colours_provider)
    qtbot.addWidget(timeline)
    timeline.resize(400, 600)
    timeline.show()
    return timeline


def test_each_notice_shows_its_date_family_summary_and_court(timeline: NoticeTimeline) -> None:
    removal, closing, sale = timeline.items
    assert removal.date_label.text() == "20/01/2023"
    assert removal.family_badge.text() == "Radiation"
    assert removal.family_badge.property("tone") == "badge-high"
    assert removal.summary_label.text() == REMOVAL.summary
    assert removal.court_label.text() == COURT
    assert not removal.withdrawn_badge.isVisible()
    assert removal.notes == []
    assert [note.text() for note in closing.notes] == ["Jugement : Jugement du 28/11/2022"]
    assert sale.family_badge.property("tone") == "badge-outline"
    assert timeline.accessibleName() == "Annonces BODACC"
    assert removal.accessibleName() == (
        "20/01/2023, Radiation, Radiation du registre du commerce et des sociétés"
    )


def test_a_withdrawn_notice_is_shown_as_such(timeline: NoticeTimeline) -> None:
    sale = timeline.items[2]
    assert sale.withdrawn_badge.isVisible()
    assert sale.withdrawn_badge.text() == "Retirée"
    assert sale.summary_label.property("tone") == "notice-withdrawn"
    assert [note.text() for note in sale.notes] == [
        "En tant qu'ancien propriétaire",
        "Absente du BODACC au rafraîchissement du 12/11/2026",
    ]
    assert sale.accessibleName().endswith(", retirée")
    assert sale.property("withdrawn") is True


def test_the_dots_follow_the_notices(timeline: NoticeTimeline) -> None:
    centres = timeline.dot_centres()
    assert [centre.y() for centre in centres] == sorted(centre.y() for centre in centres)
    assert len(centres) == 3
    timeline.grab()


def test_a_company_without_notices_says_so(qtbot: QtBot, icon_factory: IconFactory) -> None:
    timeline = NoticeTimeline((), icon_factory.colours_provider)
    qtbot.addWidget(timeline)
    assert timeline.items == []
    assert timeline.empty_label is not None
    assert timeline.empty_label.text() == "Aucune annonce collectée pour cette entreprise."
    timeline.grab()


def test_a_notice_without_summary_shows_its_family(
    qtbot: QtBot, icon_factory: IconFactory
) -> None:
    timeline = NoticeTimeline((replace(REMOVAL, summary=""),), icon_factory.colours_provider)
    qtbot.addWidget(timeline)
    assert timeline.items[0].summary_label.text() == "Radiation"


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def test_the_sheet_of_a_company_shows_its_notices(
    qtbot: QtBot,
    icon_factory: IconFactory,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
) -> None:
    builder.notice(scenario.dupont_services, NoticeFamily.REMOVAL, date(2023, 1, 20), "Radiation")
    sheet = EntitySheet(icon_factory)
    qtbot.addWidget(sheet)
    details = entity_details(builder.connection, scenario.dupont_services, None)
    sheet.show_details(details)
    assert sheet.timeline is not None
    assert sheet.section_titles[0].accessibleName() == "Annonces BODACC, 1"


def test_only_companies_have_notices_in_their_sheet(
    qtbot: QtBot,
    icon_factory: IconFactory,
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
) -> None:
    sheet = EntitySheet(icon_factory)
    qtbot.addWidget(sheet)
    sheet.show_details(entity_details(builder.connection, scenario.jean, None))
    assert sheet.timeline is None
