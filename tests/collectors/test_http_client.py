import hashlib
import logging
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from fake_time import FakeTime, FakeWallClock
from lacis import __version__
from lacis.collectors.http_client import (
    CACHE_LIFETIME,
    COLLECTORS_LOGGER_NAME,
    REQUEST_TIMEOUT,
    USER_AGENT,
    CollectionCancelledError,
    CollectionControl,
    CollectionError,
    CollectorHttpClient,
    CollectorTiming,
    current_time,
    ignore_request,
    too_many_requests_message,
    unavailable_service_message,
)
from lacis.collectors.rate_limiting import RateLimiters
from lacis.collectors.retries import DEFAULT_RETRY_POLICY, RetryPolicy, parse_retry_after
from lacis.storage.collection_log import CollectionLog, RequestStatus
from lacis.storage.responses import ResponseSource, ResponseStore

SEARCH_URL = "https://recherche-entreprises.api.gouv.fr/search"
REQUEST_DURATION = 0.25
Handler = Callable[[httpx.Request], httpx.Response]


NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


@pytest.fixture
def received_requests() -> list[httpx.Request]:
    return []


@pytest.fixture
def retry_sleeps() -> list[float]:
    return []


@pytest.fixture
def fake_time() -> FakeTime:
    return FakeTime()


@pytest.fixture
def wall_clock() -> FakeWallClock:
    return FakeWallClock(NOW)


@pytest.fixture
def collector_timing(
    fake_time: FakeTime, wall_clock: FakeWallClock, retry_sleeps: list[float]
) -> CollectorTiming:
    return CollectorTiming(
        rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
        sleep=retry_sleeps.append,
        now=wall_clock.now,
        monotonic=fake_time.clock,
    )


@pytest.fixture
def client_factory(
    response_store: ResponseStore,
    collection_log: CollectionLog,
    collector_timing: CollectorTiming,
    fake_time: FakeTime,
    received_requests: list[httpx.Request],
) -> Iterator[Callable[[Handler], CollectorHttpClient]]:
    created_clients: list[CollectorHttpClient] = []

    def create(handler: Handler) -> CollectorHttpClient:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            received_requests.append(request)
            fake_time.advance(REQUEST_DURATION)
            return handler(request)

        client = CollectorHttpClient(
            response_store,
            collection_log,
            httpx.MockTransport(recording_handler),
            collector_timing,
        )
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
    stored = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    assert stored.body == b'{"results": []}'
    assert stored.summary.parameters == {"q": "222222222"}
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
    stored = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "dupont"})
    assert stored.body == b"{}"
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
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
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
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
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


def test_a_successful_response_is_kept_in_the_investigation_with_its_fingerprint(
    client_factory: Callable[[Handler], CollectorHttpClient],
    response_store: ResponseStore,
) -> None:
    body = b'{"results": [{"siren": "222222222", "nom_complet": "DUPONT SERVICES"}]}'
    client = client_factory(lambda request: httpx.Response(200, content=body))
    stored = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    assert response_store.summaries() == [stored.summary]
    assert response_store.read(stored.summary.identifier) == stored
    assert stored.summary.source is ResponseSource.COMPANY_REGISTER
    assert stored.summary.url == SEARCH_URL
    assert stored.summary.collected_at == NOW
    assert stored.summary.fingerprint == hashlib.sha256(body).hexdigest()


def test_a_successful_request_is_logged_with_its_response(
    client_factory: Callable[[Handler], CollectorHttpClient],
    collection_log: CollectionLog,
) -> None:
    client = client_factory(lambda request: httpx.Response(200, content=b"{}"))
    stored = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    [entry] = collection_log.entries()
    assert entry.request.requested_at == NOW
    assert entry.request.source is ResponseSource.COMPANY_REGISTER
    assert entry.request.endpoint == SEARCH_URL
    assert entry.request.http_status == 200
    assert entry.request.duration == timedelta(seconds=REQUEST_DURATION)
    assert not entry.request.served_from_cache
    assert entry.request.error == ""
    assert entry.request.response_identifier == stored.summary.identifier
    assert entry.request.status is RequestStatus.SUCCEEDED


