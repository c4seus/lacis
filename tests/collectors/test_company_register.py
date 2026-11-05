import json
from collections.abc import Callable, Iterator

import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.company_register import (
    Company,
    CompanyRegister,
    Identifier,
    IdentifierKind,
    InvalidQueryError,
    LegalPersonDirector,
    NaturalPersonDirector,
    identifier_in,
)
from lacis.collectors.fake_api import FakeApi
from lacis.collectors.fake_plumbers import FAKE_PLUMBERS_SCENARIO
from lacis.collectors.http_client import CollectionError, CollectorHttpClient, CollectorTiming
from lacis.collectors.rate_limiting import RateLimiters
from lacis.storage.collection_log import CollectionLog
from lacis.storage.responses import ResponseStore

Handler = Callable[[httpx.Request], httpx.Response]
RegisterFactory = Callable[..., CompanyRegister]


@pytest.fixture
def fake_api() -> FakeApi:
    return FakeApi(FAKE_PLUMBERS_SCENARIO)


@pytest.fixture
def register_factory(
    fake_api: FakeApi, response_store: ResponseStore, collection_log: CollectionLog
) -> Iterator[RegisterFactory]:
    http_clients: list[CollectorHttpClient] = []

    def create(handler: Handler = fake_api, results_per_page: int = 25) -> CompanyRegister:
        fake_time = FakeTime()
        http_client = CollectorHttpClient(
            response_store,
            collection_log,
            httpx.MockTransport(handler),
            CollectorTiming(
                rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
                monotonic=fake_time.clock,
            ),
        )
        http_clients.append(http_client)
        return CompanyRegister(http_client, results_per_page)

    yield create
    for http_client in http_clients:
        http_client.close()


@pytest.fixture
def register(register_factory: RegisterFactory) -> CompanyRegister:
    return register_factory()


def names(companies: tuple[Company, ...]) -> list[object]:
    return [company.name for company in companies]


def sirets(company: Company) -> list[str]:
    return [establishment.siret for establishment in company.matching_establishments]


def search_payload(results: list[dict[str, str]] | None) -> bytes:
    page = {"results": results, "page": 1, "per_page": 25, "total_results": 1, "total_pages": 1}
    return json.dumps(page).encode()


def sent_parameters(fake_api: FakeApi) -> list[dict[str, str]]:
    return [dict(request.url.params) for request in fake_api.requests]


@pytest.mark.parametrize(
    ("text", "identifier"),
    [
        ("111111111", Identifier(IdentifierKind.SIREN, "111111111")),
        (" 111 111 111 ", Identifier(IdentifierKind.SIREN, "111111111")),
        ("111\u00a0111\u202f111", Identifier(IdentifierKind.SIREN, "111111111")),
        ("111.111.111", Identifier(IdentifierKind.SIREN, "111111111")),
        ("111 111 111 00015", Identifier(IdentifierKind.SIRET, "11111111100015")),
        ("111-111-111-00015", Identifier(IdentifierKind.SIRET, "11111111100015")),
        ("12345", None),
        ("1111111111", None),
        ("ACME", None),
        ("", None),
    ],
)
def test_a_siren_or_siret_typed_with_spaces_is_recognised(
    text: str, identifier: Identifier | None
) -> None:
    assert identifier_in(text) == identifier


def test_a_search_by_name_reads_the_company_its_head_office_and_directors(
    register: CompanyRegister,
) -> None:
    [acme] = register.search("acme plomberie").companies
    assert acme.siren == "111111111"
    assert acme.name == "ACME PLOMBERIE"
    assert acme.acronym is None
    assert acme.is_active
    assert acme.legal_form == "5710"
    assert acme.activity == "43.22A"
    assert acme.creation_date == "2022-11-10"
    assert acme.closing_date is None
    assert acme.establishment_count == 1
    assert acme.open_establishment_count == 1
    assert acme.head_office is not None
    assert acme.head_office.siret == "11111111100015"
    assert acme.head_office.is_head_office
    assert acme.head_office.is_open
    assert acme.head_office.address.full_text == "12 RUE DES LILAS 31000 TOULOUSE"
    assert acme.head_office.address.number == "12"
    assert acme.head_office.address.street_type == "RUE"
    assert acme.head_office.address.street_name == "DES LILAS"
    assert acme.head_office.address.postcode == "31000"
    assert acme.head_office.address.city == "TOULOUSE"
    assert acme.head_office.address.city_code == "31555"
    assert acme.directors[0] == NaturalPersonDirector(
        "DUPONT", "Jean Pierre", "1980-05", "Président", "Française"
    )
    assert acme.directors[1] == LegalPersonDirector(
        "HOLDING DUPONT", "333333333", "Directeur général"
    )
    assert acme.directors[2] == LegalPersonDirector("DUPONT INVEST LTD", None, "Associé")


