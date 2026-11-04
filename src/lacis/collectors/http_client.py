import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from lacis import __version__
from lacis.collectors.rate_limiting import SHARED_RATE_LIMITERS, RateLimiters, Sleep
from lacis.collectors.retries import (
    DEFAULT_RETRY_POLICY,
    RETRY_AFTER_HEADER,
    TOO_MANY_REQUESTS,
    RetryPolicy,
    is_retryable_status,
)
from lacis.product import REPOSITORY_URL
from lacis.storage.responses import ResponseSource

USER_AGENT = f"Lacis/{__version__} (+{REPOSITORY_URL})"
REQUEST_TIMEOUT = timedelta(seconds=10)
SUCCESSFUL_HTTP_STATUSES = range(200, 300)
SOURCE_NAMES = {
    ResponseSource.COMPANY_REGISTER: "Recherche d'entreprises",
    ResponseSource.BODACC: "BODACC",
}


class CollectionError(Exception):
    def __init__(self, message: str, source: ResponseSource, http_status: int | None) -> None:
        super().__init__(message)
        self.source = source
        self.http_status = http_status


def refused_request_message(source: ResponseSource, http_status: int) -> str:
    return f"Le service {SOURCE_NAMES[source]} a refusé la requête (erreur {http_status})."


def too_many_requests_message(source: ResponseSource) -> str:
    return (
        f"Le service {SOURCE_NAMES[source]} limite le nombre de requêtes. "
        "Patientez quelques minutes, puis réessayez."
    )


def unavailable_service_message(source: ResponseSource, http_status: int) -> str:
    return (
        f"Le service {SOURCE_NAMES[source]} est momentanément indisponible "
        f"(erreur {http_status}). Réessayez plus tard."
    )


def final_failure_message(source: ResponseSource, http_status: int) -> str:
    if http_status == TOO_MANY_REQUESTS:
        return too_many_requests_message(source)
    return unavailable_service_message(source, http_status)


def current_time() -> datetime:
    return datetime.now(UTC)


def unreachable_service_message(source: ResponseSource) -> str:
    return (
        f"Le service {SOURCE_NAMES[source]} ne répond pas. "
        "Vérifiez votre connexion à Internet, puis réessayez."
    )


@dataclass(frozen=True)
class FetchedResponse:
    source: ResponseSource
    url: str
    parameters: dict[str, str]
    http_status: int
    body: bytes


class CollectorHttpClient:
    def __init__(
        self,
        transport: httpx.BaseTransport | None = None,
        rate_limiters: RateLimiters = SHARED_RATE_LIMITERS,
        retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY,
        sleep: Sleep = time.sleep,
        now: Callable[[], datetime] = current_time,
    ) -> None:
        self.rate_limiters = rate_limiters
        self.retry_policy = retry_policy
        self.sleep = sleep
        self.now = now
        self.client = httpx.Client(
            transport=transport,
            timeout=REQUEST_TIMEOUT.total_seconds(),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def get(self, source: ResponseSource, url: str, parameters: dict[str, str]) -> FetchedResponse:
        attempt = 1
        while True:
            is_last_attempt = attempt == self.retry_policy.maximum_attempts
            self.rate_limiters.wait_for(source)
            try:
                response = self.client.get(url, params=parameters)
            except httpx.TransportError as transport_error:
                if is_last_attempt:
                    raise CollectionError(
                        unreachable_service_message(source), source, None
                    ) from transport_error
                self.wait_before_retry(attempt, None)
                attempt += 1
                continue
            if response.status_code in SUCCESSFUL_HTTP_STATUSES:
                return FetchedResponse(
                    source, url, parameters, response.status_code, response.content
                )
            if not is_retryable_status(response.status_code):
                raise CollectionError(
                    refused_request_message(source, response.status_code),
                    source,
                    response.status_code,
                )
            if is_last_attempt:
                raise CollectionError(
                    final_failure_message(source, response.status_code),
                    source,
                    response.status_code,
                )
            self.wait_before_retry(attempt, response.headers.get(RETRY_AFTER_HEADER))
            attempt += 1

    def wait_before_retry(self, failed_attempts: int, retry_after: str | None) -> None:
        delay = self.retry_policy.delay_before_retry(failed_attempts, retry_after, self.now())
        self.sleep(delay.total_seconds())
