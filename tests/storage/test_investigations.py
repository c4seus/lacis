import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.errors import (
    InvalidInvestigationNameError,
    InvalidInvestigationQuestionError,
    InvestigationAlreadyExistsError,
)
from lacis.storage.investigations import (
    DATABASE_FILE_NAME,
    MAXIMUM_QUESTION_LENGTH,
    InvestigationLibrary,
)

QUESTION = "Qui se cache derrière les plombiers du 12 rue des Lilas ?"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    return InvestigationLibrary(tmp_path / "investigations")


def test_creating_an_investigation_creates_its_folder_and_database(
    library: InvestigationLibrary,
) -> None:
    investigation = library.create("faux-plombiers-31", QUESTION)
    assert investigation.name == "faux-plombiers-31"
    assert investigation.directory == library.root / "faux-plombiers-31"
    assert investigation.database_path == investigation.directory / DATABASE_FILE_NAME
    assert investigation.database_path.is_file()


def test_the_question_and_creation_date_are_stored_in_the_database(
    library: InvestigationLibrary,
) -> None:
    investigation = library.create("faux-plombiers-31", QUESTION)
    connection = sqlite3.connect(investigation.database_path)
    try:
        stored = connection.execute("SELECT question, created_at FROM investigation").fetchall()
    finally:
        connection.close()
    assert stored == [(QUESTION, investigation.created_at.isoformat())]
    assert investigation.created_at.tzinfo == UTC
    assert abs((datetime.now(UTC) - investigation.created_at).total_seconds()) < 60


def test_the_question_is_cleaned_of_extra_spaces(library: InvestigationLibrary) -> None:
    investigation = library.create("faux-plombiers-31", "  Qui   se cache\n derrière ?  ")
    assert investigation.question == "Qui se cache derrière ?"


def test_the_question_may_be_left_empty(library: InvestigationLibrary) -> None:
    assert library.create("vide", "").question == ""


def test_a_too_long_question_is_refused(library: InvestigationLibrary) -> None:
    with pytest.raises(InvalidInvestigationQuestionError, match="500 caractères"):
        library.create("bavard", "x" * (MAXIMUM_QUESTION_LENGTH + 1))
    assert not (library.root / "bavard").exists()


def test_an_invalid_name_creates_nothing(library: InvestigationLibrary) -> None:
    with pytest.raises(InvalidInvestigationNameError):
        library.create("Faux Plombiers", QUESTION)
    assert not library.root.exists() or not any(library.root.iterdir())


def test_two_investigations_cannot_share_a_name(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers-31", QUESTION)
    with pytest.raises(InvestigationAlreadyExistsError, match="« faux-plombiers-31 » existe déjà"):
        library.create("faux-plombiers-31", "Une autre question")
