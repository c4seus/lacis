from datetime import date

from lacis.signals.context import InvestigationContext
from lacis.signals.facts import creation_date, parsed_date
from lacis.storage.comparison_keys import normalise_text
from lacis.storage.entities import Entity
from lacis.storage.notices import Notice, NoticeFamily, NoticeRole

DAYS_PER_MONTH = 30.4375
LIQUIDATION_WORD = "LIQUIDATION"


def closing_date(company: Entity) -> date | None:
    if company.attributes.get("is_active") is True:
        return None
    return parsed_date(company.attributes.get("closing_date"))


def months_between(first: date, second: date) -> float:
    return abs((second - first).days) / DAYS_PER_MONTH


def lifetime_months(company: Entity) -> float | None:
    created = creation_date(company)
    closed = closing_date(company)
    if created is None or closed is None or closed < created:
        return None
    return months_between(created, closed)


def insolvency_notices(context: InvestigationContext, company: Entity) -> list[Notice]:
    return [
        company_notice.notice
        for company_notice in context.notices_of(company.identifier).get(
            NoticeFamily.INSOLVENCY, []
        )
        if company_notice.role is NoticeRole.SUBJECT and not company_notice.notice.is_withdrawn
    ]


def mentions_liquidation(notices: list[Notice]) -> bool:
    return any(
        LIQUIDATION_WORD in normalise_text(f"{notice.judgment} {notice.summary}")
        for notice in notices
    )


def shown_months(months: float) -> str:
    return f"{round(months)} mois"
