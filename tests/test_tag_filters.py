import sqlite3

import pytest

from investigation_builder import InvestigationBuilder
from lacis.graph.drawing import GraphDrawing, GraphNode, graph_drawing
from lacis.graph.filters import GraphFilter
from lacis.identity.homonyms import Confidence
from lacis.review import HomonymEntry, QueueEntity, ReviewQueue, SignalGroup
from lacis.storage.entities import EntityKind
from lacis.storage.tags import TagStore
from lacis.tables import entity_rows


def entity(identifier: str) -> QueueEntity:
    return QueueEntity(identifier, EntityKind.COMPANY, identifier, "")


def node(identifier: str, tags: frozenset[str] = frozenset()) -> GraphNode:
    return GraphNode(identifier, EntityKind.COMPANY, identifier, False, False, 0, 0, tags=tags)


def test_a_tag_filter_shows_only_the_tagged_entities() -> None:
    drawing = GraphDrawing((node("a", frozenset({"client"})), node("b")))
    graph_filter = GraphFilter().showing_tag("client")
    assert graph_filter.is_active
    assert graph_filter.shown_identifiers(drawing) == {"a"}
    assert graph_filter.summary(drawing) == "1 entité masquée"
    assert not graph_filter.showing_tag(None).is_active


def test_the_queue_keeps_the_entries_of_the_tagged_entities() -> None:
    queue = ReviewQueue(
        (
            SignalGroup("phoenix", "Schéma phénix", (entity("a"), entity("b"))),
            SignalGroup("domiciliation", "Domiciliation", (entity("b"),)),
        ),
        (
            HomonymEntry(entity("c"), entity("a"), Confidence.PROBABLE, ()),
            HomonymEntry(entity("b"), entity("d"), Confidence.PROBABLE, ()),
        ),
        (entity("a"), entity("b")),
    )
    kept = queue.keeping(frozenset({"a"}))
    assert [group.title for group in kept.signal_groups] == ["Schéma phénix"]
    assert kept.signal_groups[0].entities == (entity("a"),)
    assert [entry.first.identifier for entry in kept.homonyms] == ["c"]
    assert kept.leads == (entity("a"),)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


def test_the_drawing_and_the_table_know_the_tags_of_each_entity(
    builder: InvestigationBuilder,
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    dupont = builder.company("DUPONT SERVICES", identifier="company:222222222")
    TagStore(builder.connection).add(acme, "Client")
    drawing = graph_drawing(builder.connection)
    assert drawing.require_node(acme).tags == frozenset({"client"})
    assert drawing.require_node(dupont).tags == frozenset()
    rows = {row.identifier: row.tags for row in entity_rows(builder.connection, None)}
    assert rows == {acme: frozenset({"client"}), dupont: frozenset()}
