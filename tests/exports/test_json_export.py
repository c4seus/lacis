import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis import __version__
from lacis.exports.json_export import (
    SCHEMA_URL,
    ExportScope,
    InvestigationExport,
    plain,
    write_json,
)
from lacis.storage.homonym_decisions import HomonymDecision, HomonymDecisionStore
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.notices import NoticeFamily, OfficeTransfer
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore

SCHEMA_PATH = Path(__file__).parents[2] / "site/public/schemas/investigation-1.schema.json"
EXPORTED_AT = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers du 12 rue des Lilas ?",
    datetime(2026, 11, 13, 9, 0, tzinfo=UTC),
    Path("faux-plombiers-31"),
)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    connection = builder.connection
    NoteStore(connection).save(scenario.acme, "Même gérant que **DUPONT SERVICES**.")
    TagStore(connection).add(scenario.acme, "réseau Dupont")
    VerdictStore(connection).save(scenario.acme, Verdict.SUSPECT, "Reprise d'activité.")
    builder.notice(scenario.dupont_services, NoticeFamily.INSOLVENCY, date(2022, 11, 3))
    builder.notice(
        scenario.acme,
        NoticeFamily.AMENDMENT,
        date(2024, 2, 1),
        office_transfer=OfficeTransfer(None, date(2024, 1, 15), effective_date_stated=True),
    )
    HomonymDecisionStore(connection).record(
        scenario.jean, scenario.jean_pierre, HomonymDecision.SAME_PERSON
    )
    return scenario


def exported(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    shown: frozenset[str] | None = None,
) -> Any:
    export = InvestigationExport(builder.connection, phoenix_report(scenario), ExportScope(shown))
    return json.loads(json.dumps(export.document(INVESTIGATION, EXPORTED_AT)))


def schema_errors(document: object) -> list[str]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    return [error.message for error in validator.iter_errors(document)]


def entity_of(document: Any, identifier: str) -> Any:
    return next(entity for entity in document["entities"] if entity["identifier"] == identifier)


def test_the_export_validates_against_its_published_schema(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    document = exported(builder, scenario)
    assert schema_errors(document) == []
    assert document["$schema"] == SCHEMA_URL
    assert json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))["$id"] == SCHEMA_URL
    assert SCHEMA_URL.endswith(f"/lacis/schemas/{SCHEMA_PATH.name}")
    assert document["lacis_version"] == __version__
    assert document["scope"] == "investigation"
    assert document["investigation"] == {
        "name": "faux-plombiers-31",
        "question": "Qui se cache derrière les plombiers du 12 rue des Lilas ?",
        "created_at": "2026-11-13T09:00:00+00:00",
    }


def test_the_export_keeps_every_entity_link_and_signal(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    document = exported(builder, scenario)
    assert len(document["entities"]) == len(builder.graph_store.entities())
    assert len(document["links"]) == len(builder.graph_store.links())
    assert [signal["rule"] for signal in document["signals"]] == ["phoenix_scheme"]
    decisions = document["homonym_decisions"]
    assert [decision["decision"] for decision in decisions] == ["même personne"]
    assert {decisions[0]["first_person"], decisions[0]["second_person"]} == {
        scenario.jean,
        scenario.jean_pierre,
    }


def test_the_export_keeps_the_notes_tags_and_verdicts(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    document = exported(builder, scenario)
    acme = entity_of(document, scenario.acme)
    assert acme["tags"] == ["réseau Dupont"]
    assert acme["note"]["text"] == "Même gérant que **DUPONT SERVICES**."
    verdict = acme["verdict"]
    assert (verdict["verdict"], verdict["label"], verdict["reason"]) == (
        "suspect",
        "Suspect",
        "Reprise d'activité.",
    )
    holding = entity_of(document, scenario.holding)
    assert (holding["tags"], holding["note"], holding["verdict"]) == ([], None, None)


def test_every_fact_cites_responses_that_are_exported(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    document = exported(builder, scenario)
    known = {response["identifier"] for response in document["responses"]}
    collected_links = [link for link in document["links"] if link["kind"] != "same_person"]
    facts = [*document["entities"], *collected_links]
    notices = [notice for entity in document["entities"] for notice in entity["notices"]]
    assert len(notices) == 2
    for fact in [*facts, *notices]:
        assert fact["provenance"]
        assert set(fact["provenance"]) <= known
    acme_notice = entity_of(document, scenario.acme)["notices"][0]
    assert acme_notice["office_transfer"] == {
        "country": None,
        "effective_on": "2024-01-15",
        "effective_date_stated": True,
    }


def test_the_filtered_view_exports_only_the_visible_entities_and_their_links(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    link = builder.graph_store.links_of(scenario.acme)[0]
    shown = frozenset({link.source, link.target, scenario.holding})
    document = exported(builder, scenario, shown)
    assert schema_errors(document) == []
    assert document["scope"] == "filtered_view"
    assert {entity["identifier"] for entity in document["entities"]} == shown
    assert document["links"]
    assert all({link["source"], link["target"]} <= shown for link in document["links"])
    assert document["homonym_decisions"] == []
    assert all(signal["subject"] in shown for signal in document["signals"])


def test_an_export_without_signals_has_an_empty_list(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    document = InvestigationExport(builder.connection, None, ExportScope()).document(
        INVESTIGATION, EXPORTED_AT
    )
    assert document["signals"] == []


def test_the_export_is_written_as_readable_utf8(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    destination = tmp_path / "faux-plombiers-31.json"
    document = InvestigationExport(builder.connection, None, ExportScope()).document(
        INVESTIGATION, EXPORTED_AT
    )
    write_json(document, destination)
    text = destination.read_text(encoding="utf-8")
    assert "derrière" in text
    assert json.loads(text) == document
    assert b"\r" not in destination.read_bytes()


def test_only_plain_values_are_exported() -> None:
    assert plain({1: (date(2024, 1, 2), Verdict.SUSPECT)}) == {"1": ["2024-01-02", "suspect"]}
    with pytest.raises(TypeError):
        plain(object())
