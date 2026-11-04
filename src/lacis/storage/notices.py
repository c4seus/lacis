import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from lacis.storage.entities import EntityKind, kind_of
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


class NoticeRole(StrEnum):
    SUBJECT = "subject"
    PREVIOUS_OPERATOR = "previous_operator"
    PREVIOUS_OWNER = "previous_owner"
    MENTIONED = "mentioned"


class InvalidNoticeError(ValueError):
    pass


NOTICE_COLUMNS = (
    "identifier, family, published_on, court, judgment, summary, response_identifier, "
    "first_collected_at, last_collected_at"
)

REPLACE_ROLE = "DO UPDATE SET role = excluded.role"
KEEP_ROLE = "DO NOTHING"


@dataclass(frozen=True)
class CollectedNotice:
    identifier: str
    family: NoticeFamily
    published_on: date
    court: str
    summary: str
    judgment: str = ""
    companies: dict[str, NoticeRole] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for company_identifier in self.companies:
            if kind_of(company_identifier) is not EntityKind.COMPANY:
                raise InvalidNoticeError(f"A notice concerns companies, not {company_identifier}")


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


@dataclass(frozen=True)
class CompanyNotice:
    notice: Notice
    role: NoticeRole


class NoticeStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_notice(self, collected_notice: CollectedNotice, response: ResponseSummary) -> Notice:
        with self.connection:
            existing = self.notice(collected_notice.identifier)
            is_newest = existing is None or response.collected_at >= existing.last_collected_at
            if existing is None:
                self.insert_notice(collected_notice, response)
            elif is_newest:
                self.update_notice(collected_notice, response)
            else:
                self.move_first_collection_back(existing, response.collected_at)
            self.save_roles(collected_notice, replace_known_roles=is_newest)
        return self.require_notice(collected_notice.identifier)

    def insert_notice(self, collected_notice: CollectedNotice, response: ResponseSummary) -> None:
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
                response.collected_at.isoformat(),
                response.collected_at.isoformat(),
            ),
        )

    def update_notice(self, collected_notice: CollectedNotice, response: ResponseSummary) -> None:
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
                response.collected_at.isoformat(),
                collected_notice.identifier,
            ),
        )

    def move_first_collection_back(self, existing: Notice, collected_at: datetime) -> None:
        self.connection.execute(
            "UPDATE notice SET first_collected_at = ? WHERE identifier = ?",
            (min(existing.first_collected_at, collected_at).isoformat(), existing.identifier),
        )

    def save_roles(self, collected_notice: CollectedNotice, replace_known_roles: bool) -> None:
        conflict_action = REPLACE_ROLE if replace_known_roles else KEEP_ROLE
        for company_identifier, role in collected_notice.companies.items():
            self.connection.execute(
                f"""
                INSERT INTO notice_company (notice_identifier, company_identifier, role)
                VALUES (?, ?, ?)
                ON CONFLICT (notice_identifier, company_identifier) {conflict_action}
                """,
                (collected_notice.identifier, company_identifier, role.value),
            )

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

    def notices_of_company(
        self, company_identifier: str
    ) -> dict[NoticeFamily, list[CompanyNotice]]:
        rows = self.connection.execute(
            f"""
            SELECT {", ".join(f"notice.{column}" for column in NOTICE_COLUMNS.split(", "))},
                notice_company.role
            FROM notice
            JOIN notice_company ON notice_company.notice_identifier = notice.identifier
            WHERE notice_company.company_identifier = ?
            ORDER BY notice.published_on DESC, notice.identifier
            """,
            (company_identifier,),
        ).fetchall()
        notices_by_family: dict[NoticeFamily, list[CompanyNotice]] = {}
        for *notice_row, role in rows:
            notice = notice_from_row(tuple(notice_row))
            notices_by_family.setdefault(notice.family, []).append(
                CompanyNotice(notice, NoticeRole(role))
            )
        return notices_by_family
