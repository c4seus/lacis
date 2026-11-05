import sqlite3
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from fake_time import FakeTime, FakeWallClock
from lacis.collectors.bodacc import Bodacc
from lacis.collectors.company_register import (
    CompanyRegister,
    InvalidQueryError,
    NaturalPersonDirector,
)
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import DUPONT_SERVICES as DUPONT_SERVICES_COMPANY
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO, HOLDING_DUPONT
from lacis.collectors.fake_plumbers import SHARED_ADDRESS as SHARED_ADDRESS_OF_SCENARIO
from lacis.collectors.fictional_records import (
    FictionalCompany,
    FictionalEstablishment,
    FictionalNaturalPerson,
    FictionalNotice,
)
from lacis.collectors.http_client import CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.graph.expansion import ExpansionError, GraphExpander, SearchedName, current_time
from lacis.graph.mapping import company_fragment
from lacis.storage.collection_log import CollectionLog
from lacis.storage.entities import (
    EntityKind,
    LinkKind,
    address_identifier,
    company_identifier,
    establishment_identifier,
    foreign_company_identifier,
    person_identifier,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.notices import NoticeFamily, NoticeRole, NoticeStore
from lacis.storage.responses import ResponseStore

DUPONT_SERVICES = "company:222222222"
DUPONT_SERVICES_HEAD_OFFICE = establishment_identifier("22222222200015")
SHARED_ADDRESS = address_identifier("12 RUE DES LILAS 31000 TOULOUSE")
JEAN_DUPONT = person_identifier("DUPONT", "Jean", "1980-05")
EXPANDED_AT = datetime(2026, 11, 5, 10, 30, tzinfo=UTC)


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(FAKE_PLUMBERS_SCENARIO)


@pytest.fixture
def wall_clock() -> FakeWallClock:
    return FakeWallClock(EXPANDED_AT)


@pytest.fixture
def http_client(
    fake_api: FakeApi,
    response_store: ResponseStore,
    collection_log: CollectionLog,
    wall_clock: FakeWallClock,
) -> Iterator[CollectorHttpClient]:
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(fake_api),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            now=wall_clock.now,
            monotonic=fake_time.clock,
        ),
    )
    yield client
    client.close()


@pytest.fixture
def company_register(http_client: CollectorHttpClient) -> CompanyRegister:
    return CompanyRegister(http_client)


@pytest.fixture
def expander(
    investigation_connection: sqlite3.Connection,
    company_register: CompanyRegister,
    http_client: CollectorHttpClient,
) -> GraphExpander:
    return GraphExpander(
        investigation_connection, company_register, Bodacc(http_client), now=lambda: EXPANDED_AT
    )


@pytest.fixture
def notice_store(investigation_connection: sqlite3.Connection) -> NoticeStore:
    return NoticeStore(investigation_connection)


@pytest.fixture
def graph_store(investigation_connection: sqlite3.Connection) -> GraphStore:
    return GraphStore(investigation_connection)


