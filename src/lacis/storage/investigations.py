import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from lacis.storage.errors import (
    InvalidInvestigationQuestionError,
    InvestigationAlreadyExistsError,
)
from lacis.storage.names import validate_investigation_name

DATABASE_FILE_NAME = "investigation.sqlite3"
MAXIMUM_QUESTION_LENGTH = 500
TOO_LONG_QUESTION_MESSAGE = (
    f"La question de départ ne doit pas dépasser {MAXIMUM_QUESTION_LENGTH} caractères."
)
INVESTIGATION_TABLE_SCHEMA = """
CREATE TABLE investigation (
    question TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Investigation:
    name: str
    question: str
    created_at: datetime
    directory: Path

    @property
    def database_path(self) -> Path:
        return self.directory / DATABASE_FILE_NAME


def current_time() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def validate_question(question: str) -> str:
    cleaned_question = " ".join(question.split())
    if len(cleaned_question) > MAXIMUM_QUESTION_LENGTH:
        raise InvalidInvestigationQuestionError(TOO_LONG_QUESTION_MESSAGE)
    return cleaned_question


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class InvestigationLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root

    def directory_of(self, name: str) -> Path:
        return self.root / name

    def create(self, name: str, question: str) -> Investigation:
        validated_name = validate_investigation_name(name)
        validated_question = validate_question(question)
        directory = self.directory_of(validated_name)
        if directory.exists():
            raise InvestigationAlreadyExistsError(validated_name)
        directory.mkdir(parents=True)
        created_at = current_time()
        investigation = Investigation(validated_name, validated_question, created_at, directory)
        connection = connect(investigation.database_path)
        try:
            with connection:
                connection.execute(INVESTIGATION_TABLE_SCHEMA)
                connection.execute(
                    "INSERT INTO investigation (question, created_at) VALUES (?, ?)",
                    (validated_question, created_at.isoformat()),
                )
        finally:
            connection.close()
        return investigation