def test_a_closed_company_is_read_as_closed(register: CompanyRegister) -> None:
    [dupont_services] = register.search("dupont services").companies
    assert not dupont_services.is_active
    assert dupont_services.closing_date == "2023-01-15"
    assert dupont_services.head_office is not None
    assert not dupont_services.head_office.is_open


def test_a_siren_typed_with_spaces_is_sent_as_digits(
    register: CompanyRegister, fake_api: FakeApi
) -> None:
    [acme] = register.search("111 111 111").companies
    assert acme.siren == "111111111"
    assert sent_parameters(fake_api) == [{"q": "111111111", "page": "1", "per_page": "25"}]


def test_a_siret_typed_with_spaces_finds_its_establishment(
    register: CompanyRegister, fake_api: FakeApi
) -> None:
    [dupont_services] = register.search("222 222 222 00015").companies
    assert sirets(dupont_services) == ["22222222200015"]
    assert sent_parameters(fake_api)[0]["q"] == "22222222200015"


def test_a_search_by_address_finds_the_companies_at_that_address(
    register: CompanyRegister,
) -> None:
    search_page = register.search("12 rue des lilas toulouse")
    assert names(search_page.companies) == ["ACME PLOMBERIE", "DUPONT SERVICES"]
    assert sirets(search_page.companies[0]) == ["11111111100015"]


def test_a_search_by_director_finds_the_companies_they_direct(
    register: CompanyRegister, fake_api: FakeApi
) -> None:
    jean_dupont = register.search_director(" dupont ", " jean ")
    assert names(jean_dupont.companies) == [
        "ACME PLOMBERIE",
        "DUPONT SERVICES",
        "HOLDING DUPONT",
        "DUPONT RENOVATION",
    ]
    every_dupont = register.search_director("dupont")
    assert "AUTRE SOCIETE" in names(every_dupont.companies)
    assert sent_parameters(fake_api) == [
        {"nom_personne": "dupont", "prenoms_personne": "jean", "page": "1", "per_page": "25"},
        {"nom_personne": "dupont", "page": "1", "per_page": "25"},
    ]


def test_search_results_are_read_page_by_page(register_factory: RegisterFactory) -> None:
    register = register_factory(results_per_page=2)
    first_page = register.search_director("dupont")
    assert len(first_page.companies) == 2
    assert first_page.page == 1
    assert first_page.per_page == 2
    assert first_page.total_results == 5
    assert first_page.total_pages == 3
    assert first_page.has_next_page
    last_page = register.search_director("dupont", page=3)
    assert names(last_page.companies) == ["DUPONT RENOVATION"]
    assert not last_page.has_next_page
    every_company = [
        *first_page.companies,
        *register.search_director("dupont", page=2).companies,
        *last_page.companies,
    ]
    assert len({company.siren for company in every_company}) == 5


def test_an_unknown_company_gives_an_empty_page(register: CompanyRegister) -> None:
    search_page = register.search("boulangerie marseille")
    assert search_page.companies == ()
    assert search_page.total_results == 0
    assert not search_page.has_next_page


@pytest.mark.parametrize(
    ("search", "message"),
    [
        (
            lambda register: register.search("  "),
            "Saisissez un nom, un SIREN, un SIRET, un dirigeant ou une adresse.",
        ),
        (lambda register: register.search_director(" "), "Saisissez le nom du dirigeant."),
        (
            lambda register: register.search("acme", page=0),
            "La page 0 n'existe pas : les pages commencent à 1.",
        ),
    ],
)
def test_an_invalid_search_is_refused_before_any_request(
    register: CompanyRegister,
    fake_api: FakeApi,
    search: Callable[[CompanyRegister], object],
    message: str,
) -> None:
    with pytest.raises(InvalidQueryError) as refusal:
        search(register)
    assert str(refusal.value) == message
    assert fake_api.requests == []


def test_every_search_page_keeps_its_stored_response(
    register: CompanyRegister, response_store: ResponseStore
) -> None:
    search_page = register.search("acme")
    assert response_store.summaries() == [search_page.response]
    assert search_page.response.parameters == {"q": "acme", "page": "1", "per_page": "25"}


def test_a_repeated_search_is_served_from_the_cache_unless_refreshed(
    register: CompanyRegister, fake_api: FakeApi
) -> None:
    register.search("acme")
    register.search("acme")
    assert len(fake_api.requests) == 1
    register.search("acme", refresh=True)
    assert len(fake_api.requests) == 2


@pytest.mark.parametrize(
    "body",
    [
        b"<html>maintenance</html>",
        b"{}",
        search_payload([{"nom_complet": "SANS SIREN"}]),
        search_payload(None),
    ],
)
def test_an_unreadable_response_reaches_the_caller_with_a_french_message(
    register_factory: RegisterFactory, body: bytes
) -> None:
    register = register_factory(lambda request: httpx.Response(200, content=body))
    with pytest.raises(CollectionError) as failure:
        register.search("acme")
    assert str(failure.value) == (
        "La réponse du service Recherche d'entreprises est illisible. Réessayez plus tard."
    )
    assert failure.value.http_status is None
