import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lacis import __version__
from lacis.design.tokens import LIGHT_THEME
from lacis.details import EntityDetails, LinkLine, SignalCard, entity_details, written_moment
from lacis.exports.json_export import ExportScope, Plain, plain
from lacis.exports.markdown_report import escaped, quoted
from lacis.graph.descriptions import CLOSED_WORDS
from lacis.graph.filters import KIND_FILTER_LABELS
from lacis.signals.store import SignalReport
from lacis.storage.entities import Entity, EntityKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.investigations import Investigation

FORBIDDEN_IN_NAMES = re.compile(r'[\\/:*?"<>|#^\[\]\s]+')
FORBIDDEN_IN_ALIASES = re.compile(r"[|\[\]\s]+")
FORBIDDEN_IN_TAGS = re.compile(r"[^\w/-]+")
FORBIDDEN_IN_KEYS = re.compile(r"[^\w-]+")
MAXIMUM_NAME_LENGTH = 100
UNNAMED = "Sans nom"
INDEX_PREFIX = "Enquête "
KIND_TAG_PREFIX = "lacis/"
INDEX_TAG = "lacis/enquête"
SETTINGS_FOLDER = ".obsidian"
GRAPH_SETTINGS = "graph.json"
NOTE_EXTENSION = ".md"


def note_name(label: str) -> str:
    cleaned = " ".join(FORBIDDEN_IN_NAMES.sub(" ", label).split()).strip(" .")
    return cleaned[:MAXIMUM_NAME_LENGTH].rstrip(" .") or UNNAMED


def tag_of(label: str) -> str:
    cleaned = FORBIDDEN_IN_TAGS.sub("-", label.strip()).strip("-/")
    if not cleaned or cleaned.isdigit():
        return f"tag-{cleaned}".rstrip("-")
    return cleaned


def yaml_scalar(value: Plain) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def front_matter(properties: list[tuple[str, Plain]]) -> list[str]:
    lines = ["---"]
    for key, value in properties:
        if value is None or value in ("", []):
            continue
        name = FORBIDDEN_IN_KEYS.sub("_", key)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            lines.append(f"{name}:")
            lines += [f"  - {yaml_scalar(item)}" for item in value]
        else:
            lines.append(f"{name}: {yaml_scalar(value)}")
    return [*lines, "---"]


@dataclass(frozen=True)
class NoteSubject:
    identifier: str
    label: str
    distinction: str


def unique_names(subjects: list[NoteSubject], reserved: str) -> dict[str, str]:
    bases = {subject.identifier: note_name(subject.label) for subject in subjects}
    counts: dict[str, int] = {}
    for base in [reserved, *bases.values()]:
        counts[base.casefold()] = counts.get(base.casefold(), 0) + 1
    names: dict[str, str] = {}
    taken = {reserved.casefold()}
    for subject in sorted(subjects, key=lambda subject: subject.identifier):
        candidate = bases[subject.identifier]
        if counts[candidate.casefold()] > 1:
            candidate = note_name(f"{candidate} ({subject.distinction})")
        unique, number = candidate, 2
        while unique.casefold() in taken:
            unique, number = f"{candidate} {number}", number + 1
        taken.add(unique.casefold())
        names[subject.identifier] = unique
    return names


def distinction(entity: Entity, details: EntityDetails) -> str:
    return details.facts[0] if details.facts else entity.identifier


@dataclass(frozen=True)
class VaultNote:
    path: Path
    text: str