def test_every_retried_attempt_is_logged_without_keeping_failed_responses(
    client_factory: Callable[[Handler], CollectorHttpClient],
    collection_log: CollectionLog,
    response_store: ResponseStore,
) -> None:
    client = client_factory(
        answers(
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(503, content=b"maintenance"),
            httpx.Response(200, content=b"{}"),
        )
    )
    stored = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {})
    entries = list(reversed(collection_log.entries()))
    assert [entry.request.http_status for entry in entries] == [429, 503, 200]
    assert [entry.request.status for entry in entries] == [
        RequestStatus.FAILED,
        RequestStatus.FAILED,
        RequestStatus.SUCCEEDED,
    ]
    assert [entry.request.error for entry in entries] == [
        too_many_requests_message(ResponseSource.COMPANY_REGISTER),
        unavailable_service_message(ResponseSource.COMPANY_REGISTER, 503),
        "",
    ]
    assert [entry.request.response_identifier for entry in entries] == [
        None,
        None,
        stored.summary.identifier,
    ]
    assert response_store.summaries() == [stored.summary]


def test_a_refused_request_is_logged_before_reaching_the_caller(
    client_factory: Callable[[Handler], CollectorHttpClient],
    collection_log: CollectionLog,
    response_store: ResponseStore,
) -> None:
    client = client_factory(lambda request: httpx.Response(404))
    with pytest.raises(CollectionError) as refusal:
        client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {})
    [entry] = collection_log.entries(status=RequestStatus.FAILED)
    assert entry.request.http_status == 404
    assert entry.request.error == str(refusal.value)
    assert response_store.summaries() == []


def test_every_attempt_on_an_unreachable_service_is_logged_without_status(
    client_factory: Callable[[Handler], CollectorHttpClient],
    collection_log: CollectionLog,
) -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Name or service not known", request=request)

    client = client_factory(fail)
    with pytest.raises(CollectionError) as failure:
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    entries = collection_log.entries(source=ResponseSource.BODACC)
    assert len(entries) == DEFAULT_RETRY_POLICY.maximum_attempts
    assert {entry.request.http_status for entry in entries} == {None}
    assert {entry.request.error for entry in entries} == {str(failure.value)}
    assert {entry.request.duration for entry in entries} == {timedelta(seconds=REQUEST_DURATION)}


