import os
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lacis.storage.entities import CollectedEntity, mandate_link
from lacis.storage.errors import (
    InvalidInvestigationNameError,
    InvalidInvestigationQuestionError,
    InvestigationAlreadyExistsError,
    InvestigationNotFoundError,
    InvestigationNotTrashedError,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import (
    DATABASE_FILE_NAME,
    MAXIMUM_QUESTION_LENGTH,
    InvestigationLibrary,
    InvestigationSummary,
    question_problem,
)
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore

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


def test_an_empty_library_lists_nothing(library: InvestigationLibrary) -> None:
    assert library.names() == []


def test_investigations_are_listed_by_name(library: InvestigationLibrary) -> None:
    library.create("zeta", "")
    library.create("alpha", "")
    (library.root / "not-an-investigation").mkdir()
    assert library.names() == ["alpha", "zeta"]


def test_opening_an_investigation_gives_its_details_and_database(
    library: InvestigationLibrary,
) -> None:
    created = library.create("faux-plombiers-31", QUESTION)
    with library.open("faux-plombiers-31") as opened:
        assert opened.investigation == created
        assert opened.connection.execute("SELECT COUNT(*) FROM investigation").fetchone() == (1,)


def test_closing_an_investigation_closes_its_database(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers-31", QUESTION)
    opened = library.open("faux-plombiers-31")
    opened.close()
    with pytest.raises(sqlite3.ProgrammingError):
        opened.connection.execute("SELECT 1")


def test_opening_an_unreadable_investigation_closes_its_database(
    library: InvestigationLibrary,
) -> None:
    investigation = library.create("abimee", "")
    connection = sqlite3.connect(investigation.database_path)
    connection.execute("DROP TABLE investigation")
    connection.commit()
    connection.close()
    with pytest.raises(sqlite3.OperationalError):
        library.open("abimee")


def test_opening_a_missing_investigation_is_refused(library: InvestigationLibrary) -> None:
    with pytest.raises(InvestigationNotFoundError, match="« absente » est introuvable"):
        library.open("absente")


def test_renaming_moves_the_investigation_to_its_new_name(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers", QUESTION)
    library.rename("faux-plombiers", "faux-plombiers-31")
    assert library.names() == ["faux-plombiers-31"]
    with library.open("faux-plombiers-31") as opened:
        assert opened.investigation.question == QUESTION


def test_renaming_validates_the_new_name_and_keeps_it_unique(
    library: InvestigationLibrary,
) -> None:
    library.create("alpha", "")
    library.create("beta", "")
    with pytest.raises(InvalidInvestigationNameError):
        library.rename("alpha", "Alpha")
    with pytest.raises(InvestigationAlreadyExistsError):
        library.rename("alpha", "beta")
    with pytest.raises(InvestigationNotFoundError):
        library.rename("gamma", "delta")
    assert library.names() == ["alpha", "beta"]


def test_deleting_moves_the_investigation_to_the_trash(tmp_path: Path) -> None:
    trashed: list[Path] = []

    def move_to_trash(path: Path) -> bool:
        trashed.append(path)
        return True

    library = InvestigationLibrary(tmp_path / "investigations", move_to_trash)
    investigation = library.create("faux-plombiers-31", QUESTION)
    library.delete("faux-plombiers-31")
    assert trashed == [investigation.directory]


def test_a_failure_of_the_trash_is_reported(tmp_path: Path) -> None:
    library = InvestigationLibrary(tmp_path / "investigations", lambda path: False)
    library.create("faux-plombiers-31", QUESTION)
    with pytest.raises(InvestigationNotTrashedError, match="dans la corbeille"):
        library.delete("faux-plombiers-31")
    assert library.names() == ["faux-plombiers-31"]


def test_deleting_a_missing_investigation_is_refused(library: InvestigationLibrary) -> None:
    with pytest.raises(InvestigationNotFoundError):
        library.delete("absente")


@pytest.mark.skipif(sys.platform != "linux", reason="checks the freedesktop trash of Linux")
def test_the_default_trash_is_the_trash_of_the_system(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user_data_directory = tmp_path / "xdg"
    user_data_directory.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(user_data_directory))
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create("faux-plombiers-31", QUESTION)
    library.delete("faux-plombiers-31")
    assert library.names() == []
    trash_files = user_data_directory / "Trash" / "files"
    assert (trash_files / "faux-plombiers-31" / DATABASE_FILE_NAME).is_file()


def touch(library: InvestigationLibrary, name: str, modified_at: datetime) -> None:
    database_path = library.directory_of(name) / DATABASE_FILE_NAME
    os.utime(database_path, (modified_at.timestamp(), modified_at.timestamp()))


def test_a_summary_gives_the_question_counts_and_last_change(
    library: InvestigationLibrary,
) -> None:
    library.create("faux-plombiers-31", QUESTION)
    with library.open("faux-plombiers-31") as investigation:
        response = ResponseStore(investigation.connection).save(
            CollectedResponse(
                ResponseSource.COMPANY_REGISTER,
                "https://recherche-entreprises.api.gouv.fr/search",
                b"{}",
                datetime(2026, 11, 2, tzinfo=UTC),
            )
        )
        graph_store = GraphStore(investigation.connection)
        graph_store.save_entity(CollectedEntity("company:111111111", "ACME PLOMBERIE"), response)
        graph_store.save_entity(CollectedEntity("company:333333333", "HOLDING DUPONT"), response)
        graph_store.save_link(
            mandate_link("company:333333333", "company:111111111", "Président"), response
        )
    modified_at = datetime(2026, 11, 2, 9, 30, tzinfo=UTC)
    touch(library, "faux-plombiers-31", modified_at)
    assert library.summary("faux-plombiers-31") == InvestigationSummary(
        "faux-plombiers-31", QUESTION, 2, 1, modified_at
    )


def test_summaries_list_the_most_recently_changed_investigation_first(
    library: InvestigationLibrary,
) -> None:
    for name, day in (("fournisseur-acme", 28), ("serie-montpellier", 1), ("ancienne", 1)):
        library.create(name, "")
        month = 10 if day == 28 else 11
        touch(library, name, datetime(2026, month, day, tzinfo=UTC))
    assert [summary.name for summary in library.summaries()] == [
        "ancienne",
        "serie-montpellier",
        "fournisseur-acme",
    ]


def test_an_empty_library_has_no_summary(library: InvestigationLibrary) -> None:
    assert library.summaries() == []


def test_an_investigation_of_a_newer_version_is_summarised_with_its_problem(
    library: InvestigationLibrary,
) -> None:
    investigation = library.create("future", QUESTION)
    connection = sqlite3.connect(investigation.database_path)
    connection.execute("PRAGMA user_version = 999")
    connection.close()
    summary = library.summary("future")
    assert summary.problem.startswith("L'enquête « future » a été enregistrée")
    assert (summary.question, summary.entity_count, summary.link_count) == ("", 0, 0)


def test_an_unreadable_database_is_summarised_with_its_problem(
    library: InvestigationLibrary,
) -> None:
    investigation = library.create("abimee", QUESTION)
    investigation.database_path.write_bytes(b"pas une base SQLite")
    assert library.summary("abimee").problem == (
        "La base de données de cette enquête est illisible."
    )


def test_a_free_and_valid_name_has_no_problem(library: InvestigationLibrary) -> None:
    assert library.name_problem("faux-plombiers-31") == ""


def test_a_name_problem_explains_what_is_wrong(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers-31", QUESTION)
    assert library.name_problem("") == "Le nom de l'enquête est obligatoire."
    assert library.name_problem("Faux Plombiers").startswith(
        "Le nom de l'enquête ne peut contenir que"
    )
    assert library.name_problem("faux-plombiers-31") == (
        "Une enquête nommée « faux-plombiers-31 » existe déjà."
    )


def test_the_current_name_of_an_investigation_has_no_problem(
    library: InvestigationLibrary,
) -> None:
    library.create("faux-plombiers-31", QUESTION)
    assert library.name_problem("faux-plombiers-31", "faux-plombiers-31") == ""
    assert library.name_problem("", "faux-plombiers-31") == "Le nom de l'enquête est obligatoire."


def test_a_question_problem_explains_what_is_wrong() -> None:
    assert question_problem(QUESTION) == ""
    assert question_problem("") == ""
    assert question_problem("?" * (MAXIMUM_QUESTION_LENGTH + 1)) == (
        f"La question de départ ne doit pas dépasser {MAXIMUM_QUESTION_LENGTH} caractères."
    )


def test_changing_the_question_stores_it_cleaned(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers-31", QUESTION)
    library.change_question("faux-plombiers-31", "  Qui gère   ces sociétés ?  ")
    with library.open("faux-plombiers-31") as opened:
        assert opened.investigation.question == "Qui gère ces sociétés ?"


def test_a_too_long_new_question_changes_nothing(library: InvestigationLibrary) -> None:
    library.create("faux-plombiers-31", QUESTION)
    with pytest.raises(InvalidInvestigationQuestionError):
        library.change_question("faux-plombiers-31", "?" * (MAXIMUM_QUESTION_LENGTH + 1))
    with library.open("faux-plombiers-31") as opened:
        assert opened.investigation.question == QUESTION


def test_changing_the_question_of_a_missing_investigation_is_refused(
    library: InvestigationLibrary,
) -> None:
    with pytest.raises(InvestigationNotFoundError):
        library.change_question("absente", QUESTION)
