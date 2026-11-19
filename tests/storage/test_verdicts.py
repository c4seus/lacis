import sqlite3
from datetime import UTC, datetime

import pytest

from investigation_builder import InvestigationBuilder
from lacis.storage.graph_store import GraphStore
from lacis.storage.verdicts import EntityVerdict, Verdict, VerdictStore

FIRST_MOMENT = datetime(2026, 11, 19, 9, 30, tzinfo=UTC)
SECOND_MOMENT = datetime(2026, 11, 20, 14, 5, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.moment = FIRST_MOMENT

    def __call__(self) -> datetime:
        return self.moment


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def store(builder: InvestigationBuilder, clock: Clock) -> VerdictStore:
    return VerdictStore(builder.connection, clock)


def test_the_verdicts_have_their_labels() -> None:
    assert [verdict.label for verdict in Verdict] == [
        "À vérifier",
        "Suspect",
        "Écarté",
        "Confirmé",
    ]


def test_an_entity_has_no_verdict_at_first(
    builder: InvestigationBuilder, store: VerdictStore
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    assert store.verdict(acme) is None
    assert store.verdicts() == {}


@pytest.mark.parametrize("verdict", list(Verdict))
def test_every_verdict_is_kept_with_its_reason(
    builder: InvestigationBuilder, store: VerdictStore, verdict: Verdict
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    saved = store.save(acme, verdict, "  Même gérant que DUPONT SERVICES. ")
    assert saved == EntityVerdict(verdict, "Même gérant que DUPONT SERVICES.", FIRST_MOMENT)
    assert store.verdict(acme) == saved
    assert store.verdicts() == {acme: verdict}


def test_a_changed_verdict_takes_a_new_date(
    builder: InvestigationBuilder, store: VerdictStore, clock: Clock
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    store.save(acme, Verdict.TO_CHECK, "")
    clock.moment = SECOND_MOMENT
    assert store.save(acme, Verdict.TO_CHECK, "") == EntityVerdict(
        Verdict.TO_CHECK, "", FIRST_MOMENT
    )
    assert store.save(acme, Verdict.SUSPECT, "") == EntityVerdict(
        Verdict.SUSPECT, "", SECOND_MOMENT
    )


def test_a_verdict_is_withdrawn(builder: InvestigationBuilder, store: VerdictStore) -> None:
    acme = builder.company("ACME PLOMBERIE")
    store.save(acme, Verdict.CONFIRMED, "")
    assert store.save(acme, None, "") is None
    assert store.verdict(acme) is None


def test_a_verdict_never_changes_the_collected_facts(
    builder: InvestigationBuilder, store: VerdictStore
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    graph_store = GraphStore(builder.connection)
    before = graph_store.entity(acme)
    store.save(acme, Verdict.DISMISSED, "Homonyme sans lien.")
    assert graph_store.entity(acme) == before


def test_a_verdict_needs_its_entity(store: VerdictStore) -> None:
    with pytest.raises(sqlite3.IntegrityError):
        store.save("company:100000000", Verdict.SUSPECT, "")