def test_requests_are_written_to_the_application_log(
    client_factory: Callable[[Handler], CollectorHttpClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = client_factory(answers(httpx.Response(502), httpx.Response(200, content=b"{}")))
    with caplog.at_level(logging.INFO, logger=COLLECTORS_LOGGER_NAME):
        stored = client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert [record.getMessage() for record in caplog.records] == [
        f"GET {SEARCH_URL} failed with status 502",
        f"GET {SEARCH_URL} returned 200, fingerprint {stored.summary.fingerprint}",
    ]
    assert [record.levelno for record in caplog.records] == [logging.WARNING, logging.INFO]


def test_a_second_identical_request_within_24_hours_is_served_from_the_cache(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
    collection_log: CollectionLog,
    wall_clock: FakeWallClock,
) -> None:
    client = client_factory(lambda request: httpx.Response(200, content=b'{"results": []}'))
    collected = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    wall_clock.advance(CACHE_LIFETIME - timedelta(seconds=1))
    served = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    assert served == collected
    assert len(received_requests) == 1
    latest_entry = collection_log.entries()[0]
    assert latest_entry.request.served_from_cache
    assert latest_entry.request.requested_at == wall_clock.now()
    assert latest_entry.request.http_status is None
    assert latest_entry.request.duration == timedelta(0)
    assert latest_entry.request.response_identifier == collected.summary.identifier
    assert latest_entry.request.status is RequestStatus.SUCCEEDED


def test_a_cache_hit_waits_for_no_rate_limit(
    client_factory: Callable[[Handler], CollectorHttpClient],
    fake_time: FakeTime,
) -> None:
    client = client_factory(lambda request: httpx.Response(200))
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    for _ in range(20):
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert fake_time.sleeps == []


def test_a_response_24_hours_old_has_expired(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
    response_store: ResponseStore,
    wall_clock: FakeWallClock,
) -> None:
    client = client_factory(
        answers(httpx.Response(200, content=b"1"), httpx.Response(200, content=b"2"))
    )
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    wall_clock.advance(CACHE_LIFETIME)
    refreshed = client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert refreshed.body == b"2"
    assert len(received_requests) == 2
    assert len(response_store.summaries()) == 2


def test_only_the_same_request_is_served_from_the_cache(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(lambda request: httpx.Response(200))
    client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "333333333"})
    client.get(ResponseSource.BODACC, SEARCH_URL, {"q": "222222222"})
    assert len(received_requests) == 3


def test_failed_requests_are_never_served_from_the_cache(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(answers(httpx.Response(404), httpx.Response(200)))
    with pytest.raises(CollectionError):
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert len(received_requests) == 2


def test_a_cache_hit_is_written_to_the_application_log(
    client_factory: Callable[[Handler], CollectorHttpClient],
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = client_factory(lambda request: httpx.Response(200))
    stored = client.get(ResponseSource.BODACC, SEARCH_URL, {})
    with caplog.at_level(logging.INFO, logger=COLLECTORS_LOGGER_NAME):
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    assert [record.getMessage() for record in caplog.records] == [
        f"GET {SEARCH_URL} served from the cache, fingerprint {stored.summary.fingerprint}"
    ]


def test_a_refresh_always_queries_the_api(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
    collection_log: CollectionLog,
) -> None:
    client = client_factory(
        answers(httpx.Response(200, content=b"1"), httpx.Response(200, content=b"2"))
    )
    collected = client.get(ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"})
    refreshed = client.get(
        ResponseSource.COMPANY_REGISTER, SEARCH_URL, {"q": "222222222"}, refresh=True
    )
    assert refreshed.body == b"2"
    assert refreshed.summary.identifier != collected.summary.identifier
    assert len(received_requests) == 2
    assert not any(entry.request.served_from_cache for entry in collection_log.entries())


def test_the_refreshed_response_is_served_from_the_cache_afterwards(
    client_factory: Callable[[Handler], CollectorHttpClient],
    received_requests: list[httpx.Request],
) -> None:
    client = client_factory(
        answers(httpx.Response(200, content=b"1"), httpx.Response(200, content=b"2"))
    )
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    client.get(ResponseSource.BODACC, SEARCH_URL, {}, refresh=True)
    assert client.get(ResponseSource.BODACC, SEARCH_URL, {}).body == b"2"
    assert len(received_requests) == 2


def test_a_failed_refresh_reaches_the_caller_instead_of_the_cached_response(
    client_factory: Callable[[Handler], CollectorHttpClient],
) -> None:
    client = client_factory(answers(httpx.Response(200), httpx.Response(404)))
    client.get(ResponseSource.BODACC, SEARCH_URL, {})
    with pytest.raises(CollectionError):
        client.get(ResponseSource.BODACC, SEARCH_URL, {}, refresh=True)


def test_every_request_sent_is_reported_but_not_a_cache_hit(
    response_store: ResponseStore, collection_log: CollectionLog, collector_timing: CollectorTiming
) -> None:
    reported: list[str] = []
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(answers(httpx.Response(503), httpx.Response(200))),
        collector_timing,
        CollectionControl(request_made=lambda: reported.append("request")),
    )
    try:
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
        client.get(ResponseSource.BODACC, SEARCH_URL, {})
    finally:
        client.close()
    assert reported == ["request", "request"]


def test_requests_are_reported_to_nobody_by_default() -> None:
    ignore_request()


def test_a_cancelled_collection_sends_no_request(
    response_store: ResponseStore, collection_log: CollectionLog, collector_timing: CollectorTiming
) -> None:
    sent: list[httpx.Request] = []
    control = CollectionControl()
    control.cancellation.set()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(recording(sent, 200)),
        collector_timing,
        control,
    )
    try:
        with pytest.raises(CollectionCancelledError) as cancellation:
            client.get(ResponseSource.BODACC, SEARCH_URL, {})
    finally:
        client.close()
    assert str(cancellation.value) == (
        "Collecte annulée : les données déjà collectées sont conservées."
    )
    assert sent == []
    assert collection_log.entries() == []


def test_a_collection_cancelled_while_waiting_to_retry_stops_before_the_next_attempt(
    response_store: ResponseStore, collection_log: CollectionLog
) -> None:
    sent: list[httpx.Request] = []
    control = CollectionControl()
    fake_time = FakeTime()
    client = CollectorHttpClient(
        response_store,
        collection_log,
        httpx.MockTransport(recording(sent, 503)),
        CollectorTiming(
            rate_limiters=RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep),
            sleep=lambda seconds: control.cancellation.set(),
            monotonic=fake_time.clock,
        ),
        control,
    )
    try:
        with pytest.raises(CollectionCancelledError):
            client.get(ResponseSource.BODACC, SEARCH_URL, {})
    finally:
        client.close()
    assert len(sent) == 1
    assert len(collection_log.entries()) == 1


def recording(sent: list[httpx.Request], status: int) -> Handler:
    def answer(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status)

    return answer
