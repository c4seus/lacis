import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.identity.homonyms import homonym_proposals
from lacis.storage.entities import (
    Attributes,
    CollectedEntity,
    LinkKind,
    company_identifier,
    mandate_link,
    person_identifier,
    same_person_link,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import InvestigationLibrary
from lacis.storage.people_by_company import split_people_by_company
from lacis.storage.positions import Position, PositionStore
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore
from lacis.storage.schema import MIGRATIONS

COLLECTED_AT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 11, 12, 15, 30, tzinfo=UTC)
EXPANDED_AT = "2026-11-11T10:00:00+00:00"
FORMER_JEAN = "person:00000000000000a1"
FORMER_JEAN_PIERRE = "person:00000000000000a2"
FORMER_JEAN_MARC = "person:00000000000000a3"
FORMER_MARIE = "person:00000000000000a4"
WITHOUT_NAME = "person:00000000000000a5"
WITHOUT_MANDATE = "person:00000000000000a6"
DUPONT_SERVICES = company_identifier("222222222")
HOLDING = company_identifier("333333333")
ACME = company_identifier("111111111")
AUTRE_SOCIETE = company_identifier("444444444")
DUPONT_RENOVATION = company_identifier("666666666")
JEAN = person_identifier("DUPONT", "Jean", "1980-05", "222222222")
JEAN_OF_HOLDING = person_identifier("DUPONT", "Jean", "1980-05", "333333333")
JEAN_PIERRE = person_identifier("DUPONT", "Jean Pierre", "1980-05", "111111111")
JEAN_MARC = person_identifier("DUPONT", "Jean Marc", "1980-05", "666666666")
MARIE = person_identifier("DUPONT", "Marie", None, "444444444")


def both(first_person: str, second_person: str) -> tuple[str, str]:
    first, second = sorted((first_person, second_person))
    return first, second


def person_attributes(first_names: str, birth_month: str | None) -> Attributes:
    return {"last_name": "DUPONT", "first_names": first_names, "birth_month": birth_month}


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    before_split = MIGRATIONS.index(split_people_by_company)
    older = InvestigationLibrary(tmp_path, migrations=MIGRATIONS[:before_split])
    older.create("ancienne", "Qui sont les Dupont ?")
    with older.open("ancienne") as opened:
        save_former_people(opened.connection)
    return InvestigationLibrary(tmp_path)


def save_former_people(connection: sqlite3.Connection) -> None:
    responses = ResponseStore(connection)
    graph_store = GraphStore(connection)
    first, second = (
        responses.save(
            CollectedResponse(
                ResponseSource.COMPANY_REGISTER,
                f"https://register.example/{page}",
                b"{}",
                COLLECTED_AT,
            )
        )
        for page in (1, 2)
    )
    people = {
        FORMER_JEAN: (
            "Jean DUPONT",
            {**person_attributes("Jean", "1980-05"), "expanded_at": EXPANDED_AT},
        ),
        FORMER_JEAN_PIERRE: ("Jean Pierre DUPONT", person_attributes("Jean Pierre", "1980-05")),
        FORMER_JEAN_MARC: ("Jean Marc DUPONT", person_attributes("Jean Marc", "1980-05")),
        FORMER_MARIE: ("Marie DUPONT", person_attributes("Marie", None)),
        WITHOUT_NAME: ("Anonyme", {}),
        WITHOUT_MANDATE: ("Paul DUPONT", person_attributes("Paul", None)),
    }
    for identifier, (label, attributes) in people.items():
        graph_store.save_entity(CollectedEntity(identifier, label, attributes), first)
    for company in (DUPONT_SERVICES, HOLDING, ACME, AUTRE_SOCIETE, DUPONT_RENOVATION):
        graph_store.save_entity(CollectedEntity(company, company), first)
    mandates = [
        (mandate_link(FORMER_JEAN, DUPONT_SERVICES, "Président"), first),
        (mandate_link(FORMER_JEAN, DUPONT_SERVICES, "Directeur général"), first),
        (mandate_link(FORMER_JEAN, HOLDING, "Président"), second),
        (mandate_link(FORMER_JEAN_PIERRE, ACME, "Président"), first),
        (mandate_link(FORMER_JEAN_MARC, DUPONT_RENOVATION, "Gérant"), second),
        (mandate_link(FORMER_MARIE, AUTRE_SOCIETE, "Gérante"), first),
        (mandate_link(WITHOUT_NAME, ACME, "Associé"), first),
    ]
    for link, response in mandates:
        graph_store.save_link(link, response)
    connection.execute(
        "DELETE FROM link_source WHERE link_identifier = ?",
        (mandate_link(FORMER_JEAN_MARC, DUPONT_RENOVATION, "Gérant").identifier,),
    )
    decisions = HomonymDecisionStore(connection, now=lambda: DECIDED_AT)
    decisions.record(FORMER_JEAN_PIERRE, FORMER_JEAN_MARC, HomonymDecision.SAME_PERSON)
    decisions.record(FORMER_JEAN, FORMER_JEAN_PIERRE, HomonymDecision.SAME_PERSON)
    decisions.record(FORMER_JEAN, FORMER_MARIE, HomonymDecision.DIFFERENT_PERSON)
    PositionStore(connection).save({FORMER_JEAN: Position(120.0, -40.0, True)})


