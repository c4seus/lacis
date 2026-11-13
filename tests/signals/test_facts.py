from datetime import UTC, date, datetime

from lacis.signals.facts import (
    activity,
    counted,
    creation_date,
    french_date,
    parsed_date,
    years_before,
)
from lacis.storage.entities import Entity, EntityKind

COLLECTED_AT = datetime(2026, 11, 2, tzinfo=UTC)


def company_with(attributes: dict[str, str | None]) -> Entity:
    return Entity(
        "company:100000001",
        EntityKind.COMPANY,
        "SOCIETE",
        dict(attributes),
        COLLECTED_AT,
        COLLECTED_AT,
    )


def test_dates_are_read_from_iso_texts() -> None:
    assert parsed_date("2022-11-10") == date(2022, 11, 10)
    assert parsed_date("2022-11-10T08:00:00+00:00") == date(2022, 11, 10)
    assert parsed_date(None) is None
    assert parsed_date("") is None
    assert parsed_date("bientôt") is None


def test_years_before_keep_the_day_or_fall_back_at_the_end_of_february() -> None:
    assert years_before(date(2026, 11, 10), 2) == date(2024, 11, 10)
    assert years_before(date(2024, 2, 29), 1) == date(2023, 2, 28)


def test_dates_are_written_the_french_way() -> None:
    assert french_date(date(2025, 9, 1)) == "01/09/2025"


def test_counts_are_plural_from_two() -> None:
    assert counted(0, "entreprise", "entreprises") == "0 entreprise"
    assert counted(1, "an", "ans") == "1 an"
    assert counted(2, "an", "ans") == "2 ans"


def test_a_company_gives_its_creation_date_and_activity() -> None:
    company = company_with({"creation_date": "2022-11-10", "activity": "43.22A"})
    assert creation_date(company) == date(2022, 11, 10)
    assert activity(company) == "43.22A"
    unknown = company_with({"activity": None})
    assert creation_date(unknown) is None
    assert activity(unknown) is None
