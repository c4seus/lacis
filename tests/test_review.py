import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis.graph.expansion import ExpansionReport, GraphChanges
from lacis.graph.leads import Lead
from lacis.identity.homonyms import Confidence
from lacis.overview import InvestigationOverview, overview_of
from lacis.review import (
    QueueEntity,
    ReviewQueue,
    expansion_message,
    notices_message,
    review_queue,
)
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.entities import EntityKind


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    return plumbers_scenario(builder)


def overview_with(
    builder: InvestigationBuilder, report: SignalReport | None
) -> InvestigationOverview:
    overview = overview_of(builder.connection, None)
    return replace(overview, report=report)


def report_of(*signals: Signal) -> SignalReport:
    return SignalReport(signals, 1, date(2026, 11, 12), "", datetime(2026, 11, 12, tzinfo=UTC))


def signal(rule: str, title: str, subject: str, severity: Severity, score: float) -> Signal:
    return Signal(rule, title, subject, severity, score, f"Explication {rule}", ())


def test_signals_are_grouped_by_rule_with_their_entities_and_scores(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    queue = review_queue(overview_with(builder, phoenix_report(scenario)))
    [group] = queue.signal_groups
    assert group.title == "Schéma phénix · forte"
    assert [entity.label for entity in group.entities] == [
        "DUPONT SERVICES",
        "ACME PLOMBERIE",
        "Jean DUPONT (1980-05)",
        "Jean Pierre DUPONT (1980-05)",
    ]
    subject, evidence = group.entities[0], group.entities[1]
    assert (subject.kind, subject.explanation, subject.written_score) == (
        EntityKind.COMPANY,
        "",
        "0,85",
    )
    assert evidence.explanation == "Indice du signal sur DUPONT SERVICES"


def test_groups_start_with_the_strongest_rule_and_list_each_entity_once(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    report = report_of(
        signal("creation_burst", "Rafale de créations", scenario.jean, Severity.MEDIUM, 0.6),
        signal("mass_domiciliation", "Domiciliation", scenario.address, Severity.LOW, 0.9),
        signal("creation_burst", "Rafale de créations", scenario.jean, Severity.HIGH, 0.7),
        replace(
            signal("creation_burst", "Rafale de créations", scenario.acme, Severity.LOW, 0.5),
            justifying_entities=(scenario.jean,),
        ),
    )
    queue = review_queue(overview_with(builder, report))
    assert [group.title for group in queue.signal_groups] == [
        "Rafale de créations · forte",
        "Domiciliation · faible",
    ]
    burst = queue.signal_groups[0]
    assert [(entity.identifier, entity.score) for entity in burst.entities] == [
        (scenario.jean, 0.7),
        (scenario.acme, 0.5),
    ]


def test_homonyms_to_verify_come_with_their_confidence_and_reasons(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    marie = builder.person("Marie", "DUPONT")
    marie_claire = builder.person("Marie Claire", "DUPONT")
    queue = review_queue(overview_with(builder, None))
    [entry] = queue.homonyms
    assert {entry.first.identifier, entry.second.identifier} == {marie, marie_claire}
    assert entry.title in {
        "Marie DUPONT (1980-05) ↔ Marie Claire DUPONT (1980-05)",
        "Marie Claire DUPONT (1980-05) ↔ Marie DUPONT (1980-05)",
    }
    assert entry.confidence is Confidence.PROBABLE
    assert entry.confidence_label == "Probable"
    assert entry.reasons[0] == "Même nom de famille"
    assert entry.first.explanation == " · ".join(entry.reasons)


def test_leads_come_with_their_reason(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    queue = review_queue(overview_with(builder, None))
    holding = next(lead for lead in queue.leads if lead.identifier == scenario.holding)
    assert (holding.label, holding.explanation) == (
        "HOLDING DUPONT",
        "Connue comme dirigeante seulement",
    )
    assert queue.signal_groups == ()
    assert queue.entity_identifiers()[-len(queue.leads) :] == [
        lead.identifier for lead in queue.leads
    ]


def test_a_signal_problem_is_kept_for_the_queue(builder: InvestigationBuilder) -> None:
    overview = replace(overview_of(builder.connection, None), signal_problem="Fichier invalide")
    assert review_queue(overview).signal_problem == "Fichier invalide"


def test_entities_missing_from_the_drawing_keep_their_own_label() -> None:
    overview = InvestigationOverview(
        1,
        0,
        0,
        None,
        unexpanded=(Lead("company:100000000", EntityKind.COMPANY, "ACME", "Raison"),),
    )
    [lead] = review_queue(overview).leads
    assert (lead.kind, lead.label) == (EntityKind.COMPANY, "ACME")
    assert (
        review_queue(
            replace(
                overview,
                report=report_of(
                    signal("phoenix_scheme", "Schéma phénix", "person:abc", Severity.LOW, 0.4)
                ),
            )
        )
        .signal_groups[0]
        .entities[0]
        .label
        == "person:abc"
    )


def test_the_queue_lists_the_entities_in_order() -> None:
    entity = QueueEntity("company:1", EntityKind.COMPANY, "ACME", "", None)
    assert entity.written_score == ""
    assert ReviewQueue((), (), (entity,)).entity_identifiers() == ["company:1"]


def test_an_expansion_message_tells_what_was_found() -> None:
    found = ExpansionReport(GraphChanges(new_entities=("company:1", "person:1")))
    assert expansion_message("HOLDING DUPONT", found) == (
        "Extension de HOLDING DUPONT terminée : 2 entités ajoutées"
    )
    assert expansion_message("HOLDING DUPONT", ExpansionReport(GraphChanges())) == (
        "Extension de HOLDING DUPONT terminée : rien de nouveau"
    )
    troubled = ExpansionReport(
        GraphChanges(new_entities=("company:1",)), failures=("BODACC",), cap=500
    )
    message = expansion_message("HOLDING DUPONT", troubled)
    assert message.startswith("Extension de HOLDING DUPONT terminée : 1 entité ajoutée. ")
    assert troubled.cap_message in message
    assert message.endswith("(1 source en échec)")


def test_a_notices_message_tells_what_changed() -> None:
    changed = ExpansionReport(GraphChanges(new_notices=("A1", "A2"), withdrawn_notices=("A3",)))
    assert notices_message("ACME", changed) == (
        "Annonces de ACME rafraîchies : 2 nouvelles annonces, 1 annonce retirée"
    )
    assert notices_message("ACME", ExpansionReport(GraphChanges(new_notices=("A1",)))) == (
        "Annonces de ACME rafraîchies : 1 nouvelle annonce"
    )
    assert notices_message("ACME", ExpansionReport(GraphChanges())) == (
        "Annonces de ACME rafraîchies : rien de nouveau"
    )
