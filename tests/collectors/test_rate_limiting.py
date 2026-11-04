import httpx
import pytest

from fake_time import FakeTime
from lacis.collectors.http_client import CollectorHttpClient
from lacis.collectors.rate_limiting import (
    REQUESTS_PER_SECOND,
    SHARED_RATE_LIMITERS,
    RateLimiter,
    RateLimiters,
)
from lacis.storage.responses import ResponseSource

DOCUMENTED_COMPANY_REGISTER_QUOTA = 7


def most_requests_in_one_second(request_times: list[float]) -> int:
    return max(
        sum(1 for other_time in request_times if start <= other_time < start + 1)
        for start in request_times
    )


def test_the_rates_stay_below_the_quota_of_each_api() -> None:
    assert REQUESTS_PER_SECOND[ResponseSource.COMPANY_REGISTER] < DOCUMENTED_COMPANY_REGISTER_QUOTA
    assert set(REQUESTS_PER_SECOND) == set(ResponseSource)
    assert set(SHARED_RATE_LIMITERS.limiters) == set(ResponseSource)


@pytest.mark.parametrize("requests_per_second", [6, 5, 1])
def test_no_more_requests_per_second_than_the_limit(requests_per_second: int) -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(requests_per_second, fake_time.clock, fake_time.sleep)
    request_times: list[float] = []
    for _ in range(30):
        limiter.wait()
        request_times.append(fake_time.now)
    assert most_requests_in_one_second(request_times) <= requests_per_second


def test_the_first_request_does_not_wait() -> None:
    fake_time = FakeTime()
    RateLimiter(6, fake_time.clock, fake_time.sleep).wait()
    assert fake_time.sleeps == []


def test_requests_within_the_limit_do_not_wait() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(5, fake_time.clock, fake_time.sleep)
    for _ in range(5):
        limiter.wait()
    assert fake_time.sleeps == []


def test_the_request_over_the_limit_waits_until_the_oldest_one_is_a_second_old() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(5, fake_time.clock, fake_time.sleep)
    for _ in range(5):
        limiter.wait()
        fake_time.advance(0.1)
    limiter.wait()
    assert fake_time.sleeps == [pytest.approx(0.5)]


def test_a_request_after_a_pause_does_not_wait() -> None:
    fake_time = FakeTime()
    limiter = RateLimiter(5, fake_time.clock, fake_time.sleep)
    for _ in range(5):
        limiter.wait()
    fake_time.advance(1.0)
    limiter.wait()
    assert fake_time.sleeps == []


def test_each_source_has_its_own_rate() -> None:
    fake_time = FakeTime()
    rate_limiters = RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep)
    for _ in range(5):
        rate_limiters.wait_for(ResponseSource.BODACC)
    rate_limiters.wait_for(ResponseSource.COMPANY_REGISTER)
    assert fake_time.sleeps == []
    rate_limiters.wait_for(ResponseSource.BODACC)
    assert fake_time.sleeps == [pytest.approx(1.0)]


def test_the_client_waits_for_the_rate_of_the_source_before_each_request() -> None:
    fake_time = FakeTime()
    request_times: list[float] = []

    def answer(request: httpx.Request) -> httpx.Response:
        request_times.append(fake_time.now)
        return httpx.Response(200)

    client = CollectorHttpClient(
        httpx.MockTransport(answer), RateLimiters(clock=fake_time.clock, sleep=fake_time.sleep)
    )
    try:
        for _ in range(20):
            client.get(ResponseSource.COMPANY_REGISTER, "https://example.test/search", {})
    finally:
        client.close()
    assert most_requests_in_one_second(request_times) == 6
    assert request_times[-1] - request_times[0] == pytest.approx(3.0)
