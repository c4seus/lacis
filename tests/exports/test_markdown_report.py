import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import COLLECTED_AT, InvestigationBuilder
from lacis import __version__
from lacis.details import written_moment
from lacis.exports.json_export import ExportScope
from lacis.exports.markdown_report import escaped, markdown_text, write_markdown
from lacis.exports.report import ReportBuilder, ReportContent
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.collection_log import CollectionLog, LoggedRequest
from lacis.storage.expansion_log import ExpansionLog, ExpansionOperation, RecordedExpansion
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore

CREATED_AT = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)
STARTED_AT = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
DECIDED_AT = datetime(2026, 11, 12, 14, 0, tzinfo=UTC)
PRODUCED_AT = datetime(2026, 11, 19, 10, 0, tzinfo=UTC)
COMPUTED_AT = datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers du 12 rue des Lilas ?",
    CREATED_AT,
    Path("faux-plombiers-31"),
)


@pytest.fixture
def builder(investigation_connection: sqlite3.Connection) -> InvestigationBuilder:
    return InvestigationBuilder(investigation_connection)


@pytest.fixture
def scenario(builder: InvestigationBuilder) -> PlumbersScenario:
    scenario = plumbers_scenario(builder)
    connection = builder.connection
    verdicts = VerdictStore(connection, now=lambda: DECIDED_AT)
    verdicts.save(scenario.dupont_services, Verdict.CONFIRMED, "Liquidée, puis *reprise*.")
    verdicts.save(scenario.acme, Verdict.SUSPECT, "Reprise d'activité.")
    verdicts.save(scenario.jean, Verdict.TO_CHECK, "")
    verdicts.save(scenario.invest, Verdict.DISMISSED, "Simple associé.")
    TagStore(connection).add(scenario.acme, "réseau Dupont")
    TagStore(connection).add(scenario.acme, "prioritaire")
    notes = NoteStore(connection, now=lambda: DECIDED_AT)
    notes.save(scenario.acme, "Même gérant que **DUPONT SERVICES**.\n\n## Relances\nAppeler.")
    log = CollectionLog(connection)
    log.record(
        LoggedRequest(STARTED_AT, ResponseSource.COMPANY_REGISTER, "/search", 200, timedelta(0))
    )
    log.record(
        LoggedRequest(STARTED_AT, ResponseSource.COMPANY_REGISTER, "/search", 503, timedelta(0))
    )
    expansions = ExpansionLog(connection)
    expansions.record(
        RecordedExpansion(
            STARTED_AT, ExpansionOperation.ADDED, scenario.acme, "ACME PLOMBERIE", 0, 1
        )
    )
    expansions.record(
        RecordedExpansion(
            STARTED_AT + timedelta(minutes=5),
            ExpansionOperation.EXPANDED,
            scenario.acme,
            "ACME PLOMBERIE",
            2,
            8,
            cap=200,
            cancelled=True,
            failures=2,
        )
    )
    return scenario


def signal_report(scenario: PlumbersScenario) -> SignalReport:
    phoenix = phoenix_report(scenario).signals[0]
    domiciliation = Signal(
        "mass_domiciliation",
        "Domiciliation de masse",
        scenario.address,
        Severity.LOW,
        0.4,
        "2 entreprises à la même adresse.",
        (),
    )
    return SignalReport((domiciliation, phoenix), 1, date(2026, 11, 10), "", COMPUTED_AT)


def content_of(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    shown: frozenset[str] | None = None,
    report: SignalReport | None = None,
) -> ReportContent:
    report_builder = ReportBuilder(
        builder.connection, report or signal_report(scenario), ExportScope(shown)
    )
    return report_builder.content(INVESTIGATION, PRODUCED_AT)


def sections(text: str) -> dict[str, str]:
    found = {}
    for block in text.split("\n## ")[1:]:
        heading, _, body = block.partition("\n")
        found[heading] = body
    return found


def report_text(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    shown: frozenset[str] | None = None,
) -> str:
    return markdown_text(content_of(builder, scenario, shown))


