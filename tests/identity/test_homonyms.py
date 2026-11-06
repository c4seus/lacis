import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import GraphExpander
from lacis.identity.homonyms import (
    Confidence,
    Corroboration,
    FirstNameRelation,
    HomonymPair,
    PersonIdentity,
    first_name_relation,
    homonym_pair,
    homonym_pairs,
    homonym_proposals,
)
from lacis.storage.collection_log import CollectionLog
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
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    ResponseSummary,
)

DECIDED_AT = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


@pytest.fixture
def decision_store(investigation_connection: sqlite3.Connection) -> HomonymDecisionStore:
    return HomonymDecisionStore(investigation_connection, now=lambda: DECIDED_AT)


@pytest.fixture
def response(response_store: ResponseStore) -> ResponseSummary:
    return response_store.save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            datetime(2026, 11, 6, tzinfo=UTC),
            {"q": "dupont"},
        )
    )


def add_person(
    graph_store: GraphStore,
    response: ResponseSummary,
    last_name: str,
    first_names: str,
    birth_month: str | None,
) -> str:
    identifier = person_identifier(last_name, first_names, birth_month)
    label = f"{first_names} {last_name.upper()}".strip()
    attributes: Attributes = {
        "last_name": last_name,
        "first_names": first_names,
        "birth_month": birth_month,
    }
    graph_store.save_entity(CollectedEntity(identifier, label, attributes), response)
    return identifier


def pairs_of(graph_store: GraphStore) -> list[tuple[str, str, FirstNameRelation]]:
    return [
        (pair.first.label, pair.second.label, pair.first_name_relation)
        for pair in homonym_pairs(graph_store)
    ]


@pytest.mark.parametrize(
    ("first", "second", "relation"),
    [
        (("JEAN",), ("JEAN",), FirstNameRelation.SAME),
        (("JEAN",), ("JEAN", "PIERRE"), FirstNameRelation.COMPOUND),
        (("JEAN", "PIERRE"), ("JEAN",), FirstNameRelation.COMPOUND),
        ((), ("JEAN",), FirstNameRelation.UNKNOWN),
        (("JEAN", "PIERRE"), ("JEAN", "MARC"), None),
        (("PIERRE",), ("JEAN", "PIERRE"), None),
        (("MARIE",), ("JEAN",), None),
    ],
)
def test_first_names_are_compatible_when_one_starts_the_other(
    first: tuple[str, ...], second: tuple[str, ...], relation: FirstNameRelation | None
) -> None:
    assert first_name_relation(first, second) is relation


def test_jean_and_jean_pierre_dupont_born_the_same_month_are_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    [pair] = homonym_pairs(graph_store)
    assert (pair.first.label, pair.second.label) == ("Jean DUPONT", "Jean Pierre DUPONT")
    assert pair.first_name_relation is FirstNameRelation.COMPOUND
    assert pair.same_birth_month


def test_people_born_different_months_are_never_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", "1980-06")
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1975-02")
    assert homonym_pairs(graph_store) == []


def test_a_person_without_birth_month_may_be_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "Dupont", "jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", None)
    [pair] = homonym_pairs(graph_store)
    assert pair.first_name_relation is FirstNameRelation.SAME
    assert not pair.same_birth_month


