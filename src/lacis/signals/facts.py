from datetime import date

from lacis.storage.entities import Entity

FIRST_PLURAL = 2


def parsed_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:
        return day.replace(year=day.year - years, day=28)


def french_date(day: date) -> str:
    return day.strftime("%d/%m/%Y")


def counted(count: int, singular: str, plural: str) -> str:
    return f"{count} {singular if count < FIRST_PLURAL else plural}"


def creation_date(company: Entity) -> date | None:
    return parsed_date(company.attributes.get("creation_date"))


def activity(company: Entity) -> str | None:
    value = company.attributes.get("activity")
    return str(value) if value else None
