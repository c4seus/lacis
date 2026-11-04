from collections.abc import Callable, Iterator

import httpx
import pytest

from lacis import __version__
from lacis.collectors.http_client import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    CollectionError,
    CollectorHttpClient,
)
from lacis.storage.responses import ResponseSource

SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"
Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def received_requests() -> list[httpx.Request]:
    return []


def client_answering(
    handler: Handler, received_requests: list[httpx.Request]
) -> CollectorHttpClient:
    def recording_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return handler(request)

    return CollectorHttpClient(httpx.MockTransport(recording_handler))


@pytest.fixture
def client_factory(
    received_requests: list[httpx.Request],
) -> Iterator[Callable[[Handler], CollectorHttpClient]]:
    created_clients: list[CollectorHttpClient] = []

    def create(handler: Handler) -> CollectorHttpClient:
        client = client_answering(handler, received_requests)
        created_clients.append(client)
        return client

    yield create
    for client in created_clients:
        client.close()


def test_the_user_agent_names_lacis_its_version_and_its_repository() -> None:
    assert f"Lacis/{__version__} (+https://github.com/c4seus/lacis)" == USER_AGENT


def test_a_request_carries_the_user_agent_and_the_parameters(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(lambda request: httpx.Response(200, content=b'{"results": []}'))
    fetched = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    assert fetched.body == b'{"results": []}'
    assert fetched.http_status == 200
    assert fetched.parameters == {"q": "222222222"}
    request = received_requests[0]
    assert request.headers["User-Agent"] == USER_AGENT
    assert request.headers["Accept"] == "application/json"
    assert request.url.params["q"] == "222222222"
    assert str(request.url.copy_with(query=None)) == SEARCH_URL


def test_requests_time_out_after_ten_seconds(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(lambda request: httpx.Response(200))
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert REQUEST_TIMEOUT.total_seconds() == 10
    assert received_requests[0].extensions["timeout"] == {
        "connect": 10.0,
        "read": 10.0,
        "write": 10.0,
        "pool": 10.0,
    }


def test_a_refused_request_reaches_the_caller_with_a_french_message(
    client_factory: Callable[[Handler], CollectorHttpClient],
) -> None:
    client = client_factory(lambda request: httpx.Response(404))
    with pytest.raises(CollectionError) as refusal:
        client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "000000000"})
    assert str(refusal.value) == (
        "Le service Recherche d'entreprises a refusé la requête (erreur 404)."
    )
    assert refusal.value.http_status == 404
    assert refusal.value.source is ResponseSource.COMPANY_REGISTER


def test_an_unreachable_service_reaches_the_caller_with_a_french_message(
    client_factory: Callable[[Handler], CollectorHttpClient],
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Name or service not known", request=request)

    client = client_factory(fail)
    with pytest.raises(CollectionError) as failure:
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert str(failure.value) == (
        "Le service BODACC ne répond pas. Vérifiez votre connexion à Internet, puis réessayez."
    )
    assert failure.value.http_status is None
