import json
from dataclasses import dataclass
from typing import Any

from lacis.collectors.company_register import siren_of
from lacis.collectors.endpoints import BODACC_RECORDS_URL, MAXIMUM_NOTICES_PER_PAGE
from lacis.collectors.http_client import SOURCE_NAMES, CollectionError, CollectorHttpClient
from lacis.storage.responses import ResponseSource, ResponseSummary, StoredResponse

SOURCE = ResponseSource.BODACC
DEFAULT_MAXIMUM_PAGES = 10


@dataclass(frozen=True)
class NoticePage:
    records: tuple[dict[str, Any], ...]
    total_count: int
    response: ResponseSummary


@dataclass(frozen=True)
class CompanyNotices:
    siren: str
    pages: tuple[NoticePage, ...]

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(record for page in self.pages for record in page.records)

    @property
    def total_count(self) -> int:
        return self.pages[-1].total_count

    @property
    def is_complete(self) -> bool:
        return len(self.records) >= self.total_count


def unreadable_response_message() -> str:
    return f"La réponse du service {SOURCE_NAMES[SOURCE]} est illisible. Réessayez plus tard."


def notice_page_from(stored_response: StoredResponse) -> NoticePage:
    try:
        payload = json.loads(stored_response.body)
        records = payload["results"]
        if not all(isinstance(record, dict) for record in records):
            raise TypeError("A notice is not an object")
        return NoticePage(tuple(records), int(payload["total_count"]), stored_response.summary)
    except (KeyError, TypeError, ValueError) as unreadable:
        raise CollectionError(unreadable_response_message(), SOURCE, None) from unreadable


class Bodacc:
    def __init__(
        self,
        http_client: CollectorHttpClient,
        notices_per_page: int = MAXIMUM_NOTICES_PER_PAGE,
        maximum_pages: int = DEFAULT_MAXIMUM_PAGES,
    ) -> None:
        self.http_client = http_client
        self.notices_per_page = notices_per_page
        self.maximum_pages = maximum_pages

    def notices_of(self, siren: str, *, refresh: bool = False) -> CompanyNotices:
        digits = siren_of(siren)
        pages: list[NoticePage] = []
        offset = 0
        while len(pages) < self.maximum_pages:
            page = self.notice_page(digits, offset, refresh)
            pages.append(page)
            offset += len(page.records)
            if not page.records or offset >= page.total_count:
                break
        return CompanyNotices(digits, tuple(pages))

    def notice_page(self, siren: str, offset: int, refresh: bool) -> NoticePage:
        stored_response = self.http_client.get(
            SOURCE,
            BODACC_RECORDS_URL,
            {
                "where": f'registre="{siren}"',
                "order_by": "dateparution desc",
                "limit": str(self.notices_per_page),
                "offset": str(offset),
            },
            refresh=refresh,
        )
        return notice_page_from(stored_response)
