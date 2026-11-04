from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from fake_time import FakeTime
from lacis import __version__
from lacis.collectors.http_client import (
    REQUEST_TIMEOUT,
    USER_AGENT,
    CollectionError,
    CollectorHttpClient,
    current_time,
)
from lacis.collectors.rate_limiting import RateLimiters
from lacis.collectors.retries import DEFAULT_RETRY_POLICY, RetryPolicy, parse_retry_after
from lacis.storage.responses import ResponseSource

SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"
Handler = Callable[[httpx.Request], httpx.Response]


NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def received_requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def retry_sleeps() -> list[float]:
    return []


def client_answering(
    handler: Handler, received_requests: list[httpx.Request], retry_sleeps: list[float]
) -> CollectorHttpClient:
    def recording_handler(request: httpx.Request) -> httpx.Response:
        received_requests.append(request)
        return handler(request)

    fake_time = FakeTime()
    return CollectorHttpClient(
        httpx.MockTransport(recording_handler),
        RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
        sleep=retry_sleeps.append,
        now=lambda: NOW,
    )


@pytest.fixture
def client_factory(
    received_requests: list[httpx.Request], retry_sleeps: list[float]
) -> Iterator[Callable[[Handler], CollectorHttpClient]]:
    created_clients: list[CollectorHttpClient] = []

    def create(handler: Handler) -> CollectorHttpClient:
        client = client_answering(handler, received_requests, retry_sleeps)
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


def test_a_refused_request_reaches_the_caller_with_a_french_message_without_retry(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(lambda request: httpx.Response(404))
    with pytest.raises(CollectionError) as refusal:
        client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "000000000"})
    assert str(refusal.value) == (
        "Le service Recherche d'entreprises a refusé la requête (erreur 404)."
    )
    assert refusal.value.http_status == 404
    assert refusal.value.source is ResponseSource.COMPANY_REGISTER
    assert len(received_requests) == 1


def test_an_unreachable_service_reaches_the_caller_after_the_last_retry(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
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
    assert len(received_requests) == DEFAULT_RETRY_POLICY.maximum_attempts


def answers(*responses: httpx.Response) -> Handler:
    remaining = list(responses)

    def answer(request: httpx.Request) -> httpx.Response:
        return remaining.pop(0)

    return answer


def test_a_429_response_is_retried_after_the_delay_given_by_the_api(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
    retry_sleeps: list[float],
) -> None:
    client = client_factory(
        answers(
            httpx.Response(429, headers={"Retry-After": "3"}), httpx.Response(200, content=b"{}")
        )
    )
    fetched = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "dupont"})
    assert fetched.http_status == 200
    assert len(received_requests) == 2
    assert retry_sleeps == [3.0]


def test_a_retry_after_given_as_a_date_is_honoured(
    client_factory: Callable[[Handler], CollectorHttpClient],
    retry_sleeps: list[float],
) -> None:
    retry_date = format_datetime(NOW + timedelta(seconds=7), usegmt=True)
    client = client_factory(
        answers(httpx.Response(503, headers={"Retry-After": retry_date}), httpx.Response(200))
    )
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert retry_sleeps == [7.0]


def test_server_errors_are_retried_with_an_exponential_backoff(
    client_factory: Callable[[Handler], CollectorHttpClient],
    retry_sleeps: list[float],
) -> None:
    client = client_factory(
        answers(httpx.Response(500), httpx.Response(502), httpx.Response(503), httpx.Response(200))
    )
    assert client.get(ResponseSource.BODACC, SEARCH_URL, {}).http_status == 200
    assert retry_sleeps == [0.5, 1.0, 2.0]


def test_after_the_last_retry_a_429_reaches_the_caller_with_a_french_message(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(lambda request: httpx.Response(429, headers={"Retry-After": "1"}))
    with pytest.raises(CollectionError) as failure:
        client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {})
    assert str(failure.value) == (
        "Le service Recherche d'entreprises limite le nombre de requêtes. "
        "Patientez quelques minutes, puis réessayez."
    )
    assert failure.value.http_status == 429
    assert len(received_requests) == DEFAULT_RETRY_POLICY.maximum_attempts


def test_after_the_last_retry_a_server_error_reaches_the_caller_with_a_french_message(
    client_factory: Callable[[Handler], CollectorHttpClient],
) -> None:
    client = client_factory(lambda request: httpx.Response(502))
    with pytest.raises(CollectionError) as failure:
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert str(failure.value) == (
        "Le service BODACC est momentanément indisponible (erreur 502). Réessayez plus tard."
    )


def test_a_network_failure_is_retried_before_giving_up(
    client_factory: Callable[[Handler], CollectorHttpClient],
    retry_sleeps: list[float],
) -> None:
    attempts: list[int] = []

    def fail_once(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(200)

    client = client_factory(fail_once)
    assert client.get(ResponseSource.BODACC, SEARCH_URL, {}).http_status == 200
    assert retry_sleeps == [0.5]


@pytest.mark.parametrize(
    ("retry_after", "expected_delay"),
    [
        ("3", timedelta(seconds=3)),
        (" 12 ", timedelta(seconds=12)),
        (format_datetime(NOW + timedelta(minutes=1), usegmt=True), timedelta(minutes=1)),
        (format_datetime(NOW - timedelta(minutes=1), usegmt=True), timedelta(0)),
        ("Wed, 04 Nov 2026 12:00:30", timedelta(seconds=30)),
        ("tomorrow", None),
    ],
)
def test_retry_after_values_are_read_as_seconds_or_dates(
    retry_after: str, expected_delay: timedelta | None
) -> None:
    assert parse_retry_after(retry_after, NOW) == expected_delay


def test_long_delays_are_capped() -> None:
    policy = RetryPolicy(maximum_delay=timedelta(seconds=60))
    assert policy.delay_before_retry(1, "3600", NOW) == timedelta(seconds=60)
    assert policy.backoff_delay(20) == timedelta(seconds=60)
    assert policy.delay_before_retry(2, "tomorrow", NOW) == timedelta(seconds=1)


def test_retry_dates_are_compared_with_the_current_time_in_utc() -> None:
    assert current_time().tzinfo is UTC
    assert abs(current_time() - datetime.now(UTC)) < timedelta(seconds=5)
