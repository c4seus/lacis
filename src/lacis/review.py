from dataclasses import dataclass, field

from lacis.graph.descriptions import spoken_label
from lacis.graph.expansion import ExpansionReport
from lacis.graph.progress import ExpansionProgress
from lacis.identity.homonyms import Confidence, HomonymProposal
from lacis.overview import InvestigationOverview
from lacis.signals.facts import counted
from lacis.signals.signal import Signal
from lacis.storage.entities import EntityKind, kind_of

CONFIDENCE_LABELS = {
    Confidence.CERTAIN: "Certain",
    Confidence.PROBABLE: "Probable",
    Confidence.WEAK: "Faible",
}
EVIDENCE_PREFIX = "Indice du signal sur "
NO_SIGNAL_TEXT = "Aucun signal"
NO_HOMONYM_TEXT = "Aucun rapprochement en attente"
NO_LEAD_TEXT = "Aucune piste à étendre"
UNAVAILABLE_SIGNALS_PREFIX = "Signaux indisponibles : "
STARTING_TEXT = "Démarrage…"
CANCELLING_TEXT = "Annulation en cours…"


@dataclass(frozen=True)
class QueueEntity:
    identifier: str
    kind: EntityKind
    label: str
    explanation: str
    score: float | None = None

    @property
    def written_score(self) -> str:
        return "" if self.score is None else f"{self.score:.2f}".replace(".", ",")


@dataclass(frozen=True)
class SignalGroup:
    rule: str
    title: str
    entities: tuple[QueueEntity, ...]


@dataclass(frozen=True)
class HomonymEntry:
    first: QueueEntity
    second: QueueEntity
    confidence: Confidence
    reasons: tuple[str, ...]

    @property
    def confidence_label(self) -> str:
        return CONFIDENCE_LABELS[self.confidence]

    @property
    def title(self) -> str:
        return f"{self.first.label} ↔ {self.second.label}"


@dataclass(frozen=True)
class ReviewQueue:
    signal_groups: tuple[SignalGroup, ...]
    homonyms: tuple[HomonymEntry, ...]
    leads: tuple[QueueEntity, ...]
    signal_problem: str = ""

    def entity_identifiers(self) -> list[str]:
        signal_entities = [
            entity.identifier for group in self.signal_groups for entity in group.entities
        ]
        homonym_entities = [entry.first.identifier for entry in self.homonyms]
        return [*signal_entities, *homonym_entities, *(lead.identifier for lead in self.leads)]


class EntityLabels:
    def __init__(self, overview: InvestigationOverview) -> None:
        self.nodes = {node.identifier: node for node in overview.drawing.nodes}

    def entity(
        self, identifier: str, explanation: str, score: float | None, fallback_label: str = ""
    ) -> QueueEntity:
        node = self.nodes.get(identifier)
        if node is None:
            label = fallback_label or identifier
            return QueueEntity(identifier, kind_of(identifier), label, explanation, score)
        return QueueEntity(identifier, node.kind, spoken_label(node), explanation, score)

    def label(self, identifier: str) -> str:
        node = self.nodes.get(identifier)
        return spoken_label(node) if node is not None else identifier


def signal_group(rule: str, signals: list[Signal], labels: EntityLabels) -> SignalGroup:
    ordered = sorted(signals, key=lambda signal: (-signal.severity.rank, -signal.score))
    strongest = ordered[0]
    title = f"{strongest.title} · {strongest.severity.label.lower()}"
    entities: dict[str, QueueEntity] = {}
    for signal in ordered:
        entities.setdefault(
            signal.subject, labels.entity(signal.subject, signal.explanation, signal.score)
        )
    for signal in ordered:
        evidence = f"{EVIDENCE_PREFIX}{labels.label(signal.subject)}"
        for identifier in signal.justifying_entities:
            entities.setdefault(identifier, labels.entity(identifier, evidence, signal.score))
    return SignalGroup(rule, title, tuple(entities.values()))


def signal_groups(
    overview: InvestigationOverview, labels: EntityLabels
) -> tuple[SignalGroup, ...]:
    if overview.report is None:
        return ()
    by_rule: dict[str, list[Signal]] = {}
    for signal in overview.report.signals:
        by_rule.setdefault(signal.rule, []).append(signal)
    groups = [signal_group(rule, signals, labels) for rule, signals in by_rule.items()]
    strongest = {
        rule: max((signal.severity.rank, signal.score) for signal in signals)
        for rule, signals in by_rule.items()
    }
    return tuple(
        sorted(
            groups,
            key=lambda group: (
                -strongest[group.rule][0],
                -strongest[group.rule][1],
                group.title,
            ),
        )
    )


def homonym_entry(proposal: HomonymProposal, labels: EntityLabels) -> HomonymEntry:
    reasons = " · ".join(proposal.reasons)
    pair = proposal.pair
    first = labels.entity(pair.first.identifier, reasons, None, pair.first.label)
    second = labels.entity(pair.second.identifier, reasons, None, pair.second.label)
    return HomonymEntry(first, second, proposal.confidence, proposal.reasons)


def review_queue(overview: InvestigationOverview) -> ReviewQueue:
    labels = EntityLabels(overview)
    return ReviewQueue(
        signal_groups(overview, labels),
        tuple(homonym_entry(proposal, labels) for proposal in overview.proposals),
        tuple(
            labels.entity(lead.identifier, lead.reason, None, lead.label)
            for lead in overview.unexpanded
        ),
        overview.signal_problem,
    )


def expansion_message(label: str, report: ExpansionReport) -> str:
    added = len(report.changes.new_entities)
    found = counted(added, "entité ajoutée", "entités ajoutées") if added else "rien de nouveau"
    message = f"Extension de {label} terminée : {found}"
    if report.cap_reached:
        message = f"{message}. {report.cap_message}"
    if report.failures:
        failures = counted(len(report.failures), "source en échec", "sources en échec")
        message = f"{message} ({failures})"
    return message


def notices_message(label: str, report: ExpansionReport) -> str:
    new = len(report.changes.new_notices)
    withdrawn = len(report.changes.withdrawn_notices)
    parts = []
    if new:
        parts.append(counted(new, "nouvelle annonce", "nouvelles annonces"))
    if withdrawn:
        parts.append(counted(withdrawn, "annonce retirée", "annonces retirées"))
    found = ", ".join(parts) if parts else "rien de nouveau"
    return f"Annonces de {label} rafraîchies : {found}"


def expansion_cancelled_message(label: str, report: ExpansionReport | None) -> str:
    added = 0 if report is None else len(report.changes.new_entities)
    if not added:
        return f"Extension de {label} annulée : rien n'a été ajouté"
    found = counted(added, "entité ajoutée", "entités ajoutées")
    return f"Extension de {label} annulée : {found} avant l'arrêt"


def notices_cancelled_message(label: str, report: ExpansionReport | None) -> str:
    return f"Rafraîchissement des annonces de {label} annulé"


@dataclass(frozen=True)
class RunningCollection:
    identifier: str
    title: str
    progress: ExpansionProgress = field(default_factory=ExpansionProgress)
    cancelling: bool = False

    @property
    def status_text(self) -> str:
        if self.cancelling:
            return CANCELLING_TEXT
        if self.progress == ExpansionProgress():
            return STARTING_TEXT
        return self.progress.summary

    @property
    def cancel_name(self) -> str:
        return f"Annuler : {self.title}"
