from dataclasses import dataclass
from datetime import timedelta

import httpx

from lacis import __version__
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
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.client = httpx.Client(
            transport=transport,
            timeout=REQUEST_TIMEOUT.total_seconds(),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            follow_redirects=True,
        )

    def close(self) -> None:
        self.client.close()

    def get(self, source: ResponseSource, url: str, parameters: dict[str, str]) -> FetchedResponse:
        try:
            response = self.client.get(url, params=parameters)
        except httpx.TransportError as transport_error:
            raise CollectionError(
                unreachable_service_message(source), source, None
            ) from transport_error
        if response.status_code not in SUCCESSFUL_HTTP_STATUSES:
            raise CollectionError(
                refused_request_message(source, response.status_code),
                source,
                response.status_code,
            )
        return FetchedResponse(source, url, parameters, response.status_code, response.content)
