import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ResponseSource(StrEnum):
    COMPANY_REGISTER = "company_register"
    BODACC = "bodacc"


RESPONSE_SUMMARY_COLUMNS = "identifier, source, url, parameters, collected_at, fingerprint"


def fingerprint(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def encode_parameters(parameters: dict[str, str]) -> str:
    return json.dumps(parameters, ensure_ascii=False, sort_keys=True)


@dataclass(frozen=True)
class CollectedResponse:
    source: ResponseSource
    url: str
    body: bytes
    collected_at: datetime
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ResponseSummary:
    identifier: int
    source: ResponseSource
    url: str
    parameters: dict[str, str]
    collected_at: datetime
    fingerprint: str


@dataclass(frozen=True)
class StoredResponse:
    summary: ResponseSummary
    body: bytes


def summary_from_row(row: tuple[int, str, str, str, str, str]) -> ResponseSummary:
    identifier, source, url, parameters, collected_at, stored_fingerprint = row
    return ResponseSummary(
        identifier=identifier,
        source=ResponseSource(source),
        url=url,
        parameters=json.loads(parameters),
        collected_at=datetime.fromisoformat(collected_at),
        fingerprint=stored_fingerprint,
    )


class ResponseStore:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, collected_response: CollectedResponse) -> ResponseSummary:
        with self.connection:
            (identifier,) = self.connection.execute(
                """
                INSERT INTO response (source, url, parameters, collected_at, fingerprint, body)
                VALUES (?, ?, ?, ?, ?, ?)
                RETURNING identifier
                """,
                (
                    collected_response.source.value,
                    collected_response.url,
                    encode_parameters(collected_response.parameters),
                    collected_response.collected_at.isoformat(),
                    fingerprint(collected_response.body),
                    collected_response.body,
                ),
            ).fetchone()
        return self.summary(identifier)

    def summary(self, identifier: int) -> ResponseSummary:
        row = self.connection.execute(
            f"SELECT {RESPONSE_SUMMARY_COLUMNS} FROM response WHERE identifier = ?",
            (identifier,),
        ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return summary_from_row(row)

    def read(self, identifier: int) -> StoredResponse:
        summary = self.summary(identifier)
        (body,) = self.connection.execute(
            "SELECT body FROM response WHERE identifier = ?", (identifier,)
        ).fetchone()
        return StoredResponse(summary, bytes(body))

    def summaries(self) -> list[ResponseSummary]:
        rows = self.connection.execute(
            f"SELECT {RESPONSE_SUMMARY_COLUMNS} FROM response ORDER BY collected_at, identifier"
        ).fetchall()
        return [summary_from_row(row) for row in rows]