def test_a_company_is_added_from_a_search_result(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("dupont services")
    [dupont_services] = search_page.companies
    changes = expander.add_company(dupont_services, search_page.response)
    assert changes.new_entities == (DUPONT_SERVICES,)
    assert changes.new_links == ()
    assert not changes.is_empty
    entity = graph_store.require_entity(DUPONT_SERVICES)
    assert entity.label == "DUPONT SERVICES"
    assert entity.attributes["siren"] == "222222222"
    assert entity.attributes["is_active"] is False
    assert graph_store.sources_of_entity(DUPONT_SERVICES) == [search_page.response]


def test_adding_a_company_does_not_expand_it(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("acme plomberie")
    expander.add_company(search_page.companies[0], search_page.response)
    assert [entity.kind for entity in graph_store.entities()] == [EntityKind.COMPANY]
    assert graph_store.links() == []


def test_adding_a_company_twice_adds_nothing_new(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("dupont services")
    expander.add_company(search_page.companies[0], search_page.response)
    changes = expander.add_company(search_page.companies[0], search_page.response)
    assert changes.is_empty
    assert len(graph_store.entities()) == 1


def test_a_fragment_saved_twice_adds_its_entities_and_links_once(
    company_register: CompanyRegister, expander: GraphExpander, graph_store: GraphStore
) -> None:
    search_page = company_register.search("acme plomberie")
    fragment = company_fragment(search_page.companies[0])
    changes = expander.save_fragment(fragment, search_page.response)
    assert set(changes.new_entities) == {entity.identifier for entity in fragment.entities}
    assert set(changes.new_links) == {link.identifier for link in fragment.links}
    assert len(graph_store.links()) == len(fragment.links)
    assert expander.save_fragment(fragment, search_page.response).is_empty


def test_expanding_dupont_services_gives_its_establishment_address_and_directors(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    changes = expander.expand_company("222 222 222")
    assert set(changes.new_entities) == {
        DUPONT_SERVICES,
        DUPONT_SERVICES_HEAD_OFFICE,
        SHARED_ADDRESS,
        JEAN_DUPONT,
    }
    assert {(link.source, link.kind, link.target) for link in graph_store.links()} == {
        (DUPONT_SERVICES_HEAD_OFFICE, LinkKind.ESTABLISHMENT_OF, DUPONT_SERVICES),
        (DUPONT_SERVICES_HEAD_OFFICE, LinkKind.LOCATED_AT, SHARED_ADDRESS),
        (DUPONT_SERVICES, LinkKind.REGISTERED_OFFICE, SHARED_ADDRESS),
        (JEAN_DUPONT, LinkKind.MANDATE, DUPONT_SERVICES),
    }
    assert len(changes.new_links) == 4


def test_an_expanded_company_records_when_it_was_expanded_and_from_which_response(
    expander: GraphExpander, graph_store: GraphStore, response_store: ResponseStore
) -> None:
    expander.expand_company("222222222")
    company = graph_store.require_entity(DUPONT_SERVICES)
    assert company.attributes["expanded_at"] == EXPANDED_AT.isoformat()
    assert company.attributes["closing_date"] == "2023-01-15"
    detail_response, _ = response_store.summaries()
    assert graph_store.sources_of_entity(JEAN_DUPONT) == [detail_response]
    assert detail_response.parameters["q"] == "222222222"


def test_expanding_the_same_company_twice_adds_nothing_new(
    expander: GraphExpander, graph_store: GraphStore, fake_api: FakeApi
) -> None:
    expander.expand_company("222222222")
    entities_after_first_expansion = graph_store.entities()
    assert expander.expand_company("222222222").is_empty
    assert expander.expand_company("222222222", refresh=True).is_empty
    assert len(graph_store.entities()) == len(entities_after_first_expansion)
    assert len(fake_api.requests) == 4


def test_expanding_a_company_added_from_a_search_keeps_it_and_adds_the_rest(
    company_register: CompanyRegister, expander: GraphExpander
) -> None:
    search_page = company_register.search("dupont services")
    expander.add_company(search_page.companies[0], search_page.response)
    changes = expander.expand_company("222222222")
    assert DUPONT_SERVICES not in changes.new_entities
    assert JEAN_DUPONT in changes.new_entities


def test_a_second_company_at_the_same_address_shares_it(expander: GraphExpander) -> None:
    expander.expand_company("111111111")
    changes = expander.expand_company("222222222")
    assert SHARED_ADDRESS not in changes.new_entities
    assert DUPONT_SERVICES in changes.new_entities


def test_expanding_an_unknown_siren_reaches_the_caller_with_a_french_message(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    with pytest.raises(ExpansionError) as failure:
        expander.expand_company("123456780")
    assert str(failure.value) == (
        "Aucune entreprise ne porte le SIREN 123 456 780 dans le registre national."
    )
    assert graph_store.entities() == []


def test_expanding_requires_a_siren(expander: GraphExpander, fake_api: FakeApi) -> None:
    with pytest.raises(InvalidQueryError):
        expander.expand_company("ACME")
    assert fake_api.requests == []


def test_expansions_are_dated_in_utc() -> None:
    assert current_time().tzinfo is UTC


def test_expanding_dupont_services_fetches_its_bodacc_notices(
    expander: GraphExpander, notice_store: NoticeStore
) -> None:
    changes = expander.expand_company("222222222")
    assert set(changes.new_notices) == {"B202300030001", "A202200030002", "A202200030003"}
    notices = notice_store.notices_of_company(DUPONT_SERVICES)
    assert {family: len(items) for family, items in notices.items()} == {
        NoticeFamily.REMOVAL: 1,
        NoticeFamily.INSOLVENCY: 2,
    }
    removal = notices[NoticeFamily.REMOVAL][0]
    assert removal.role is NoticeRole.SUBJECT
    assert removal.notice.court == "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE"


def test_expanding_twice_adds_no_notice(expander: GraphExpander) -> None:
    expander.expand_company("222222222")
    changes = expander.expand_company("222222222", refresh=True)
    assert changes.new_notices == ()
    assert changes.withdrawn_notices == ()


def test_a_notice_is_only_linked_to_companies_of_the_investigation(
    expander: GraphExpander, fake_api: FakeApi, notice_store: NoticeStore
) -> None:
    sale = FictionalNotice(
        "A202400990001",
        DUPONT_SERVICES_COMPANY,
        "vente",
        "Ventes et cessions",
        "2024-03-01",
        "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE",
        {
            "listeprecedentexploitant": {
                "personne": {"numeroImmatriculation": {"numeroIdentification": "444 444 444"}}
            }
        },
    )
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO, notices=(*FAKE_PLUMBERS_SCENARIO.notices, sale)
    )
    expander.expand_company("222222222")
    sale_notices = notice_store.notices_of_company(DUPONT_SERVICES)[NoticeFamily.SALE]
    assert [item.notice.identifier for item in sale_notices] == ["A202400990001"]
    assert notice_store.notices_of_company("company:444444444") == {}


def test_a_notice_no_longer_returned_on_refresh_is_withdrawn(
    expander: GraphExpander,
    fake_api: FakeApi,
    wall_clock: FakeWallClock,
    notice_store: NoticeStore,
) -> None:
    expander.expand_company("222222222")
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO,
        notices=tuple(
            notice
            for notice in FAKE_PLUMBERS_SCENARIO.notices
            if notice.identifier != "A202200030003"
        ),
    )
    wall_clock.advance(timedelta(days=2))
    changes = expander.expand_company("222222222")
    assert changes.withdrawn_notices == ("A202200030003",)
    withdrawn = notice_store.require_notice("A202200030003")
    assert withdrawn.is_withdrawn


@pytest.fixture
def one_notice_expander(
    investigation_connection: sqlite3.Connection,
    company_register: CompanyRegister,
    http_client: CollectorHttpClient,
) -> GraphExpander:
    bodacc = Bodacc(http_client, notices_per_page=1, maximum_pages=1)
    return GraphExpander(investigation_connection, company_register, bodacc)


def test_an_incomplete_notice_list_withdraws_nothing(
    expander: GraphExpander,
    one_notice_expander: GraphExpander,
    fake_api: FakeApi,
    wall_clock: FakeWallClock,
    notice_store: NoticeStore,
) -> None:
    expander.expand_company("222222222")
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO,
        notices=tuple(
            notice
            for notice in FAKE_PLUMBERS_SCENARIO.notices
            if notice.identifier != "A202200030003"
        ),
    )
    wall_clock.advance(timedelta(days=2))
    changes = one_notice_expander.expand_company("222222222")
    assert changes.withdrawn_notices == ()
    assert not notice_store.require_notice("A202200030003").is_withdrawn


ACME = "company:111111111"
HOLDING = "company:333333333"
DUPONT_RENOVATION = "company:666666666"
JEAN_PIERRE_DUPONT = person_identifier("DUPONT", "Jean Pierre", "1980-05")
JEAN_MARC_DUPONT = person_identifier("DUPONT", "Jean Marc", "1980-05")


def mandates(graph_store: GraphStore) -> set[tuple[str, str, str]]:
    return {
        (link.source, link.target, link.role)
        for link in graph_store.links()
        if link.kind is LinkKind.MANDATE
    }


def test_expanding_jean_dupont_finds_the_companies_run_under_his_name(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("222222222")
    changes = expander.expand_person(JEAN_DUPONT)
    assert set(changes.new_entities) == {
        ACME,
        HOLDING,
        DUPONT_RENOVATION,
        JEAN_PIERRE_DUPONT,
        JEAN_MARC_DUPONT,
    }
    assert mandates(graph_store) == {
        (JEAN_DUPONT, DUPONT_SERVICES, "Président"),
        (JEAN_DUPONT, HOLDING, "Président"),
        (JEAN_PIERRE_DUPONT, ACME, "Président"),
        (JEAN_MARC_DUPONT, DUPONT_RENOVATION, "Gérant"),
    }
    assert "company:444444444" not in {entity.identifier for entity in graph_store.entities()}


def test_a_person_expansion_adds_companies_without_expanding_them(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("222222222")
    expander.expand_person(JEAN_DUPONT)
    acme = graph_store.require_entity(ACME)
    assert acme.label == "ACME PLOMBERIE"
    assert "expanded_at" not in acme.attributes
    assert graph_store.entity(establishment_identifier("11111111100015")) is None
    assert graph_store.entity(company_identifier("333333333")) is not None


def test_an_expanded_person_records_when_it_was_expanded(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("222222222")
    expander.expand_person(JEAN_DUPONT)
    jean = graph_store.require_entity(JEAN_DUPONT)
    assert jean.attributes["expanded_at"] == EXPANDED_AT.isoformat()
    assert jean.attributes["birth_month"] == "1980-05"


def test_expanding_a_person_twice_adds_nothing_new(expander: GraphExpander) -> None:
    expander.expand_company("222222222")
    expander.expand_person(JEAN_DUPONT)
    assert expander.expand_person(JEAN_DUPONT).is_empty


def test_a_person_born_another_month_is_not_taken_for_the_one_expanded(
    expander: GraphExpander, fake_api: FakeApi, graph_store: GraphStore
) -> None:
    namesake = FictionalCompany(
        siren="888888888",
        name="DUPONT ELEC",
        establishments=HOLDING_DUPONT.establishments,
        directors=(FictionalNaturalPerson("DUPONT", "Jean", "1975-01", "Gérant"),),
        creation_date="2020-01-01",
    )
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO, companies=(*FAKE_PLUMBERS_SCENARIO.companies, namesake)
    )
    expander.expand_company("222222222")
    changes = expander.expand_person(JEAN_DUPONT)
    assert "company:888888888" not in changes.new_entities
    assert graph_store.entity("company:888888888") is None


def test_a_person_with_several_first_names_finds_only_their_companies(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("111111111")
    changes = expander.expand_person(JEAN_PIERRE_DUPONT)
    assert ACME not in changes.new_entities
    assert mandates(graph_store) == {
        (JEAN_PIERRE_DUPONT, ACME, "Président"),
        (HOLDING, ACME, "Directeur général"),
        (foreign_company_identifier("DUPONT INVEST LTD", ""), ACME, "Associé"),
    }


def test_a_person_expansion_reads_the_search_results_page_by_page(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    fake_api: FakeApi,
    graph_store: GraphStore,
) -> None:
    expander = GraphExpander(
        investigation_connection,
        CompanyRegister(http_client, results_per_page=1),
        Bodacc(http_client),
    )
    expander.expand_company("222222222")
    expander.expand_person(JEAN_DUPONT)
    director_searches = [
        request for request in fake_api.requests if "nom_personne" in request.url.params
    ]
    assert [request.url.params["page"] for request in director_searches] == ["1", "2", "3", "4"]
    assert graph_store.entity(DUPONT_RENOVATION) is not None


def test_a_person_expansion_stops_after_four_pages(
    investigation_connection: sqlite3.Connection,
    http_client: CollectorHttpClient,
    fake_api: FakeApi,
) -> None:
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO,
        companies=(*FAKE_PLUMBERS_SCENARIO.companies, DUPONT_SERVICES_COMPANY),
    )
    expander = GraphExpander(
        investigation_connection,
        CompanyRegister(http_client, results_per_page=1),
        Bodacc(http_client),
    )
    expander.expand_company("222222222")
    expander.expand_person(JEAN_DUPONT)
    director_searches = [
        request for request in fake_api.requests if "nom_personne" in request.url.params
    ]
    assert len(director_searches) == 4


@pytest.mark.parametrize("identifier", ["person:0000000000000000", DUPONT_SERVICES])
def test_only_a_person_of_the_investigation_can_be_expanded_as_a_person(
    expander: GraphExpander, identifier: str
) -> None:
    expander.expand_company("222222222")
    with pytest.raises(ExpansionError) as failure:
        expander.expand_person(identifier)
    assert str(failure.value) == (
        "Cette entité n'est pas dans l'enquête ou ne peut pas être étendue."
    )


@pytest.mark.parametrize(
    ("director", "bears"),
    [
        (NaturalPersonDirector("Dupont", "jean", "1980-05", None, None), True),
        (NaturalPersonDirector("DUPONT", "Jean Pierre", None, None, None), True),
        (NaturalPersonDirector("DUPONT", "Jean", "1975-01", None, None), False),
        (NaturalPersonDirector("DUPONT", "Marie", "1980-05", None, None), False),
        (NaturalPersonDirector("DUPONTEL", "Jean", "1980-05", None, None), False),
        (NaturalPersonDirector(None, "Jean", "1980-05", None, None), False),
    ],
)
def test_a_director_bears_the_searched_name_when_names_and_birth_month_agree(
    director: NaturalPersonDirector, bears: bool
) -> None:
    assert SearchedName("DUPONT", "Jean", "1980-05").bears(director) is bears
    assert SearchedName("DUPONT", "Jean", None).bears(director) is (
        bears or director.birth_month == "1975-01"
    )


def registered_offices(graph_store: GraphStore) -> set[tuple[str, str]]:
    return {
        (link.source, link.target)
        for link in graph_store.links()
        if link.kind is LinkKind.REGISTERED_OFFICE
    }


def test_expanding_the_address_of_the_scenario_finds_the_companies_registered_there(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("111111111")
    changes = expander.expand_address(SHARED_ADDRESS)
    assert set(changes.new_entities) == {DUPONT_SERVICES, DUPONT_SERVICES_HEAD_OFFICE}
    assert registered_offices(graph_store) == {
        (ACME, SHARED_ADDRESS),
        (DUPONT_SERVICES, SHARED_ADDRESS),
    }
    assert (
        DUPONT_SERVICES_HEAD_OFFICE,
        LinkKind.LOCATED_AT,
        SHARED_ADDRESS,
    ) in {(link.source, link.kind, link.target) for link in graph_store.links()}


def test_an_address_expansion_leaves_out_other_cities_and_hidden_companies(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("111111111")
    expander.expand_address(SHARED_ADDRESS)
    identifiers = {entity.identifier for entity in graph_store.entities()}
    assert "company:555555555" not in identifiers
    assert "company:999999999" not in identifiers
    assert graph_store.entity(JEAN_DUPONT) is None


def test_an_establishment_at_the_address_is_found_without_a_registered_office(
    expander: GraphExpander, fake_api: FakeApi, graph_store: GraphStore
) -> None:
    branch = FictionalCompany(
        siren="888888888",
        name="PLOMBERIE DU SUD",
        establishments=(
            HOLDING_DUPONT.establishments[0],
            FictionalEstablishment("00023", SHARED_ADDRESS_OF_SCENARIO, "2024-02-01"),
        ),
        directors=(),
        creation_date="2018-01-01",
    )
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO, companies=(*FAKE_PLUMBERS_SCENARIO.companies, branch)
    )
    expander.expand_company("111111111")
    changes = expander.expand_address(SHARED_ADDRESS)
    branch_establishment = establishment_identifier("88888888800023")
    assert branch_establishment in changes.new_entities
    assert establishment_identifier("88888888800015") not in changes.new_entities
    assert ("company:888888888", SHARED_ADDRESS) not in registered_offices(graph_store)


def test_an_expanded_address_records_when_it_was_expanded(
    expander: GraphExpander, graph_store: GraphStore
) -> None:
    expander.expand_company("111111111")
    expander.expand_address(SHARED_ADDRESS)
    address = graph_store.require_entity(SHARED_ADDRESS)
    assert address.attributes["expanded_at"] == EXPANDED_AT.isoformat()
    assert address.attributes["text"] == "12 RUE DES LILAS 31000 TOULOUSE"


def test_expanding_an_address_twice_adds_nothing_new(expander: GraphExpander) -> None:
    expander.expand_company("111111111")
    expander.expand_address(SHARED_ADDRESS)
    assert expander.expand_address(SHARED_ADDRESS).is_empty


def test_only_an_address_of_the_investigation_can_be_expanded_as_an_address(
    expander: GraphExpander,
) -> None:
    expander.expand_company("111111111")
    with pytest.raises(ExpansionError):
        expander.expand_address(ACME)


def test_a_company_found_by_the_search_at_another_address_is_left_out(
    expander: GraphExpander, fake_api: FakeApi, graph_store: GraphStore
) -> None:
    neighbour = FictionalCompany(
        siren="888888888",
        name="VOISIN DES LILAS",
        establishments=(
            FictionalEstablishment(
                "00015", replace(SHARED_ADDRESS_OF_SCENARIO, number="112"), "2021-01-01"
            ),
        ),
        directors=(),
        creation_date="2021-01-01",
    )
    fake_api.scenario = replace(
        FAKE_PLUMBERS_SCENARIO, companies=(*FAKE_PLUMBERS_SCENARIO.companies, neighbour)
    )
    expander.expand_company("111111111")
    expander.expand_address(SHARED_ADDRESS)
    assert graph_store.entity("company:888888888") is None
