import sqlite3
from dataclasses import dataclass

from investigation_builder import COLLECTED_AT, fictional_sirens
from lacis.storage.entities import (
    CollectedLink,
    address_identifier,
    company_identifier,
    mandate_link,
    person_identifier,
    registered_office_link,
)
from lacis.storage.graph_store import ENTITY_COLUMNS, LINK_COLUMNS

PEOPLE_PER_GROUP = 1
COMPANIES_PER_GROUP = 3
ADDRESSES_PER_GROUP = 1
GROUP_SIZE = PEOPLE_PER_GROUP + COMPANIES_PER_GROUP + ADDRESSES_PER_GROUP


@dataclass(frozen=True)
class LargeInvestigation:
    people: list[str]
    companies: list[str]
    addresses: list[str]

    @property
    def size(self) -> int:
        return len(self.people) + len(self.companies) + len(self.addresses)


def entity_row(identifier: str, kind: str, label: str) -> tuple[str, ...]:
    collected_at = COLLECTED_AT.isoformat()
    return (identifier, kind, label, "{}", collected_at, collected_at)


def link_row(link: CollectedLink) -> tuple[str, ...]:
    collected_at = COLLECTED_AT.isoformat()
    return (
        link.identifier,
        link.kind.value,
        link.source,
        link.target,
        link.role,
        collected_at,
        collected_at,
    )


def large_investigation(connection: sqlite3.Connection, groups: int) -> LargeInvestigation:
    sirens = fictional_sirens()
    people: list[str] = []
    companies: list[str] = []
    addresses: list[str] = []
    entities: list[tuple[str, ...]] = []
    links: list[CollectedLink] = []
    for group in range(groups):
        person = person_identifier(f"NOM{group}", "Jean", "1980-05")
        address = address_identifier(f"{group} RUE DES LILAS 31000 TOULOUSE")
        entities.append(entity_row(person, "person", f"Jean NOM{group}"))
        entities.append(entity_row(address, "address", f"{group} RUE DES LILAS 31000 TOULOUSE"))
        people.append(person)
        addresses.append(address)
        for position in range(COMPANIES_PER_GROUP):
            company = company_identifier(next(sirens))
            entities.append(entity_row(company, "company", f"SOCIETE {group}-{position}"))
            companies.append(company)
            links.append(mandate_link(person, company, "Gérant"))
            links.append(registered_office_link(company, address))
        if group:
            links.append(mandate_link(people[group - 1], companies[-1], "Associé"))
    with connection:
        connection.executemany(
            f"INSERT INTO entity ({ENTITY_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?)", entities
        )
        connection.executemany(
            f"INSERT INTO link ({LINK_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [link_row(link) for link in links],
        )
    return LargeInvestigation(people, companies, addresses)
