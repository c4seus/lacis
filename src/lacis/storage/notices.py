import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from lacis.storage.responses import ResponseSummary


class NoticeFamily(StrEnum):
    CREATION = "creation"
    REGISTRATION = "registration"
    AMENDMENT = "amendment"
    INSOLVENCY = "insolvency"
    CONCILIATION = "conciliation"
    PROFESSIONAL_RECOVERY = "professional_recovery"
    SALE = "sale"
    ACCOUNTS = "accounts"
    REMOVAL = "removal"
    MISCELLANEOUS = "miscellaneous"


NOTICE_COLUMNS = (
    "identifier, family, published_on, court, judgment, summary, response_identifier, "
    "first_collected_at, last_collected_at"
)


@dataclass(frozen=True)
class CollectedNotice:
    identifier: str
    family: NoticeFamily
    published_on: date
    court: str
    summary: str
    judgment: str = ""


@dataclass(frozen=True)
class Notice:
    identifier: str
    family: NoticeFamily
    published_on: date
    court: str
    judgment: str
    summary: str
    response_identifier: int
    first_collected_at: datetime
    last_collected_at: datetime


def notice_from_row(row: tuple[str, str, str, str, str, str, int, str, str]) -> Notice:
    (
        identifier,
        family,
        published_on,
        court,
        judgment,
        summary,
        response_identifier,
        first_collected_at,
        last_collected_at,
    ) = row
    return Notice(
        identifier=identifier,
        family=NoticeFamily(family),
        published_on=date.fromisoformat(published_on),
        court=court,
        judgment=judgment,
        summary=summary,
        response_identifier=response_identifier,
        first_collected_at=datetime.fromisoformat(first_collected_at),
        last_collected_at=datetime.fromisoformat(last_collected_at),
    )


class NoticeStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_notice(self, collected_notice: CollectedNotice, response: ResponseSummary) -> Notice:
        collected_at = response.collected_at
        with self.connection:
            existing = self.notice(collected_notice.identifier)
            if existing is None:
                self.connection.execute(
                    f"INSERT INTO notice ({NOTICE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        collected_notice.identifier,
                        collected_notice.family.value,
                        collected_notice.published_on.isoformat(),
                        collected_notice.court,
                        collected_notice.judgment,
                        collected_notice.summary,
                        response.identifier,
                        collected_at.isoformat(),
                        collected_at.isoformat(),
                    ),
                )
            elif collected_at >= existing.last_collected_at:
                self.connection.execute(
                    """
                    UPDATE notice
                    SET family = ?, published_on = ?, court = ?, judgment = ?, summary = ?,
                        response_identifier = ?, last_collected_at = ?
                    WHERE identifier = ?
                    """,
                    (
                        collected_notice.family.value,
                        collected_notice.published_on.isoformat(),
                        collected_notice.court,
                        collected_notice.judgment,
                        collected_notice.summary,
                        response.identifier,
                        collected_at.isoformat(),
                        collected_notice.identifier,
                    ),
                )
            else:
                self.connection.execute(
                    "UPDATE notice SET first_collected_at = ? WHERE identifier = ?",
                    (
                        min(existing.first_collected_at, collected_at).isoformat(),
                        collected_notice.identifier,
                    ),
                )
        return self.require_notice(collected_notice.identifier)

    def notice(self, identifier: str) -> Notice | None:
        row = self.connection.execute(
            f"SELECT {NOTICE_COLUMNS} FROM notice WHERE identifier = ?", (identifier,)
        ).fetchone()
        return notice_from_row(row) if row is not None else None

    def require_notice(self, identifier: str) -> Notice:
        notice = self.notice(identifier)
        if notice is None:
            raise KeyError(identifier)
        return notice
