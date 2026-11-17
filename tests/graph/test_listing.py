import sqlite3

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.drawing import GraphDrawing, graph_drawing
from lacis.graph.filters import GraphFilter
from lacis.graph.listing import ListedEntity, ListedKind, graph_listing, sortable
from lacis.storage.entities import EntityKind


@pytest.fixture
def scenario(investigation_connection: sqlite3.Connection) -> PlumbersScenario:
    return plumbers_scenario(InvestigationBuilder(investigation_connection))


@pytest.fixture
def drawing(
    investigation_connection: sqlite3.Connection, scenario: PlumbersScenario
) -> GraphDrawing:
    return graph_drawing(investigation_connection, phoenix_report(scenario))


def entity_in(listing: tuple[ListedKind, ...], identifier: str) -> ListedEntity:
    return next(
        entity
        for listed_kind in listing
        for entity in listed_kind.entities
        if entity.identifier == identifier
    )


def test_the_entities_are_grouped_by_kind_in_the_order_of_the_filters(
    drawing: GraphDrawing,
) -> None:
    listing = graph_listing(drawing, GraphFilter())
    assert [listed_kind.title for listed_kind in listing] == [
        "Entreprises (3)",
        "Personnes (2)",
        "Adresses (1)",
        "Établissements (2)",
        "Entreprises étrangères (1)",
    ]
    assert listing[0].summary == "Entreprises, 3 entités"
    assert listing[2].summary == "Adresses, 1 entité"


def test_every_entity_is_listed_once_by_name_with_its_spoken_summary(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    listing = graph_listing(drawing, GraphFilter())
    listed = [entity.identifier for listed_kind in listing for entity in listed_kind.entities]
    assert sorted(listed) == sorted(node.identifier for node in drawing.nodes)
    assert [entity.label for entity in listing[1].entities] == [
        "Jean DUPONT (1980-05)",
        "Jean Pierre DUPONT (1980-05)",
    ]
    assert entity_in(listing, scenario.dupont_services).summary == (
        "DUPONT SERVICES, entreprise, fermée, 2 liens, signal de sévérité forte"
    )


def test_each_entity_lists_its_links_with_the_entity_they_lead_to(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    acme = entity_in(graph_listing(drawing, GraphFilter()), scenario.acme)
    assert [(link.description, link.target) for link in acme.links] == [
        ("Associé : DUPONT INVEST LTD", scenario.invest),
        ("Directeur général : HOLDING DUPONT", scenario.holding),
        ("établissement Siège — TOULOUSE", scenario.acme_office),
        ("Président : Jean Pierre DUPONT (1980-05)", scenario.jean_pierre),
    ]
    assert [link.target_kind for link in acme.links] == [
        EntityKind.FOREIGN_COMPANY,
        EntityKind.COMPANY,
        EntityKind.ESTABLISHMENT,
        EntityKind.PERSON,
    ]
    every_link = [
        link.identifier
        for listed_kind in graph_listing(drawing, GraphFilter())
        for entity in listed_kind.entities
        for link in entity.links
    ]
    assert sorted(set(every_link)) == sorted(edge.identifier for edge in drawing.edges)


def test_the_filters_hide_the_entities_and_the_links_that_lead_to_them(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    graph_filter = GraphFilter().showing_kind(EntityKind.ESTABLISHMENT, False)
    listing = graph_listing(drawing, graph_filter)
    assert "Établissements (2)" not in [listed_kind.title for listed_kind in listing]
    acme = entity_in(listing, scenario.acme)
    assert acme.summary == "ACME PLOMBERIE, entreprise, 3 liens, signal de sévérité forte"
    assert scenario.acme_office not in [link.target for link in acme.links]


def test_only_flagged_entities_can_be_listed(
    drawing: GraphDrawing, scenario: PlumbersScenario
) -> None:
    listing = graph_listing(drawing, GraphFilter(flagged_only=True))
    assert [listed_kind.title for listed_kind in listing] == ["Entreprises (2)", "Personnes (2)"]
    jean = entity_in(listing, scenario.jean)
    assert [link.target for link in jean.links] == [scenario.jean_pierre, scenario.dupont_services]


def test_an_empty_graph_lists_nothing() -> None:
    assert graph_listing(GraphDrawing(), GraphFilter()) == ()


def test_names_are_sorted_without_case_or_accents() -> None:
    assert sorted(["Zoé", "émile", "Eric"], key=sortable) == ["émile", "Eric", "Zoé"]
