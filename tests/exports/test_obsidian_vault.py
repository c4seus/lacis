import json
import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from graph_scenario import PlumbersScenario, phoenix_report, plumbers_scenario
from investigation_builder import InvestigationBuilder
from lacis import __version__
from lacis.details import written_moment
from lacis.exports.json_export import ExportScope
from lacis.exports.obsidian_vault import (
    NoteSubject,
    ObsidianVault,
    front_matter,
    note_name,
    tag_of,
    unique_names,
)
from lacis.signals.signal import Severity, Signal
from lacis.signals.store import SignalReport
from lacis.storage.investigations import Investigation
from lacis.storage.notes import NoteStore
from lacis.storage.notices import NoticeFamily
from lacis.storage.tags import TagStore
from lacis.storage.verdicts import Verdict, VerdictStore

EXPORTED_AT = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
INVESTIGATION = Investigation(
    "faux-plombiers-31",
    "Qui se cache derrière les plombiers du 12 rue des Lilas ?",
    datetime(2026, 11, 13, 9, 0, tzinfo=UTC),
    Path("faux-plombiers-31"),
)
INDEX = "Enquête faux-plombiers-31.md"
WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")


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
    VerdictStore(connection).save(scenario.holding, Verdict.TO_CHECK, "")
    builder.notice(scenario.dupont_services, NoticeFamily.INSOLVENCY, date(2022, 11, 3))
    builder.notice(
        scenario.dupont_services, NoticeFamily.REMOVAL, date(2023, 1, 20), "Radiation *d'office*"
    )
    return scenario


def write_vault(
    builder: InvestigationBuilder,
    scenario: PlumbersScenario,
    destination: Path,
    shown: frozenset[str] | None = None,
) -> Path:
    vault = ObsidianVault(builder.connection, phoenix_report(scenario), ExportScope(shown))
    vault.write(INVESTIGATION, destination, EXPORTED_AT)
    return destination


def notes_of(vault: Path) -> dict[str, str]:
    return {
        path.relative_to(vault).as_posix(): path.read_text(encoding="utf-8")
        for path in vault.rglob("*.md")
    }


def linked_names(text: str) -> set[str]:
    return set(WIKILINK.findall(text))


