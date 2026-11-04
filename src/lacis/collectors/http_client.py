import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from lacis import __version__
from lacis.collectors.rate_limiting import SHARED_RATE_LIMITERS, Clock, RateLimiters, Sleep
from lacis.collectors.retries import (
    DEFAULT_RETRY_POLICY,
    RETRY_AFTER_HEADER,
    TOO_MANY_REQUESTS,
    RetryPolicy,
    is_retryable_status,
)
from lacis.diagnostics import LOGGER_NAME
from lacis.product import REPOSITORY_URL
from lacis.storage.collection_log import CollectionLog, LoggedRequest
from lacis.storage.responses import (
    CollectedResponse,
    ResponseSource,
    ResponseStore,
    StoredResponse,
)

USER_AGENT = f"Lacis/{__version__} (+{REPOSITORY_URL})"
COLLECTORS_LOGGER_NAME = f"{LOGGER_NAME}.collectors"
REQUEST_TIMEOUT = timedelta(seconds=10)
CACHE_LIFETIME = timedelta(hours=24)
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
class CollectorTiming:
    rate_limiters: RateLimiters = SHARED_RATE_LIMITERS
    retry_policy: RetryPolicy = DEFAULT_RETRY_POLICY
    sleep: Sleep = time.sleep
    now: Callable[[], datetime] = current_time
    monotonic: Clock = time.monotonic


DEFAULT_TIMING = CollectorTiming()


@dataclass(frozen=True)
class CollectorRequest:
    source: ResponseSource
    url: str
    parameters: dict[str, str]


@dataclass(frozen=True)
class AttemptStart:
    requested_at: datetime
    monotonic_time: float


class CollectorHttpClient:
    def __init__(
        self,
        response_store: ResponseStore,
        collection_log: CollectionLog,
        transport: httpx.BaseTransport | None = None,
        timing: CollectorTiming = DEFAULT_TIMING,
    ) -> None:
        self.response_store = response_store
        self.collection_log = collection_log
        self.timing = timing
        self.client = httpx.Client(
            transport=transport,
            timeout=REQUEST_TIMEOUT.total_seconds(),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def get(self, source: ResponseSource, url: str, parameters: dict[str, str]) -> StoredResponse:
        request = CollectorRequest(source, url, parameters)
        cached_response = self.cached_response(request)
        if cached_response is not None:
            return cached_response
        return self.fetch(request)

    def cached_response(self, request: CollectorRequest) -> StoredResponse | None:
        lookup_start = AttemptStart(self.timing.now(), self.timing.monotonic())
        stored_response = self.response_store.latest_collected_since(
            request.source,
            request.url,
            request.parameters,
            lookup_start.requested_at - CACHE_LIFETIME,
        )
        if stored_response is None:
            return None
        self.collection_log.record(
            LoggedRequest(
                requested_at=lookup_start.requested_at,
                source=request.source,
                endpoint=request.url,
                http_status=None,
                duration=self.elapsed_since(lookup_start),
                served_from_cache=True,
                response_identifier=stored_response.summary.identifier,
            )
        )
        logging.getLogger(COLLECTORS_LOGGER_NAME).info(
            "GET %s served from the cache, fingerprint %s",
            request.url,
            stored_response.summary.fingerprint,
        )
        return stored_response

    def fetch(self, request: CollectorRequest) -> StoredResponse:
        source = request.source
        attempt = 1
        while True:
            is_last_attempt = attempt == self.timing.retry_policy.maximum_attempts
            self.timing.rate_limiters.wait_for(source)
            attempt_start = AttemptStart(self.timing.now(), self.timing.monotonic())
            try:
                response = self.client.get(request.url, params=request.parameters)
            except httpx.TransportError as transport_error:
                message = unreachable_service_message(source)
                self.record_attempt(request, attempt_start, None, message)
                if is_last_attempt:
                    raise CollectionError(message, source, None) from transport_error
                self.wait_before_retry(attempt, None)
                attempt += 1
                continue
            if response.status_code in SUCCESSFUL_HTTP_STATUSES:
                return self.keep_response(request, attempt_start, response)
            retryable = is_retryable_status(response.status_code)
            message = (
                final_failure_message(source, response.status_code)
                if retryable
                else refused_request_message(source, response.status_code)
            )
            self.record_attempt(request, attempt_start, response.status_code, message)
            if not retryable or is_last_attempt:
                raise CollectionError(message, source, response.status_code)
            self.wait_before_retry(attempt, response.headers.get(RETRY_AFTER_HEADER))
            attempt += 1

    def keep_response(
        self, request: CollectorRequest, attempt_start: AttemptStart, response: httpx.Response
    ) -> StoredResponse:
        summary = self.response_store.save(
            CollectedResponse(
                request.source,
                request.url,
                response.content,
                attempt_start.requested_at,
                request.parameters,
            )
        )
        self.record_attempt(request, attempt_start, response.status_code, "", summary.identifier)
        logging.getLogger(COLLECTORS_LOGGER_NAME).info(
            "GET %s returned %d, fingerprint %s",
            request.url,
            response.status_code,
            summary.fingerprint,
        )
        return StoredResponse(summary, response.content)

    def record_attempt(
        self,
        request: CollectorRequest,
        attempt_start: AttemptStart,
        http_status: int | None,
        error: str,
        response_identifier: int | None = None,
    ) -> None:
        self.collection_log.record(
            LoggedRequest(
                requested_at=attempt_start.requested_at,
                source=request.source,
                endpoint=request.url,
                http_status=http_status,
                duration=self.elapsed_since(attempt_start),
                error=error,
                response_identifier=response_identifier,
            )
        )
        if error:
            logging.getLogger(COLLECTORS_LOGGER_NAME).warning(
                "GET %s failed with status %s", request.url, http_status
            )

    def elapsed_since(self, attempt_start: AttemptStart) -> timedelta:
        return timedelta(seconds=self.timing.monotonic() - attempt_start.monotonic_time)

    def wait_before_retry(self, failed_attempts: int, retry_after: str | None) -> None:
        delay = self.timing.retry_policy.delay_before_retry(
            failed_attempts, retry_after, self.timing.now()
        )
        self.timing.sleep(delay.total_seconds())
