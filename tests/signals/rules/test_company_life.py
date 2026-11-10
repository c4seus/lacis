import sqlite3
from datetime import date

import pytest

from investigation_builder import InvestigationBuilder
from lacis.signals.rules.company_life import (
    closing_date,
    insolvency_notices,
    lifetime_months,
    mentions_liquidation,
    months_between,
    shown_months,
)
from lacis.storage.notices import NoticeFamily


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


def test_an_active_company_has_no_closing_date(builder: InvestigationBuilder) -> None:
    active = builder.company("ACTIVE", date(2024, 1, 10))
    closed = builder.company("FERMEE", date(2024, 1, 10), closing_date=date(2024, 5, 10))
    context = builder.context()
    assert closing_date(context.entities[active]) is None
    assert closing_date(context.entities[closed]) == date(2024, 5, 10)


def test_the_lifetime_runs_from_creation_to_closing(builder: InvestigationBuilder) -> None:
    closed = builder.company("FERMEE", date(2024, 1, 10), closing_date=date(2025, 1, 10))
    assert lifetime_months(builder.context().entities[closed]) == pytest.approx(366 / 30.4375)
    assert months_between(date(2023, 1, 15), date(2022, 11, 10)) == pytest.approx(66 / 30.4375)
    assert shown_months(2.17) == "2 mois"


def test_insolvency_notices_and_liquidations_are_found(builder: InvestigationBuilder) -> None:
    company = builder.company("FERMEE", date(2024, 1, 10), closing_date=date(2025, 1, 10))
    builder.notice(company, NoticeFamily.REMOVAL, date(2025, 1, 20), "Radiation.")
    builder.notice(
        company, NoticeFamily.INSOLVENCY, date(2024, 6, 3), "Jugement de redressement judiciaire"
    )
    notices = insolvency_notices(builder.context(), builder.context().entities[company])
    assert len(notices) == 1
    assert not mentions_liquidation(notices)
    builder.notice(
        company,
        NoticeFamily.INSOLVENCY,
        date(2024, 9, 3),
        "Jugement de conversion en liquidation judiciaire",
    )
    assert mentions_liquidation(
        insolvency_notices(builder.context(), builder.context().entities[company])
    )