def test_the_report_opens_with_the_question_and_the_coverage(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    lines = report_text(builder, scenario).splitlines()
    assert lines[0] == "# Rapport d'enquête : faux-plombiers-31"
    assert lines[2] == ("**Question :** Qui se cache derrière les plombiers du 12 rue des Lilas ?")
    assert lines[4] == (
        f"Rapport produit le {written_moment(PRODUCED_AT)} par Lacis {__version__}, "
        f"à partir de l'enquête créée le {written_moment(CREATED_AT)}. "
        "Il couvre toute l'enquête : 9 entités et 11 liens."
    )


def test_the_report_has_every_section_in_order(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    assert list(sections(report_text(builder, scenario))) == [
        "Synthèse",
        "Méthode",
        "Constats",
        "Signaux",
        "Notes",
        "Réserves",
        "Annexe : preuves",
    ]


def test_the_summary_counts_findings_signals_and_notes(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    summary = sections(report_text(builder, scenario))["Synthèse"]
    assert summary.strip().splitlines() == [
        "- Constats : Confirmé : 1, Suspect : 1, À vérifier : 1, Écarté : 1",
        "- 2 signaux",
        "- 1 note",
    ]


def test_the_method_describes_the_sources_and_their_use(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    method = sections(report_text(builder, scenario))["Méthode"]
    collected = written_moment(COLLECTED_AT)
    assert f"collectées du {collected} au {collected}." in method
    assert "- **Recherche d'entreprises** : l'API Recherche d'entreprises de l'État" in method
    assert "- **BODACC** : le Bulletin officiel des annonces civiles et commerciales" in method
    assert f"| Recherche d'entreprises | 2 | 1 | 1 | du {collected} au {collected} |" in method
    assert f"| BODACC | 0 | 0 | 1 | du {collected} au {collected} |" in method


def test_the_method_lists_every_expansion_with_its_depth(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    method = sections(report_text(builder, scenario))["Méthode"]
    expanded_at = written_moment(STARTED_AT + timedelta(minutes=5))
    assert "L'enquête part de 1 entité ajoutée depuis la recherche." in method
    assert (
        f"| {written_moment(STARTED_AT)} | ACME PLOMBERIE | Ajout depuis la recherche |  | 1 |  |"
        in method
    )
    assert (
        f"| {expanded_at} | ACME PLOMBERIE | Extension | 2 niveaux | 8 | "
        "limite de 200 nouvelles entités atteinte, annulée, 2 échecs |"
    ) in method
    assert "0 entité a été étendue sur 6. Les 6 autres restent des pistes" in method
    assert f"Les signaux ont été calculés le {written_moment(COMPUTED_AT)}." in method


def test_the_method_says_when_no_expansion_was_recorded(
    builder: InvestigationBuilder, investigation_connection: sqlite3.Connection
) -> None:
    scenario = plumbers_scenario(builder)
    method = sections(report_text(builder, scenario))["Méthode"]
    assert "Aucune extension n'est enregistrée pour cette enquête" in method
    assert "| Date |" not in method


def test_the_method_counts_the_entities_already_expanded(
    builder: InvestigationBuilder,
) -> None:
    builder.address("1 RUE DU PORT 13002 MARSEILLE", expanded=True)
    builder.person("Camille", "LEROUX")
    method = sections(markdown_text(content_of_empty(builder)))["Méthode"]
    assert "1 entité a été étendue sur 2. La dernière reste une piste" in method


def test_the_method_says_when_every_lead_was_explored(builder: InvestigationBuilder) -> None:
    builder.address("1 RUE DU PORT 13002 MARSEILLE", expanded=True)
    method = sections(markdown_text(content_of_empty(builder)))["Méthode"]
    assert "1 entité a été étendue sur 1. Toutes les pistes ont été explorées." in method


def content_of_empty(builder: InvestigationBuilder) -> ReportContent:
    return ReportBuilder(builder.connection, None, ExportScope()).content(
        INVESTIGATION, PRODUCED_AT
    )


def test_a_report_without_data_or_signals_says_so(
    investigation_connection: sqlite3.Connection,
) -> None:
    content = ReportBuilder(investigation_connection, None, ExportScope()).content(
        INVESTIGATION, PRODUCED_AT
    )
    found = sections(markdown_text(content))
    assert "Aucune donnée n'a encore été collectée pour cette enquête." in found["Méthode"]
    assert "### Sources" not in found["Méthode"]
    assert "Les signaux n'ont pas pu être calculés" in found["Méthode"]
    assert "- Aucun constat." in found["Synthèse"]
    assert "Aucune entité n'a encore de verdict." in found["Constats"]
    assert "Aucun signal ne concerne les entités de ce rapport." in found["Signaux"]
    assert "Aucune note." in found["Notes"]
    assert "0 rapprochement a été décidé." in found["Réserves"]


def test_the_findings_are_grouped_by_verdict(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    findings = sections(report_text(builder, scenario))["Constats"]
    headings = [line for line in findings.splitlines() if line.startswith("### ")]
    assert headings == [
        "### Confirmé (1)",
        "### Suspect (1)",
        "### À vérifier (1)",
        "### Écarté (1)",
    ]
    decided = written_moment(DECIDED_AT)
    assert "- **DUPONT SERVICES**, entreprise, SIREN " in findings
    assert (
        ", créée le 01/06/2019, fermée le 15/01/2023\n"
        "  - Raison : Liquidée, puis \\*reprise\\*.\n"
        f"  - Verdict posé le {decided}"
    ) in findings
    assert "- **Jean DUPONT**, personne, né en 05/1980\n" in findings
    assert "- **DUPONT INVEST LTD**, entreprise étrangère, pays Royaume-Uni\n" in findings
    assert "  - Tags : prioritaire, réseau Dupont\n" in findings
    assert "  - Raison : aucune raison donnée\n" in findings
    assert "5 entités n'ont pas encore de verdict." in findings


def test_the_signals_are_sorted_by_severity_with_their_entities(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    signals = sections(report_text(builder, scenario))["Signaux"]
    assert signals.index("### Schéma phénix : DUPONT SERVICES") < signals.index(
        "### Domiciliation de masse : 12 RUE DES LILAS 31000 TOULOUSE"
    )
    assert "Gravité forte, score 0,85." in signals
    assert "Entités en cause : ACME PLOMBERIE, Jean DUPONT, Jean Pierre DUPONT." in signals
    assert "Gravité faible, score 0,40.\n\n2 entreprises à la même adresse." in signals
    assert "un signal est une piste" in signals.lower()


def test_the_notes_are_quoted_under_their_entity(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    notes = sections(report_text(builder, scenario))["Notes"]
    assert (
        "### ACME PLOMBERIE (entreprise)\n\n"
        "> Même gérant que **DUPONT SERVICES**.\n"
        ">\n"
        "> ## Relances\n"
        "> Appeler.\n\n"
        f"Note modifiée le {written_moment(DECIDED_AT)}."
    ) in notes


def test_the_reserves_name_the_limits_of_the_report(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    reserves = sections(report_text(builder, scenario))["Réserves"].strip().splitlines()
    assert reserves[0].startswith("- Les données viennent de registres publics")
    assert reserves[1].startswith("- Les signaux sont des pistes")
    assert "1 rapprochement a été décidé." in reserves[2]
    assert reserves[3] == (
        "- 1 requête a échoué pendant la collecte : des informations peuvent manquer."
    )
    assert reserves[4] == (
        "- 6 entités n'ont pas été étendues : leurs autres liens restent inconnus."
    )
    assert len(reserves) == 5


def test_the_filtered_view_reports_only_the_entities_shown(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    shown = frozenset({scenario.acme, scenario.dupont_services, scenario.jean})
    text = report_text(builder, scenario, shown)
    assert "Il couvre la vue filtrée du graphe : 3 entités sur 9, et 1 lien entre elles." in text
    found = sections(text)
    assert "### Écarté" not in found["Constats"]
    assert "Domiciliation de masse" not in found["Signaux"]
    assert "Schéma phénix" in found["Signaux"]
    assert "0 rapprochement a été décidé." in found["Réserves"]
    assert found["Réserves"].strip().splitlines()[-1] == (
        "- Ce rapport ne couvre que la vue filtrée du graphe : les entités masquées par les "
        "filtres n'y figurent pas."
    )


def test_labels_cannot_break_the_markdown_of_the_report(
    builder: InvestigationBuilder,
) -> None:
    builder.company("SOCIÉTÉ *ÉTOILE* | [LIENS] #1")
    text = markdown_text(content_of_empty(builder))
    assert escaped("SOCIÉTÉ *ÉTOILE* | [LIENS] #1") == (
        "SOCIÉTÉ \\*ÉTOILE\\* \\| \\[LIENS\\] \\#1"
    )
    assert "*ÉTOILE*" not in text


def test_the_report_is_written_in_utf_8_with_unix_line_endings(tmp_path: Path) -> None:
    destination = tmp_path / "rapport.md"
    write_markdown("# Rapport d'enquête\n", destination)
    assert destination.read_bytes() == "# Rapport d'enquête\n".encode()


def test_a_source_asked_without_any_response_kept_says_so(
    investigation_connection: sqlite3.Connection,
) -> None:
    CollectionLog(investigation_connection).record(
        LoggedRequest(STARTED_AT, ResponseSource.BODACC, "/notices", 500, timedelta(0))
    )
    content = ReportBuilder(investigation_connection, None, ExportScope()).content(
        INVESTIGATION, PRODUCED_AT
    )
    assert "| BODACC | 1 | 1 | 0 | aucune réponse |" in markdown_text(content)


def test_a_report_where_every_entity_has_a_verdict_counts_none_left(
    builder: InvestigationBuilder,
) -> None:
    acme = builder.company("ACME PLOMBERIE")
    VerdictStore(builder.connection).save(acme, Verdict.CONFIRMED, "Vérifié.")
    findings = sections(markdown_text(content_of_empty(builder)))["Constats"]
    assert "### Confirmé (1)" in findings
    assert "pas encore de verdict" not in findings


ANCHOR = re.compile(r'<a id="preuve-(\d+)"></a>\*\*R(\d+)\*\*')


def anchors_of(text: str) -> set[str]:
    return {number for number, label in ANCHOR.findall(text) if number == label}


def test_the_appendix_lists_each_cited_response_once_with_its_evidence(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    appendix = sections(report_text(builder, scenario))["Annexe : preuves"]
    entries = [line for line in appendix.splitlines() if line.startswith("- ")]
    response = builder.response
    expected = (
        f'- <a id="preuve-1"></a>**R1** : Recherche d\'entreprises, collectée le '
        f"{written_moment(response.collected_at)}, <{response.url}>, "
        f"empreinte SHA-256 `{response.fingerprint}`"
    )
    assert entries == [expected]


def test_responses_are_numbered_in_the_order_the_report_cites_them(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    builder.response = ResponseStore(builder.connection).save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.example/search",
            b"[]",
            COLLECTED_AT,
            {"q": "AZUR PLOMBERIE", "page": "1"},
        )
    )
    azur = builder.company("AZUR PLOMBERIE")
    VerdictStore(builder.connection).save(azur, Verdict.CONFIRMED, "Même adresse.")
    found = sections(report_text(builder, scenario))
    confirmed = found["Constats"].split("### Suspect")[0]
    assert "**AZUR PLOMBERIE**" in confirmed.split("- **DUPONT SERVICES**")[0]
    entries = [line for line in found["Annexe : preuves"].splitlines() if line.startswith("- ")]
    assert len(entries) == 2
    assert entries[0].startswith('- <a id="preuve-1"></a>**R1** : Recherche')
    assert ", paramètres `page=1&q=AZUR+PLOMBERIE`, empreinte SHA-256 `" in entries[0]


def test_the_filtered_view_cites_only_the_responses_of_the_entities_shown(
    builder: InvestigationBuilder, scenario: PlumbersScenario
) -> None:
    builder.response = builder.bodacc_response
    lone = builder.company("SOCIÉTÉ ISOLÉE")
    VerdictStore(builder.connection).save(lone, Verdict.DISMISSED, "")
    shown = frozenset({scenario.acme})
    appendix = sections(report_text(builder, scenario, shown))["Annexe : preuves"]
    assert "BODACC" not in appendix
    assert anchors_of(appendix) == {"1"}
