import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta

from lacis.storage.responses import ResponseSource

COLLECTION_LOG_COLUMNS = (
    "identifier, requested_at, source, endpoint, http_status, duration_milliseconds, "
    "served_from_cache, error, response_identifier"
)
MILLISECOND = timedelta(milliseconds=1)


@dataclass(frozen=True)
class LoggedRequest:
    requested_at: datetime
    source: ResponseSource
    endpoint: str
    http_status: int | None
    duration: timedelta
    served_from_cache: bool = False
    error: str = ""
    response_identifier: int | None = None


@dataclass(frozen=True)
class CollectionLogEntry:
    identifier: int
    request: LoggedRequest


def entry_from_row(
    row: tuple[int, str, str, str, int | None, int, int, str, int | None],
) -> CollectionLogEntry:
    (
        identifier,
        requested_at,
        source,
        endpoint,
        http_status,
        duration_milliseconds,
        served_from_cache,
        error,
        response_identifier,
    ) = row
    return CollectionLogEntry(
        identifier,
        LoggedRequest(
            requested_at=datetime.fromisoformat(requested_at),
            source=ResponseSource(source),
            endpoint=endpoint,
            http_status=http_status,
            duration=duration_milliseconds * MILLISECOND,
            served_from_cache=bool(served_from_cache),
            error=error,
            response_identifier=response_identifier,
        ),
    )


class CollectionLog:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def record(self, request: LoggedRequest) -> CollectionLogEntry:
        with self.connection:
            (identifier,) = self.connection.execute(
                """
                INSERT INTO collection_log (
                    requested_at, source, endpoint, http_status, duration_milliseconds,
                    served_from_cache, error, response_identifier
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING identifier
                """,
                (
                    request.requested_at.isoformat(),
                    request.source.value,
                    request.endpoint,
                    request.http_status,
                    round(request.duration / MILLISECOND),
                    request.served_from_cache,
                    request.error,
                    request.response_identifier,
                ),
            ).fetchone()
        return self.entry(identifier)

    def entry(self, identifier: int) -> CollectionLogEntry:
        row = self.connection.execute(
            f"SELECT {COLLECTION_LOG_COLUMNS} FROM collection_log WHERE identifier = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return entry_from_row(row)
