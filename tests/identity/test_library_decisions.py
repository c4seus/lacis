from pathlib import Path

import pytest

from investigation_builder import InvestigationBuilder
from lacis.identity.library_decisions import LibraryDecisionStore
from lacis.storage.entities import LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionNotFoundError
from lacis.storage.investigations import InvestigationLibrary

INVESTIGATION_NAME = "faux-plombiers-31"


@pytest.fixture
def library(tmp_path: Path) -> InvestigationLibrary:
    library = InvestigationLibrary(tmp_path / "investigations")
    library.create(INVESTIGATION_NAME, "")
    return library


@pytest.fixture
def people(library: InvestigationLibrary) -> tuple[str, str]:
    with library.open(INVESTIGATION_NAME) as opened:
        builder = InvestigationBuilder(opened.connection)
        return builder.person("Jean", "DUPONT"), builder.person("Jean Pierre", "DUPONT")


def same_person_links(library: InvestigationLibrary) -> int:
    with library.open(INVESTIGATION_NAME) as opened:
        links = GraphStore(opened.connection).links()
    return sum(1 for link in links if link.kind is LinkKind.SAME_PERSON)


def test_decisions_are_saved_in_the_investigation_each_time(
    library: InvestigationLibrary, people: tuple[str, str]
) -> None:
    store = LibraryDecisionStore(library, INVESTIGATION_NAME)
    assert store.decision_between(*people) is None
    recorded = store.record(*people, HomonymDecision.SAME_PERSON)
    assert store.decision_between(*people) == recorded
    assert same_person_links(library) == 1
    assert store.withdraw(*people) == recorded
    assert store.decision_between(*people) is None
    assert same_person_links(library) == 0
    assert store.restore(recorded) == recorded
    assert same_person_links(library) == 1


def test_withdrawing_a_missing_decision_fails(
    library: InvestigationLibrary, people: tuple[str, str]
) -> None:
    with pytest.raises(HomonymDecisionNotFoundError):
        LibraryDecisionStore(library, INVESTIGATION_NAME).withdraw(*people)
