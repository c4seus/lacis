import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Self

from PySide6.QtCore import QFile

from lacis.storage.errors import (
    InvalidInvestigationQuestionError,
    InvestigationAlreadyExistsError,
    InvestigationNotFoundError,
    InvestigationNotTrashedError,
    NewerInvestigationError,
)
from lacis.storage.names import validate_investigation_name
from lacis.storage.schema import MIGRATIONS, Migration, NewerSchemaError, migrate

DATABASE_FILE_NAME = "investigation.sqlite3"
MAXIMUM_QUESTION_LENGTH = 500
TOO_LONG_QUESTION_MESSAGE = (
    f"La question de départ ne doit pas dépasser {MAXIMUM_QUESTION_LENGTH} caractères."
)


@dataclass(frozen=True)
class Investigation:
    name: str
    question: str
    created_at: datetime
    directory: Path

    @property
    def database_path(self) -> Path:
        return self.directory / DATABASE_FILE_NAME


class OpenInvestigation:
    def __init__(self, investigation: Investigation, connection: sqlite3.Connection) -> None:
        self.investigation = investigation
        self.connection = connection

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


def move_to_system_trash(path: Path) -> bool:
    return bool(QFile.moveToTrash(str(path)))


def current_time() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def validate_question(question: str) -> str:
    cleaned_question = " ".join(question.split())
    if len(cleaned_question) > MAXIMUM_QUESTION_LENGTH:
        raise InvalidInvestigationQuestionError(TOO_LONG_QUESTION_MESSAGE)
    return cleaned_question


def connect(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, autocommit=True)
    connection.execute("PRAGMA foreign_keys = ON")
    connection.autocommit = False
    return connection


class InvestigationLibrary:
    def __init__(
        self,
        root: Path,
        move_to_trash: Callable[[Path], bool] = move_to_system_trash,
        migrations: Sequence[Migration] = MIGRATIONS,
    ) -> None:
        self.root = root
        self.move_to_trash = move_to_trash
        self.migrations = migrations

    def directory_of(self, name: str) -> Path:
        return self.root / name

    def existing_directory_of(self, name: str) -> Path:
        directory = self.directory_of(name)
        if not (directory / DATABASE_FILE_NAME).is_file():
            raise InvestigationNotFoundError(name)
        return directory

    def names(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(
            directory.name
            for directory in self.root.iterdir()
            if (directory / DATABASE_FILE_NAME).is_file()
        )

    def open(self, name: str) -> OpenInvestigation:
        directory = self.existing_directory_of(name)
        connection = connect(directory / DATABASE_FILE_NAME)
        try:
            migrate(connection, self.migrations)
            question, created_at = connection.execute(
                "SELECT question, created_at FROM investigation"
            ).fetchone()
        except NewerSchemaError as newer_schema:
            connection.close()
            raise NewerInvestigationError(
                name, newer_schema.version, newer_schema.supported_version
            ) from newer_schema
        except BaseException:
            connection.close()
            raise
        investigation = Investigation(
            name, question, datetime.fromisoformat(created_at), directory
        )
        return OpenInvestigation(investigation, connection)

    def rename(self, name: str, new_name: str) -> None:
        directory = self.existing_directory_of(name)
        validated_new_name = validate_investigation_name(new_name)
        new_directory = self.directory_of(validated_new_name)
        if new_directory.exists():
            raise InvestigationAlreadyExistsError(validated_new_name)
        directory.rename(new_directory)

    def delete(self, name: str) -> None:
        directory = self.existing_directory_of(name)
        if not self.move_to_trash(directory):
            raise InvestigationNotTrashedError(name)

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
            migrate(connection, self.migrations)
            with connection:
                connection.execute(
                    "INSERT INTO investigation (question, created_at) VALUES (?, ?)",
                    (validated_question, created_at.isoformat()),
                )
        finally:
            connection.close()
        return investigation