def people_of(graph_store: GraphStore) -> set[str]:
    return {
        entity.identifier for entity in graph_store.entities() if entity.kind.value == "person"
    }


def test_each_person_becomes_one_person_for_each_company_they_run(
    library: InvestigationLibrary,
) -> None:
    with library.open("ancienne") as opened:
        graph_store = GraphStore(opened.connection)
        assert people_of(graph_store) == {
            JEAN,
            JEAN_OF_HOLDING,
            JEAN_PIERRE,
            JEAN_MARC,
            MARIE,
            WITHOUT_NAME,
            WITHOUT_MANDATE,
        }
        assert {
            (link.source, link.target, link.role)
            for link in graph_store.links()
            if link.kind is LinkKind.MANDATE and link.source in {JEAN, JEAN_OF_HOLDING}
        } == {
            (JEAN, DUPONT_SERVICES, "Président"),
            (JEAN, DUPONT_SERVICES, "Directeur général"),
            (JEAN_OF_HOLDING, HOLDING, "Président"),
        }


def test_each_new_person_keeps_the_attributes_and_the_sources_of_its_mandates(
    library: InvestigationLibrary,
) -> None:
    with library.open("ancienne") as opened:
        graph_store = GraphStore(opened.connection)
        jean_of_holding = graph_store.require_entity(JEAN_OF_HOLDING)
        assert jean_of_holding.label == "Jean DUPONT"
        assert jean_of_holding.attributes["expanded_at"] == EXPANDED_AT
        assert [source.url for source in graph_store.sources_of_entity(JEAN)] == [
            "https://register.example/1"
        ]
        assert [source.url for source in graph_store.sources_of_entity(JEAN_OF_HOLDING)] == [
            "https://register.example/2"
        ]
        assert [source.url for source in graph_store.sources_of_entity(JEAN_MARC)] == [
            "https://register.example/1"
        ]
        moved = mandate_link(JEAN_OF_HOLDING, HOLDING, "Président")
        assert [source.url for source in graph_store.sources_of_link(moved.identifier)] == [
            "https://register.example/2"
        ]


def test_the_decisions_that_can_be_attributed_are_kept(library: InvestigationLibrary) -> None:
    with library.open("ancienne") as opened:
        decisions = {
            (recorded.first_person, recorded.second_person): (
                recorded.decision,
                recorded.decided_at,
            )
            for recorded in HomonymDecisionStore(opened.connection).decisions()
        }
        same = HomonymDecision.SAME_PERSON
        different = HomonymDecision.DIFFERENT_PERSON
        assert decisions == {
            both(JEAN_PIERRE, JEAN_MARC): (same, DECIDED_AT),
            both(JEAN, MARIE): (different, DECIDED_AT),
            both(JEAN_OF_HOLDING, MARIE): (different, DECIDED_AT),
        }
        same_people = {
            link.identifier
            for link in GraphStore(opened.connection).links()
            if link.kind is LinkKind.SAME_PERSON
        }
        assert same_people == {same_person_link(JEAN_PIERRE, JEAN_MARC).identifier}


def test_the_namesakes_of_a_split_person_come_back_as_proposals(
    library: InvestigationLibrary,
) -> None:
    with library.open("ancienne") as opened:
        proposals = {
            proposal.pair.people
            for proposal in homonym_proposals(
                GraphStore(opened.connection), HomonymDecisionStore(opened.connection)
            )
        }
        assert both(JEAN, JEAN_OF_HOLDING) in proposals


def test_the_position_of_a_person_goes_to_its_first_company(
    library: InvestigationLibrary,
) -> None:
    with library.open("ancienne") as opened:
        positions = PositionStore(opened.connection).positions()
        assert positions[JEAN] == Position(120.0, -40.0, True)
        assert JEAN_OF_HOLDING not in positions


def test_splitting_people_again_changes_nothing(library: InvestigationLibrary) -> None:
    with library.open("ancienne") as opened, opened.connection:
        graph_store = GraphStore(opened.connection)
        before = people_of(graph_store)
        split_people_by_company(opened.connection)
        assert people_of(graph_store) == before
