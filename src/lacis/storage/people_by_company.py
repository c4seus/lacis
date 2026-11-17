import json
import sqlite3
from dataclasses import dataclass

from lacis.storage.entities import (
    IDENTIFIER_SEPARATOR,
    EntityKind,
    InvalidIdentifierError,
    LinkKind,
    mandate_link,
    person_identifier,
    same_person_link,
)
from lacis.storage.homonym_decisions import HomonymDecision


@dataclass(frozen=True)
class FormerPerson:
    identifier: str
    label: str
    attributes: str
    first_collected_at: str
    last_collected_at: str


@dataclass(frozen=True)
class FormerMandate:
    identifier: str
    company: str
    role: str
    first_collected_at: str
    last_collected_at: str


def siren_of_company(company: str) -> str:
    return company.split(IDENTIFIER_SEPARATOR, 1)[1]


def identifier_in(person: FormerPerson, company: str) -> str:
    attributes = json.loads(person.attributes)
    birth_month = attributes.get("birth_month")
    return person_identifier(
        str(attributes.get("last_name") or ""),
        str(attributes.get("first_names") or ""),
        birth_month if isinstance(birth_month, str) and birth_month else None,
        siren_of_company(company),
    )


def mandates_of(connection: sqlite3.Connection, person: str) -> list[FormerMandate]:
    rows = connection.execute(
        """
        SELECT identifier, target, role, first_collected_at, last_collected_at FROM link
        WHERE kind = ? AND source = ? ORDER BY target, identifier
        """,
        (LinkKind.MANDATE.value, person),
    ).fetchall()
    return [FormerMandate(*row) for row in rows]


def copy_sources(
    connection: sqlite3.Connection, person: str, new_person: str, mandates: list[FormerMandate]
) -> None:
    responses = {
        response
        for mandate in mandates
        for (response,) in connection.execute(
            "SELECT response_identifier FROM link_source WHERE link_identifier = ?",
            (mandate.identifier,),
        )
    }
    if not responses:
        responses = {
            response
            for (response,) in connection.execute(
                "SELECT response_identifier FROM entity_source WHERE entity_identifier = ?",
                (person,),
            )
        }
    connection.executemany(
        "INSERT INTO entity_source (entity_identifier, response_identifier) VALUES (?, ?)",
        [(new_person, response) for response in sorted(responses)],
    )


def move_mandate(connection: sqlite3.Connection, new_person: str, mandate: FormerMandate) -> None:
    link = mandate_link(new_person, mandate.company, mandate.role)
    connection.execute(
        """
        INSERT OR IGNORE INTO link (identifier, kind, source, target, role,
                                    first_collected_at, last_collected_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            link.identifier,
            LinkKind.MANDATE.value,
            new_person,
            mandate.company,
            mandate.role,
            mandate.first_collected_at,
            mandate.last_collected_at,
        ),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO link_source (link_identifier, response_identifier)
        SELECT ?, response_identifier FROM link_source WHERE link_identifier = ?
        """,
        (link.identifier, mandate.identifier),
    )


def split_person(connection: sqlite3.Connection, person: FormerPerson) -> list[str]:
    mandates = mandates_of(connection, person.identifier)
    companies = sorted({mandate.company for mandate in mandates})
    try:
        new_people = [identifier_in(person, company) for company in companies]
    except InvalidIdentifierError:
        return []
    if new_people == [person.identifier]:
        return []
    for company, new_person in zip(companies, new_people, strict=True):
        company_mandates = [mandate for mandate in mandates if mandate.company == company]
        connection.execute(
            """
            INSERT INTO entity (identifier, kind, label, attributes,
                                first_collected_at, last_collected_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                new_person,
                EntityKind.PERSON.value,
                person.label,
                person.attributes,
                person.first_collected_at,
                person.last_collected_at,
            ),
        )
        copy_sources(connection, person.identifier, new_person, company_mandates)
        for mandate in company_mandates:
            move_mandate(connection, new_person, mandate)
    if new_people:
        connection.execute(
            "UPDATE entity_position SET entity_identifier = ? WHERE entity_identifier = ?",
            (new_people[0], person.identifier),
        )
    return new_people


def kept_pairs(
    first_people: list[str], second_people: list[str], decision: HomonymDecision
) -> list[tuple[str, str]]:
    if decision is HomonymDecision.DIFFERENT_PERSON:
        return [(first, second) for first in first_people for second in second_people]
    if len(first_people) == 1 and len(second_people) == 1:
        return [(first_people[0], second_people[0])]
    return []


def record_decision(
    connection: sqlite3.Connection,
    people: tuple[str, str],
    decision: HomonymDecision,
    decided_at: str,
) -> None:
    first, second = sorted(people)
    connection.execute(
        """
        INSERT OR REPLACE INTO homonym_decision (first_person, second_person, decision, decided_at)
        VALUES (?, ?, ?, ?)
        """,
        (first, second, decision.value, decided_at),
    )
    if decision is HomonymDecision.SAME_PERSON:
        connection.execute(
            """
            INSERT OR IGNORE INTO link (identifier, kind, source, target, role,
                                        first_collected_at, last_collected_at)
            VALUES (?, ?, ?, ?, '', ?, ?)
            """,
            (
                same_person_link(first, second).identifier,
                LinkKind.SAME_PERSON.value,
                first,
                second,
                decided_at,
                decided_at,
            ),
        )


def move_decisions(connection: sqlite3.Connection, new_people: dict[str, list[str]]) -> None:
    rows = connection.execute(
        "SELECT first_person, second_person, decision, decided_at FROM homonym_decision"
    ).fetchall()
    for first, second, decision, decided_at in rows:
        if first not in new_people and second not in new_people:
            continue
        recorded = HomonymDecision(decision)
        for pair in kept_pairs(
            new_people.get(first, [first]), new_people.get(second, [second]), recorded
        ):
            record_decision(connection, pair, recorded, decided_at)


def remove_person(connection: sqlite3.Connection, person: str) -> None:
    connection.execute(
        """
        DELETE FROM link_source WHERE link_identifier IN (
            SELECT identifier FROM link WHERE source = ? OR target = ?
        )
        """,
        (person, person),
    )
    connection.execute("DELETE FROM link WHERE source = ? OR target = ?", (person, person))
    connection.execute("DELETE FROM entity_source WHERE entity_identifier = ?", (person,))
    connection.execute("DELETE FROM entity WHERE identifier = ?", (person,))


def split_people_by_company(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        """
        SELECT identifier, label, attributes, first_collected_at, last_collected_at
        FROM entity WHERE kind = ? ORDER BY identifier
        """,
        (EntityKind.PERSON.value,),
    ).fetchall()
    new_people: dict[str, list[str]] = {}
    for row in rows:
        person = FormerPerson(*row)
        split = split_person(connection, person)
        if split:
            new_people[person.identifier] = split
    move_decisions(connection, new_people)
    for former in new_people:
        remove_person(connection, former)
