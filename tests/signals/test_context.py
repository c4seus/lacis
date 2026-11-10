import sqlite3
from datetime import date

import pytest

from lacis.signals.context import InvestigationContext
from lacis.storage.entities import EntityKind, LinkKind
from lacis.storage.notices import NoticeFamily
from signal_rules import (
    ACME,
    DUPONT_SERVICES,
    JEAN_DUPONT,
    LILAS_ADDRESS,
    LILAS_BOULANGERIE,
    fill_small_investigation,
)

TODAY = date(2026, 11, 10)


@pytest.fixture
def context(investigation_connection: sqlite3.Connection) -> InvestigationContext:
    fill_small_investigation(investigation_connection)
    return InvestigationContext(investigation_connection, TODAY)


def test_the_context_gives_the_day_of_the_computation(context: InvestigationContext) -> None:
    assert context.today == TODAY


def test_the_context_gives_entities_by_identifier_and_kind(
    context: InvestigationContext,
) -> None:
    acme = context.entity(ACME)
    assert acme is not None
    assert acme.label == "ACME PLOMBERIE"
    assert context.entity("company:999999999") is None
    assert {entity.identifier for entity in context.entities_of(EntityKind.COMPANY)} == {
        ACME,
        DUPONT_SERVICES,
        LILAS_BOULANGERIE,
    }


def test_the_context_gives_the_links_of_an_entity(context: InvestigationContext) -> None:
    assert len(context.links) == 4
    assert {link.kind for link in context.links_of(ACME)} == {
        LinkKind.MANDATE,
        LinkKind.REGISTERED_OFFICE,
    }
    assert {link.target for link in context.links_of(JEAN_DUPONT, LinkKind.MANDATE)} == {
        ACME,
        DUPONT_SERVICES,
    }
    assert context.links_of(LILAS_BOULANGERIE) == []


def test_the_context_gives_the_neighbours_of_an_entity(context: InvestigationContext) -> None:
    assert {entity.identifier for entity in context.neighbours(LILAS_ADDRESS)} == {
        ACME,
        DUPONT_SERVICES,
    }
    assert [
        entity.identifier
        for entity in context.neighbours(ACME, LinkKind.MANDATE, EntityKind.PERSON)
    ] == [JEAN_DUPONT]
    assert context.neighbours(ACME, LinkKind.MANDATE, EntityKind.ADDRESS) == []


def test_the_context_gives_the_notices_of_a_company(context: InvestigationContext) -> None:
    notices = context.notices_of(DUPONT_SERVICES)
    assert [notice.notice.identifier for notice in notices[NoticeFamily.REMOVAL]] == [
        "B202300150001"
    ]
    assert context.notices_of(ACME) == {}


def test_the_context_computes_each_kind_of_identities_once(
    context: InvestigationContext,
) -> None:
    confirmed = context.identities(include_probable=False)
    assert context.identities(include_probable=False) is confirmed
    assert context.identities(include_probable=True) is not confirmed