def test_the_vault_has_an_index_and_one_note_per_entity_in_folders_by_kind(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    vault = write_vault(builder, scenario, tmp_path / "vault")
    assert sorted(notes_of(vault)) == [
        "Adresses/12 RUE DES LILAS 31000 TOULOUSE.md",
        INDEX,
        "Entreprises étrangères/DUPONT INVEST LTD.md",
        "Entreprises/ACME PLOMBERIE.md",
        "Entreprises/DUPONT SERVICES.md",
        "Entreprises/HOLDING DUPONT.md",
        "Personnes/Jean DUPONT.md",
        "Personnes/Jean Pierre DUPONT.md",
        "Établissements/Siège — TOULOUSE (SIRET 100 000 000 00015).md",
        "Établissements/Siège — TOULOUSE (SIRET 100 000 001 00015).md",
    ]
    assert len(notes_of(vault)) == len(builder.graph_store.entities()) + 1


def test_every_wikilink_leads_to_a_note_of_the_vault(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    notes = notes_of(write_vault(builder, scenario, tmp_path / "vault"))
    names = {Path(path).stem for path in notes}
    for text in notes.values():
        assert linked_names(text) <= names


def test_the_links_between_notes_match_the_links_of_the_investigation(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    notes = notes_of(write_vault(builder, scenario, tmp_path / "vault"))
    by_identifier = {}
    for path, text in notes.items():
        found = re.search(r'^lacis_identifier: "(.+)"$', text, re.MULTILINE)
        if found:
            by_identifier[found[1]] = (Path(path).stem, text)
    for link in builder.graph_store.links():
        source_name, source_text = by_identifier[link.source]
        target_name, target_text = by_identifier[link.target]
        links_section = source_text.split("## Liens")[1].split("\n## ")[0]
        assert target_name in linked_names(links_section)
        assert source_name in linked_names(target_text.split("## Liens")[1].split("\n## ")[0])


def test_an_entity_note_keeps_its_facts_as_front_matter(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    notes = notes_of(write_vault(builder, scenario, tmp_path / "vault"))
    acme = notes["Entreprises/ACME PLOMBERIE.md"]
    properties = acme.split("---\n")[1]
    assert properties.splitlines() == [
        f'lacis_identifier: "{scenario.acme}"',
        'lacis_kind: "entreprise"',
        "tags:",
        '  - "lacis/entreprise"',
        '  - "réseau-Dupont"',
        'lacis_verdict: "Suspect"',
        'lacis_verdict_reason: "Reprise d\'activité."',
        'creation_date: "2021-03-01"',
        "is_active: true",
        'siren: "100000000"',
        'lacis_first_collected_at: "2026-11-02T23:11:00+00:00"',
        'lacis_last_collected_at: "2026-11-02T23:11:00+00:00"',
    ]


def test_an_entity_note_describes_the_entity_its_links_signals_and_note(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    notes = notes_of(write_vault(builder, scenario, tmp_path / "vault"))
    acme = notes["Entreprises/ACME PLOMBERIE.md"].split("---\n", 2)[2]
    assert acme.startswith(
        "\n# ACME PLOMBERIE\n\n"
        "Entreprise · SIREN 100 000 000 · Créée le 01/03/2021\n\n"
        "**Verdict : Suspect**, Reprise d'activité.\n\n"
        "## Liens\n\n"
    )
    assert "- Président : [[Jean Pierre DUPONT]]\n" in acme
    assert "- Siège social : [[12 RUE DES LILAS 31000 TOULOUSE]]\n" in acme
    assert (
        "- Établissement : [[Siège — TOULOUSE (SIRET 100 000 000 00015)|Siège — TOULOUSE]]\n"
        in acme
    )
    assert (
        "## Signaux\n\n- **Schéma phénix**, gravité forte, score 0,85. Entités en cause : "
        "[[DUPONT SERVICES]], [[Jean DUPONT]], [[Jean Pierre DUPONT]].\n"
    ) in acme
    assert "## Note\n\n> Même gérant que **DUPONT SERVICES**.\n" in acme
    assert "## Sources\n\n- Recherche d'entreprises, collecté le " in acme
    holding = notes["Entreprises/HOLDING DUPONT.md"]
    assert "- Directeur général de [[ACME PLOMBERIE]]\n" in holding
    assert "**Verdict : À vérifier**\n" in holding


def test_a_closed_company_note_lists_its_bodacc_notices(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    notes = notes_of(write_vault(builder, scenario, tmp_path / "vault"))
    services = notes["Entreprises/DUPONT SERVICES.md"]
    assert "Créée le 01/06/2019 · Fermée le 15/01/2023" in services
    assert "(fermé)" in services
    notices = services.split("## Annonces BODACC\n\n")[1].splitlines()
    assert any(
        line.startswith("- 03/11/2022, Procédure collective ([annonce](https://")
        for line in notices
    )
    assert any(": Radiation \\*d'office\\* ([annonce](https://" in line for line in notices)


def test_the_index_gives_the_question_the_signals_and_the_entities(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    index = notes_of(write_vault(builder, scenario, tmp_path / "vault"))[INDEX]
    assert index.startswith(
        "---\n"
        'lacis_investigation: "faux-plombiers-31"\n'
        'lacis_question: "Qui se cache derrière les plombiers du 12 rue des Lilas ?"\n'
        'lacis_exported_at: "2026-11-23T10:00:00+00:00"\n'
        f'lacis_version: "{__version__}"\n'
        "tags:\n"
        '  - "lacis/enquête"\n'
        "---\n\n"
        "# Enquête faux-plombiers-31\n\n"
        "**Question :** Qui se cache derrière les plombiers du 12 rue des Lilas ?\n\n"
        f"Exporté le {written_moment(EXPORTED_AT)} par Lacis {__version__}, "
        "à partir de toute l'enquête.\n\n"
        "## Signaux\n\n"
        "- **Schéma phénix** : [[DUPONT SERVICES]], gravité forte\n\n"
        "## Entités\n\n"
        "### Entreprises (3)\n\n"
        "- [[ACME PLOMBERIE]]\n"
    )
    assert "### Établissements (2)\n" in index
    assert "### Entreprises étrangères (1)\n\n- [[DUPONT INVEST LTD]]\n" in index


def test_the_graph_view_hides_the_index_and_colours_each_kind(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    vault = write_vault(builder, scenario, tmp_path / "vault")
    settings = json.loads((vault / ".obsidian/graph.json").read_text(encoding="utf-8"))
    assert settings["search"] == '-file:"Enquête faux-plombiers-31"'
    assert settings["showTags"] is False
    assert [group["query"] for group in settings["colorGroups"]] == [
        'path:"Entreprises/"',
        'path:"Personnes/"',
        'path:"Adresses/"',
        'path:"Établissements/"',
        'path:"Entreprises étrangères/"',
    ]
    assert settings["colorGroups"][0]["color"] == {"a": 1, "rgb": 0x3D63DD}


def test_the_filtered_view_writes_only_the_entities_shown(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    shown = frozenset({scenario.acme, scenario.jean_pierre})
    vault = write_vault(builder, scenario, tmp_path / "vault", shown)
    notes = notes_of(vault)
    assert sorted(notes) == [
        INDEX,
        "Entreprises/ACME PLOMBERIE.md",
        "Personnes/Jean Pierre DUPONT.md",
    ]
    acme = notes["Entreprises/ACME PLOMBERIE.md"]
    assert linked_names(acme) == {"Jean Pierre DUPONT"}
    assert "à partir de la vue filtrée du graphe." in notes[INDEX]
    assert "## Signaux\n\nAucun signal." in notes[INDEX]
    settings = json.loads((vault / ".obsidian/graph.json").read_text(encoding="utf-8"))
    assert len(settings["colorGroups"]) == 2


def test_an_empty_folder_receives_the_vault_with_unix_line_endings(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    destination = tmp_path / "coffre"
    destination.mkdir()
    write_vault(builder, scenario, destination)
    written = [path for path in destination.rglob("*") if path.is_file()]
    assert len(written) == 11
    for path in written:
        assert b"\r" not in path.read_bytes()


def test_an_entity_without_links_signals_or_sources_has_a_short_note(
    investigation_connection: sqlite3.Connection, tmp_path: Path
) -> None:
    InvestigationBuilder(investigation_connection).foreign_company("NORTH LTD")
    investigation_connection.execute("DELETE FROM entity_source")
    vault = ObsidianVault(investigation_connection, None, ExportScope())
    vault.write(INVESTIGATION, tmp_path / "vault", EXPORTED_AT)
    note = (tmp_path / "vault/Entreprises étrangères/NORTH LTD.md").read_text(encoding="utf-8")
    assert (
        note.split("---\n", 2)[2] == "\n# NORTH LTD\n\nEntreprise étrangère · Pays Royaume-Uni\n"
    )


def test_a_signal_keeps_its_explanation_without_the_entities_left_out(
    builder: InvestigationBuilder, scenario: PlumbersScenario, tmp_path: Path
) -> None:
    signal = Signal(
        "mass_domiciliation",
        "Domiciliation de masse",
        scenario.acme,
        Severity.LOW,
        0.4,
        "2 entreprises à la même adresse.",
        (scenario.holding,),
    )
    report = SignalReport((signal,), 1, date(2026, 11, 10), "", EXPORTED_AT)
    vault = ObsidianVault(builder.connection, report, ExportScope(frozenset({scenario.acme})))
    vault.write(INVESTIGATION, tmp_path / "vault", EXPORTED_AT)
    acme = (tmp_path / "vault/Entreprises/ACME PLOMBERIE.md").read_text(encoding="utf-8")
    assert (
        "## Signaux\n\n- **Domiciliation de masse**, gravité faible, score 0,40. "
        "2 entreprises à la même adresse.\n"
    ) in acme


def test_note_names_drop_the_characters_files_and_links_refuse() -> None:
    assert note_name('A/B: "C" *D* <E>?|#^[F]\nG') == "A B C D E F G"
    assert note_name("  . ") == "Sans nom"
    assert note_name("X" * 150) == "X" * 100
    assert note_name("Société. ") == "Société"


def test_tags_keep_letters_digits_and_dashes() -> None:
    assert tag_of("réseau Dupont") == "réseau-Dupont"
    assert tag_of("à revoir / urgent!") == "à-revoir-/-urgent"
    assert tag_of("2024") == "tag-2024"
    assert tag_of("!!") == "tag"


def test_front_matter_writes_plain_yaml_values() -> None:
    assert front_matter(
        [
            ("text", 'Dit "oui"'),
            ("flag", False),
            ("count", 3),
            ("score", 0.5),
            ("names", ["A", "B"]),
            ("mixed", [1, "A"]),
            ("place", {"city": "Albi"}),
            ("empty", ""),
            ("nothing", None),
            ("none", []),
            ("bad key!", "x"),
        ]
    ) == [
        "---",
        'text: "Dit \\"oui\\""',
        "flag: false",
        "count: 3",
        "score: 0.5",
        "names:",
        '  - "A"',
        '  - "B"',
        'mixed: [1, "A"]',
        'place: {"city": "Albi"}',
        'bad_key_: "x"',
        "---",
    ]


def test_homonyms_get_distinct_note_names() -> None:
    subjects = [
        NoteSubject("person:1", "Jean DUPONT", "Né en 05/1980"),
        NoteSubject("person:2", "Jean DUPONT", "Né en 05/1980"),
        NoteSubject("person:3", "Jean DUPONT", "Né en 07/1975"),
        NoteSubject("company:1", "Enquête X", "SIREN 1"),
        NoteSubject("company:2", "ACME", "SIREN 2"),
    ]
    assert unique_names(subjects, "Enquête X") == {
        "company:1": "Enquête X (SIREN 1)",
        "company:2": "ACME",
        "person:1": "Jean DUPONT (Né en 05 1980)",
        "person:2": "Jean DUPONT (Né en 05 1980) 2",
        "person:3": "Jean DUPONT (Né en 07 1975)",
    }