class ObsidianVault:
    def __init__(
        self,
        connection: sqlite3.Connection,
        report: SignalReport | None,
        scope: ExportScope,
    ) -> None:
        self.connection = connection
        self.report = report
        self.scope = scope
        self.entities = [
            entity
            for entity in GraphStore(connection).entities()
            if scope.keeps(entity.identifier)
        ]
        self.names: dict[str, str] = {}

    def notes(self, investigation: Investigation, exported_at: datetime) -> list[VaultNote]:
        index = note_name(f"{INDEX_PREFIX}{investigation.name}")
        pairs = [
            (entity, found)
            for entity in self.entities
            if (found := entity_details(self.connection, entity.identifier, self.report))
        ]
        subjects = [
            NoteSubject(entity.identifier, entity.label, distinction(entity, found))
            for entity, found in pairs
        ]
        self.names = unique_names(subjects, index)
        details = [found for _entity, found in pairs]
        notes = [self.entity_note(entity, found) for entity, found in pairs]
        return [self.index_note(index, investigation, exported_at, details), *notes]

    def link_to(self, identifier: str, label: str) -> str:
        name = self.names[identifier]
        alias = " ".join(FORBIDDEN_IN_ALIASES.sub(" ", label).split())
        return f"[[{name}]]" if name == alias else f"[[{name}|{alias}]]"

    def folder_of(self, kind: EntityKind) -> str:
        return KIND_FILTER_LABELS[kind]

    def entity_note(self, entity: Entity, details: EntityDetails) -> VaultNote:
        name = self.names[entity.identifier]
        verdict = details.verdict
        properties: list[tuple[str, Plain]] = [
            ("lacis_identifier", entity.identifier),
            ("lacis_kind", details.kind_label.lower()),
            ("aliases", [entity.label] if entity.label != name else []),
            (
                "tags",
                [
                    f"{KIND_TAG_PREFIX}{tag_of(details.kind_label.lower())}",
                    *(tag_of(tag.label) for tag in details.tags),
                ],
            ),
            ("lacis_verdict", verdict.verdict.label if verdict else None),
            ("lacis_verdict_reason", verdict.reason if verdict else None),
            *((key, plain(value)) for key, value in sorted(entity.attributes.items())),
            ("lacis_first_collected_at", plain(entity.first_collected_at)),
            ("lacis_last_collected_at", plain(entity.last_collected_at)),
        ]
        lines = [
            *front_matter(properties),
            "",
            f"# {escaped(entity.label)}",
            "",
            " · ".join([details.kind_label, *(escaped(fact) for fact in details.facts)]),
            "",
        ]
        if verdict:
            reason = escaped(verdict.reason.strip())
            lines += [
                f"**Verdict : {verdict.verdict.label}**" + (f", {reason}" if reason else ""),
                "",
            ]
        lines += self.links_section(details.links)
        lines += self.signals_section(details.signals)
        if details.note:
            lines += ["## Note", "", *quoted(details.note.text), ""]
        lines += self.notices_section(details)
        lines += self.sources_section(details)
        path = Path(self.folder_of(entity.kind)) / f"{name}{NOTE_EXTENSION}"
        return VaultNote(path, "\n".join(lines).rstrip() + "\n")

    def links_section(self, links: tuple[LinkLine, ...]) -> list[str]:
        kept = [line for line in links if self.scope.keeps(line.reference.identifier)]
        if not kept:
            return []
        lines = ["## Liens", ""]
        for line in kept:
            target = self.link_to(line.reference.identifier, line.reference.label)
            text = (
                f"{line.role} {target}" if line.role.endswith(" de") else f"{line.role} : {target}"
            )
            if line.closed:
                text += f" ({CLOSED_WORDS[line.reference.kind]})"
            if line.decided_on:
                text += f", {line.decided_on.lower()}"
            lines.append(f"- {text}")
        return [*lines, ""]

    def signals_section(self, signals: tuple[SignalCard, ...]) -> list[str]:
        if not signals:
            return []
        lines = ["## Signaux", ""]
        for signal in signals:
            severity = signal.severity.label.lower()
            parts = [
                f"**{escaped(signal.title)}**, gravité {severity}, score {signal.score_value}."
            ]
            if signal.explanation:
                parts.append(escaped(signal.explanation))
            others = [
                self.link_to(reference.identifier, reference.label)
                for reference in signal.references
                if self.scope.keeps(reference.identifier)
            ]
            if others:
                parts.append(f"Entités en cause : {', '.join(others)}.")
            lines.append(f"- {' '.join(parts)}")
        return [*lines, ""]

    def notices_section(self, details: EntityDetails) -> list[str]:
        if not details.notices:
            return []
        lines = ["## Annonces BODACC", ""]
        for notice in details.notices:
            heading = f"{notice.written_date}, {notice.family_label}"
            if notice.summary:
                heading += f" : {escaped(notice.summary)}"
            lines.append(f"- {heading} ([annonce]({notice.url}))")
        return [*lines, ""]

    def sources_section(self, details: EntityDetails) -> list[str]:
        if not details.sources:
            return []
        lines = ["## Sources", ""]
        for source in details.sources:
            lines.append(
                f"- {source.source_name}, collecté le {source.written_date} "
                f"([réponse]({source.url})), empreinte `{source.fingerprint}`"
            )
        return [*lines, ""]

    def index_note(
        self,
        name: str,
        investigation: Investigation,
        exported_at: datetime,
        details: list[EntityDetails],
    ) -> VaultNote:
        properties: list[tuple[str, Plain]] = [
            ("lacis_investigation", investigation.name),
            ("lacis_question", investigation.question),
            ("lacis_exported_at", plain(exported_at)),
            ("lacis_version", __version__),
            ("tags", [INDEX_TAG]),
        ]
        coverage = (
            "la vue filtrée du graphe" if self.scope.shown is not None else "toute l'enquête"
        )
        exported = f"Exporté le {written_moment(exported_at)} par Lacis {__version__}"
        lines = [
            *front_matter(properties),
            "",
            f"# {escaped(f'{INDEX_PREFIX}{investigation.name}')}",
            "",
            f"**Question :** {escaped(investigation.question)}",
            "",
            f"{exported}, à partir de {coverage}.",
            "",
            *self.index_signals(),
            *self.index_entities(details),
        ]
        return VaultNote(Path(f"{name}{NOTE_EXTENSION}"), "\n".join(lines).rstrip() + "\n")

    def index_signals(self) -> list[str]:
        signals = [
            signal
            for signal in (self.report.signals if self.report else ())
            if self.scope.keeps(signal.subject)
        ]
        if not signals:
            return ["## Signaux", "", "Aucun signal.", ""]
        ordered = sorted(signals, key=lambda signal: (-signal.severity.rank, -signal.score))
        labels = {entity.identifier: entity.label for entity in self.entities}
        lines = ["## Signaux", ""]
        for signal in ordered:
            subject = self.link_to(signal.subject, labels[signal.subject])
            lines.append(
                f"- **{escaped(signal.title)}** : {subject}, gravité "
                f"{signal.severity.label.lower()}"
            )
        return [*lines, ""]

    def index_entities(self, details: list[EntityDetails]) -> list[str]:
        lines = ["## Entités", ""]
        for kind, folder in KIND_FILTER_LABELS.items():
            found = sorted(
                (item for item in details if item.kind is kind),
                key=lambda item: item.name.casefold(),
            )
            if not found:
                continue
            lines += [f"### {folder} ({len(found)})", ""]
            lines += [f"- {self.link_to(item.identifier, item.name)}" for item in found]
            lines.append("")
        return lines

    def graph_settings(self, index: VaultNote) -> str:
        colours = LIGHT_THEME.colours
        kinds = {entity.kind for entity in self.entities}
        groups = [
            {
                "query": f'path:"{folder}/"',
                "color": {"a": 1, "rgb": int(getattr(colours, kind.value).lstrip("#"), 16)},
            }
            for kind, folder in KIND_FILTER_LABELS.items()
            if kind in kinds
        ]
        settings = {
            "search": f'-file:"{index.path.stem}"',
            "showTags": False,
            "showAttachments": False,
            "hideUnresolved": True,
            "showOrphans": True,
            "colorGroups": groups,
        }
        return json.dumps(settings, ensure_ascii=False, indent=2) + "\n"

    def write(
        self, investigation: Investigation, destination: Path, exported_at: datetime
    ) -> None:
        notes = self.notes(investigation, exported_at)
        destination.mkdir(exist_ok=True)
        for note in notes:
            path = destination / note.path
            path.parent.mkdir(exist_ok=True)
            path.write_text(note.text, encoding="utf-8", newline="\n")
        settings = destination / SETTINGS_FOLDER
        settings.mkdir(exist_ok=True)
        (settings / GRAPH_SETTINGS).write_text(
            self.graph_settings(notes[0]), encoding="utf-8", newline="\n"
        )
