import sqlite3
from collections.abc import Iterator
from datetime import UTC, date, datetime
from itertools import count

from identifier_checks import passes_luhn_check
from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE
from lacis.signals.context import InvestigationContext
from lacis.storage.entities import (
    Attributes,
    CollectedEntity,
    address_identifier,
    company_identifier,
    mandate_link,
    person_identifier,
    registered_office_link,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.notices import (
    CollectedNotice,
    NoticeFamily,
    NoticeRole,
    NoticeStore,
    OfficeTransfer,
)
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)

COLLECTED_AT = datetime(2026, 11, 2, 23, 11, tzinfo=UTC)
TODAY = date(2026, 11, 10)
COURT = "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE"


def fictional_sirens() -> Iterator[str]:
    for number in count(100000000):
        siren = str(number)
        if not passes_luhn_check(siren):
            yield siren


class InvestigationBuilder:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection
        self.graph_store = GraphStore(connection)
        self.notice_store = NoticeStore(connection)
        self.sirens = fictional_sirens()
        self.notice_numbers = count(1)
        self.response = self.saved_response(ResponseSource.COMPANY_REGISTER)
        self.bodacc_response = self.saved_response(ResponseSource.BODACC)

    def saved_response(self, source: ResponseSource) -> ResponseSummary:
        return ResponseStore(self.connection).save(
            CollectedResponse(source, f"https://{source.value}.example", b"{}", COLLECTED_AT, {})
        )

    def company(
        self,
        label: str,
        creation_date: date | None = None,
        activity: str | None = None,
        *,
        closing_date: date | None = None,
        identifier: str | None = None,
    ) -> str:
        identifier = identifier or company_identifier(next(self.sirens))
        attributes: Attributes = {"is_active": closing_date is None}
        if closing_date is not None:
            attributes["closing_date"] = closing_date.isoformat()
        if creation_date is not None:
            attributes["creation_date"] = creation_date.isoformat()
        if activity is not None:
            attributes["activity"] = activity
        self.graph_store.save_entity(CollectedEntity(identifier, label, attributes), self.response)
        return identifier

    def address(self, text: str, *, expanded: bool = False, postcode: str | None = None) -> str:
        identifier = address_identifier(text)
        attributes: Attributes = {"postcode": postcode}
        if expanded:
            attributes[EXPANDED_AT_ATTRIBUTE] = COLLECTED_AT.isoformat()
        self.graph_store.save_entity(CollectedEntity(identifier, text, attributes), self.response)
        return identifier

    def person(self, first_names: str, last_name: str, *, expanded: bool = False) -> str:
        identifier = person_identifier(last_name, first_names, "1980-05")
        attributes: Attributes = {
            "last_name": last_name,
            "first_names": first_names,
            "birth_month": "1980-05",
        }
        if expanded:
            attributes[EXPANDED_AT_ATTRIBUTE] = COLLECTED_AT.isoformat()
        self.graph_store.save_entity(
            CollectedEntity(identifier, f"{first_names} {last_name}", attributes), self.response
        )
        return identifier

    def mandate(self, director: str, company: str, role: str = "Gérant") -> None:
        self.graph_store.save_link(mandate_link(director, company, role), self.response)

    def same_person(self, first_person: str, second_person: str) -> None:
        HomonymDecisionStore(self.connection).record(
            first_person, second_person, HomonymDecision.SAME_PERSON
        )

    def registered_office(self, company: str, address: str) -> None:
        self.graph_store.save_link(registered_office_link(company, address), self.response)

    def notice(
        self,
        company: str,
        family: NoticeFamily,
        published_on: date,
        summary: str = "",
        office_transfer: OfficeTransfer | None = None,
    ) -> str:
        identifier = f"A2025{next(self.notice_numbers):08d}"
        self.notice_store.save_notice(
            CollectedNotice(
                identifier,
                family,
                published_on,
                COURT,
                summary,
                companies={company: NoticeRole.SUBJECT},
                office_transfer=office_transfer,
            ),
            self.bodacc_response,
        )
        return identifier

    def context(self, today: date = TODAY) -> InvestigationContext:
        return InvestigationContext(self.connection, today)