def test_other_last_names_and_incompatible_first_names_are_not_paired(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Marc", "1980-05")
    add_person(graph_store, response, "DUPONTEL", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Marie", "1980-05")
    assert homonym_pairs(graph_store) == []


def test_every_compatible_pair_is_listed_in_name_order(
    graph_store: GraphStore, response: ResponseSummary
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Marc", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "MARTIN", "", "1990-01")
    add_person(graph_store, response, "MARTIN", "Paul", "1990-01")
    graph_store.save_entity(CollectedEntity("company:111111111", "DUPONT"), response)
    assert pairs_of(graph_store) == [
        ("Jean DUPONT", "Jean Marc DUPONT", FirstNameRelation.COMPOUND),
        ("Jean DUPONT", "Jean Pierre DUPONT", FirstNameRelation.COMPOUND),
        ("MARTIN", "Paul MARTIN", FirstNameRelation.UNKNOWN),
    ]


def test_people_without_last_name_are_never_paired() -> None:
    nameless = PersonIdentity("person:1", "?", "", ("JEAN",), None)
    other = PersonIdentity("person:2", "?", "", ("JEAN",), None)
    pair = HomonymPair(nameless, other, FirstNameRelation.SAME)
    assert not pair.same_birth_month
    assert homonym_pair(nameless, other) is None


def add_company(
    graph_store: GraphStore, response: ResponseSummary, siren: str, name: str, address: str
) -> str:
    company = company_identifier(siren)
    graph_store.save_entity(CollectedEntity(company, name), response)
    address_entity = address_identifier(address)
    graph_store.save_entity(CollectedEntity(address_entity, address), response)
    graph_store.save_link(registered_office_link(company, address_entity), response)
    return company


def add_mandate(
    graph_store: GraphStore, response: ResponseSummary, director: str, company: str
) -> None:
    graph_store.save_link(mandate_link(director, company, "Président"), response)


def proposals_of(
    graph_store: GraphStore, decision_store: HomonymDecisionStore
) -> list[tuple[str, str, Confidence]]:
    return [
        (proposal.pair.first.label, proposal.pair.second.label, proposal.confidence)
        for proposal in homonym_proposals(graph_store, decision_store)
    ]


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(FAKE_PLUMBERS_SCENARIO)


@pytest.fixture
def expander(
    investigation_connection: sqlite3.Connection,
    response_store: ResponseStore,
    collection_log: CollectionLog,
    fake_api: FakeApi,
) -> Iterator[GraphExpander]:
    fake_time = FakeTime()
    http_client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(fake_api),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            monotonic=fake_time.clock,
        ),
    )
    yield GraphExpander(
        investigation_connection, CompanyRegister(http_client), Bodacc(http_client)
    )
    http_client.close()


def test_jean_and_jean_pierre_dupont_of_the_scenario_are_proposed_with_their_reasons(
    expander: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    expander.expand_company("222222222")
    expander.expand_company("111111111")
    [proposal] = homonym_proposals(graph_store, decision_store)
    assert (proposal.pair.first.label, proposal.pair.second.label) == (
        "Jean DUPONT",
        "Jean Pierre DUPONT",
    )
    assert proposal.confidence is Confidence.PROBABLE
    assert proposal.reasons == (
        "Même nom de famille",
        "Prénom composé : Jean / Jean Pierre",
        "Même mois de naissance (05/1980)",
        "Entreprises domiciliées à la même adresse : 12 RUE DES LILAS 31000 TOULOUSE",
    )


def test_a_company_linking_the_two_people_makes_the_match_certain(
    expander: GraphExpander,
    graph_store: GraphStore,
    decision_store: HomonymDecisionStore,
) -> None:
    expander.expand_company("222222222")
    expander.expand_company("111111111")
    expander.expand_person(person_identifier("DUPONT", "Jean", "1980-05"))
    proposals = {
        (proposal.pair.first.label, proposal.pair.second.label): proposal
        for proposal in homonym_proposals(graph_store, decision_store)
    }
    jean_pierre = proposals["Jean DUPONT", "Jean Pierre DUPONT"]
    assert jean_pierre.confidence is Confidence.CERTAIN
    assert "HOLDING DUPONT dirige ACME PLOMBERIE" in jean_pierre.reasons
    jean_marc = proposals["Jean DUPONT", "Jean Marc DUPONT"]
    assert jean_marc.confidence is Confidence.PROBABLE
    assert jean_marc.reasons == (
        "Même nom de famille",
        "Prénom composé : Jean / Jean Marc",
        "Même mois de naissance (05/1980)",
    )
    assert next(iter(proposals.values())) is jean_pierre


def test_an_unknown_birth_month_makes_a_match_weak(
    graph_store: GraphStore,
    response: ResponseSummary,
    decision_store: HomonymDecisionStore,
) -> None:
    add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean", None)
    [proposal] = homonym_proposals(graph_store, decision_store)
    assert proposal.confidence is Confidence.WEAK
    assert proposal.reasons == (
        "Même nom de famille",
        "Mêmes prénoms",
        "Mois de naissance inconnu d'un côté",
    )


def test_unknown_first_names_make_a_match_weak(
    graph_store: GraphStore,
    response: ResponseSummary,
    decision_store: HomonymDecisionStore,
) -> None:
    add_person(graph_store, response, "MARTIN", "", "1990-01")
    add_person(graph_store, response, "MARTIN", "Paul", "1990-01")
    [proposal] = homonym_proposals(graph_store, decision_store)
    assert proposal.confidence is Confidence.WEAK
    assert "Prénoms inconnus d'un côté" in proposal.reasons


def test_a_well_corroborated_match_with_an_unknown_birth_month_is_probable(
    graph_store: GraphStore,
    response: ResponseSummary,
    decision_store: HomonymDecisionStore,
) -> None:
    jean = add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    other_jean = add_person(graph_store, response, "DUPONT", "Jean", None)
    lilas = "12 RUE DES LILAS 31000 TOULOUSE"
    acme = add_company(graph_store, response, "111111111", "ACME PLOMBERIE", lilas)
    services = add_company(graph_store, response, "222222222", "DUPONT SERVICES", lilas)
    add_mandate(graph_store, response, jean, acme)
    add_mandate(graph_store, response, other_jean, acme)
    add_mandate(graph_store, response, other_jean, services)
    [proposal] = homonym_proposals(graph_store, decision_store)
    assert proposal.confidence is Confidence.PROBABLE
    assert proposal.reasons[3:] == (
        "Dirigeants tous deux de ACME PLOMBERIE",
        f"Entreprises domiciliées à la même adresse : {lilas}",
    )


def test_proposals_go_from_certain_to_weak(
    graph_store: GraphStore, response: ResponseSummary, decision_store: HomonymDecisionStore
) -> None:
    add_person(graph_store, response, "MARTIN", "", "1990-01")
    add_person(graph_store, response, "MARTIN", "Paul", "1990-01")
    jean = add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    jean_pierre = add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    add_person(graph_store, response, "BLANC", "Hugo", "1992-07")
    add_person(graph_store, response, "BLANC", "Hugo Louis", "1992-07")
    lilas = "12 RUE DES LILAS 31000 TOULOUSE"
    acme = add_company(graph_store, response, "111111111", "ACME PLOMBERIE", lilas)
    add_mandate(graph_store, response, jean, acme)
    add_mandate(graph_store, response, jean_pierre, acme)
    assert proposals_of(graph_store, decision_store) == [
        ("Jean DUPONT", "Jean Pierre DUPONT", Confidence.CERTAIN),
        ("Hugo BLANC", "Hugo Louis BLANC", Confidence.PROBABLE),
        ("MARTIN", "Paul MARTIN", Confidence.WEAK),
    ]


def test_a_corroboration_names_an_entity_even_without_its_label(
    graph_store: GraphStore,
) -> None:
    assert Corroboration(graph_store).label("company:111111111") == "company:111111111"


def test_a_rejected_pair_is_not_proposed_again(
    graph_store: GraphStore, response: ResponseSummary, decision_store: HomonymDecisionStore
) -> None:
    jean = add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    jean_marc = add_person(graph_store, response, "DUPONT", "Jean Marc", "1980-05")
    add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    decision_store.record(jean_marc, jean, HomonymDecision.DIFFERENT_PERSON)
    assert proposals_of(graph_store, decision_store) == [
        ("Jean DUPONT", "Jean Pierre DUPONT", Confidence.PROBABLE)
    ]


def test_a_confirmed_pair_is_no_longer_proposed(
    graph_store: GraphStore, response: ResponseSummary, decision_store: HomonymDecisionStore
) -> None:
    jean = add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    jean_pierre = add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    decision_store.record(jean, jean_pierre, HomonymDecision.SAME_PERSON)
    assert proposals_of(graph_store, decision_store) == []


@pytest.mark.parametrize(
    "decision", [HomonymDecision.SAME_PERSON, HomonymDecision.DIFFERENT_PERSON]
)
def test_an_undone_decision_brings_the_pair_back_to_the_proposals(
    graph_store: GraphStore,
    response: ResponseSummary,
    decision_store: HomonymDecisionStore,
    decision: HomonymDecision,
) -> None:
    jean = add_person(graph_store, response, "DUPONT", "Jean", "1980-05")
    jean_pierre = add_person(graph_store, response, "DUPONT", "Jean Pierre", "1980-05")
    decision_store.record(jean, jean_pierre, decision)
    decision_store.undo(jean, jean_pierre)
    assert proposals_of(graph_store, decision_store) == [
        ("Jean DUPONT", "Jean Pierre DUPONT", Confidence.PROBABLE)
    ]
