import sqlite3
from collections.abc import Iterator
from dataclasses import replace

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.company_register import CompanyRegister
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.mapping import company_entity
from lacis.graph.register_search import (
    MINIMUM_QUERY_LENGTH,
    RegisterSearchResult,
    RegisterSearchResults,
    french_date,
    grouped,
    query_problem,
    search_register,
)
from lacis.storage.collection_log import CollectionLog
from lacis.storage.graph_store import GraphStore
from lacis.storage.responses import ResponseStore


@pytest.fixture
def company_register(
    response_store: ResponseStore, collection_log: CollectionLog
) -> Iterator[CompanyRegister]:
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(FakeApi(FAKE_PLUMBERS_SCENARIO)),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            sleep=fake_time.sleep,
            monotonic=fake_time.clock,
        ),
    )
    yield CompanyRegister(client)
    client.close()


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


def search(
    company_register: CompanyRegister, graph_store: GraphStore, text: str
) -> RegisterSearchResults:
    return search_register(company_register, graph_store, text)


def test_a_search_gives_each_company_with_its_main_facts(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    results = search(company_register, graph_store, "lilas")
    assert [(result.title, result.status, result.details) for result in results.results] == [
        (
            "ACME PLOMBERIE",
            "Active",
            "111 111 111 · NAF 43.22A · 31000 TOULOUSE · créée le 10/11/2022",
        ),
        (
            "DUPONT SERVICES",
            "Fermée",
            "222 222 222 · NAF 43.22A · 31000 TOULOUSE · créée le 02/04/2019",
        ),
        (
            "LILAS BOULANGERIE",
            "Active",
            "555 555 555 · NAF 10.71C · 69001 LYON · créée le 14/04/2025",
        ),
    ]
    assert results.count_text == "3 résultats dans le registre national"
    assert results.truncation_text == ""
    assert results.announcement == "3 résultats dans le registre national."


def test_companies_already_in_the_investigation_are_marked(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    first = search(company_register, graph_store, "lilas")
    acme = first.results[0]
    graph_store.save_entity(company_entity(acme.company), first.page.response)
    second = search(company_register, graph_store, "lilas")
    assert [result.in_investigation for result in second.results] == [True, False, False]
    assert second.results[0].identifier == "company:111111111"
    assert second.results[0].spoken == "ACME PLOMBERIE, Active, Déjà dans l'enquête"
    assert second.results[1].spoken == "DUPONT SERVICES, Fermée"


def test_an_added_result_is_in_the_investigation(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    result = search(company_register, graph_store, "plomberie").results[0]
    assert not result.in_investigation
    assert result.added().in_investigation
    assert result.added().company is result.company


def test_a_company_withheld_from_the_public_keeps_its_siren(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    [result] = search(company_register, graph_store, "999999999").results
    assert result.title == "Entreprise non diffusible (999 999 999)"


def test_a_count_is_singular_for_one_result_and_says_when_nothing_is_found(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    assert search(company_register, graph_store, "thames").count_text == (
        "1 résultat dans le registre national"
    )
    nothing = search(company_register, graph_store, "introuvable")
    assert nothing.count_text == "Aucun résultat dans le registre national"
    assert nothing.results == ()


def test_more_results_than_shown_invite_to_refine_the_search(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    results = search(company_register, graph_store, "dupont")
    shortened = RegisterSearchResults(
        replace(results.page, total_results=1312), results.results[:2]
    )
    assert shortened.count_text == "1\u00a0312 résultats dans le registre national"
    assert shortened.truncation_text == (
        "Les 2 premiers sont affichés : précisez la recherche pour trouver les autres."
    )
    assert shortened.announcement == (
        "1\u00a0312 résultats dans le registre national. "
        "Les 2 premiers sont affichés : précisez la recherche pour trouver les autres."
    )


def test_details_leave_out_what_the_register_does_not_give(
    company_register: CompanyRegister, graph_store: GraphStore
) -> None:
    company = search(company_register, graph_store, "thames").results[0].company
    assert company.head_office is not None
    abroad = replace(
        company,
        activity=None,
        creation_date=None,
        head_office=replace(
            company.head_office,
            address=replace(company.head_office.address, postcode=None, city=None),
        ),
    )
    assert RegisterSearchResult(abroad, False).details == (
        f"121 212 121 · {company.head_office.address.country}"
    )
    without_office = replace(abroad, head_office=None)
    assert RegisterSearchResult(without_office, False).details == "121 212 121"


def test_a_short_query_is_refused_before_searching() -> None:
    assert query_problem("  ab ") == (
        f"Saisissez au moins {MINIMUM_QUERY_LENGTH} caractères pour rechercher."
    )
    assert query_problem("abc") == ""


def test_dates_and_numbers_are_written_the_french_way() -> None:
    assert french_date("2022-11-10") == "10/11/2022"
    assert french_date("2022") == "2022"
    assert grouped(1234567) == "1\u00a0234\u00a0567"
