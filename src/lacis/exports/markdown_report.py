import re
from pathlib import Path
from urllib.parse import urlencode

from lacis.collectors.http_client import SOURCE_NAMES
from lacis.details import written_moment
from lacis.exports.report import (
    VERDICT_ORDER,
    Finding,
    ReportContent,
    ReportedEntity,
    ReportedNote,
    ReportedSignal,
)
from lacis.signals.facts import counted
from lacis.storage.expansion_log import ExpansionOperation, RecordedExpansion
from lacis.storage.responses import ResponseSource

MARKDOWN_SPECIAL = re.compile(r"([\\`*_\[\]<>|#~])")
SOURCE_DESCRIPTIONS = {
    ResponseSource.COMPANY_REGISTER: (
        "l'API Recherche d'entreprises de l'État, qui publie le registre national des "
        "entreprises : identité, établissements, dirigeants"
    ),
    ResponseSource.BODACC: (
        "le Bulletin officiel des annonces civiles et commerciales : créations, modifications, "
        "procédures collectives et radiations"
    ),
}
EVIDENCE_ANCHOR = "preuve-"
APPENDIX_INTRODUCTION = (
    "Chaque constat et chaque signal de ce rapport renvoie aux réponses des sources sur "
    "lesquelles il repose. L'empreinte SHA-256 permet de vérifier qu'une réponse conservée "
    "par Lacis n'a pas été modifiée."
)
SIGNALS_INTRODUCTION = (
    "Les signaux sont calculés par des règles explicables. Un signal est une piste qui "
    "mérite un examen, pas une accusation : il ne prouve aucune fraude."
)
FINDINGS_INTRODUCTION = (
    "Les constats sont les verdicts posés par l'enquêteur sur les entités, avec leurs raisons."
)
NO_RECORDED_EXPANSION = (
    "Aucune extension n'est enregistrée pour cette enquête : Lacis ne les enregistrait pas "
    "encore quand elle a été construite."
)
PUBLIC_DATA_RESERVE = (
    "Les données viennent de registres publics et décrivent leur état aux dates de collecte : "
    "elles ont pu changer depuis."
)
SIGNAL_RESERVE = (
    "Les signaux sont des pistes calculées par des règles : chacun demande un retour aux "
    "sources avant toute conclusion."
)
GROWTH_SENTENCE = (
    "Elle s'étend ensuite de proche en proche, en suivant les liens jusqu'à la profondeur "
    "choisie à chaque extension."
)
NO_VERDICT_SINGULAR = "entité n'a"
NO_VERDICT_PLURAL = "entités n'ont"
UNEXPANDED_SINGULAR = "entité n'a pas été étendue : ses autres liens restent inconnus"
UNEXPANDED_PLURAL = "entités n'ont pas été étendues : leurs autres liens restent inconnus"
FILTERED_RESERVE = (
    "Ce rapport ne couvre que la vue filtrée du graphe : les entités masquées par les filtres "
    "n'y figurent pas."
)


def escaped(text: str) -> str:
    return MARKDOWN_SPECIAL.sub(r"\\\1", text)


def quoted(text: str) -> list[str]:
    return [f"> {line}" if line else ">" for line in text.strip().splitlines()]


def written_depth(depth: int) -> str:
    return counted(depth, "niveau", "niveaux") if depth else ""


def within_sentence(fact: str) -> str:
    if fact[:2].isupper():
        return fact
    return fact[:1].lower() + fact[1:]


def entity_heading(entity: ReportedEntity) -> str:
    facts = [within_sentence(fact) for fact in entity.facts]
    return ", ".join([f"**{escaped(entity.label)}**", entity.kind_label, *facts])


def written_tags(tags: tuple[str, ...]) -> str:
    return ", ".join(escaped(tag) for tag in tags)


class MarkdownReport:
    def __init__(self, content: ReportContent) -> None:
        self.content = content
        self.numbers = {
            response.identifier: number
            for number, response in enumerate(content.evidence, start=1)
        }

    def text(self) -> str:
        lines = [
            *self.title(),
            *self.method(),
            *self.findings(),
            *self.signals(),
            *self.notes(),
            *self.reserves(),
            *self.appendix(),
        ]
        return "\n".join(lines).rstrip() + "\n"

    def title(self) -> list[str]:
        content = self.content
        investigation = content.investigation
        produced = (
            f"Rapport produit le {written_moment(content.produced_at)} par Lacis "
            f"{content.version}, à partir de l'enquête créée le "
            f"{written_moment(investigation.created_at)}."
        )
        return [
            f"# Rapport d'enquête : {escaped(investigation.name)}",
            "",
            f"**Question :** {escaped(investigation.question)}",
            "",
            f"{produced} {self.coverage()}",
            "",
            *self.summary(),
        ]

    def coverage(self) -> str:
        size = self.content.size
        entities = counted(size.entities, "entité", "entités")
        links = counted(size.links, "lien", "liens")
        if self.content.filtered:
            return (
                f"Il couvre la vue filtrée du graphe : {entities} sur {size.total_entities}, "
                f"et {links} entre elles."
            )
        return f"Il couvre toute l'enquête : {entities} et {links}."

    def summary(self) -> list[str]:
        content = self.content
        verdicts = [
            f"{verdict.label} : {len(found)}"
            for verdict in VERDICT_ORDER
            if (found := content.findings_with(verdict))
        ]
        lines = ["## Synthèse", ""]
        lines.append(f"- Constats : {', '.join(verdicts)}" if verdicts else "- Aucun constat.")
        lines.append(f"- {counted(len(content.signals), 'signal', 'signaux')}")
        lines.append(f"- {counted(len(content.notes), 'note', 'notes')}")
        return [*lines, ""]

    def method(self) -> list[str]:
        lines = ["## Méthode", ""]
        dates = self.content.collection_dates
        if dates is None:
            lines += ["Aucune donnée n'a encore été collectée pour cette enquête.", ""]
        else:
            first, last = dates
            period = f"du {written_moment(first)} au {written_moment(last)}"
            lines += [f"Les données viennent de sources publiques, collectées {period}.", ""]
        return [*lines, *self.sources(), *self.expansions(), *self.computation()]

    def sources(self) -> list[str]:
        if not self.content.sources:
            return []
        lines = ["### Sources", ""]
        lines += [
            f"- **{SOURCE_NAMES[use.source]}** : {SOURCE_DESCRIPTIONS[use.source]}."
            for use in self.content.sources
        ]
        lines += [
            "",
            "| Source | Requêtes | Échecs | Réponses conservées | Période de collecte |",
            "| --- | ---: | ---: | ---: | --- |",
        ]
        for use in self.content.sources:
            period = (
                f"du {written_moment(use.first_collected_at)} au "
                f"{written_moment(use.last_collected_at)}"
                if use.first_collected_at and use.last_collected_at
                else "aucune réponse"
            )
            lines.append(
                f"| {SOURCE_NAMES[use.source]} | {use.requests} | {use.failures} | "
                f"{use.responses} | {period} |"
            )
        return [*lines, ""]

    def expansions(self) -> list[str]:
        lines = ["### Extensions", ""]
        expansions = self.content.expansions
        if not expansions:
            lines += [NO_RECORDED_EXPANSION, ""]
        else:
            starts = sum(item.operation is ExpansionOperation.ADDED for item in expansions)
            added = counted(starts, "entité ajoutée", "entités ajoutées")
            lines += [
                f"L'enquête part de {added} depuis la recherche. {GROWTH_SENTENCE}",
                "",
                "| Date | Entité | Opération | Profondeur | Nouvelles entités | Remarques |",
                "| --- | --- | --- | ---: | ---: | --- |",
            ]
            lines += [self.expansion_row(expansion) for expansion in expansions]
            lines.append("")
        size = self.content.size
        if size.expanded or size.leads:
            lines += [
                f"{self.expanded_sentence()} {self.leads_sentence()}",
                "",
            ]
        return lines

    def expanded_sentence(self) -> str:
        size = self.content.size
        expanded = counted(size.expanded, "entité a été étendue", "entités ont été étendues")
        return f"{expanded} sur {size.expanded + size.leads}."

    def leads_sentence(self) -> str:
        leads = self.content.size.leads
        if not leads:
            return "Toutes les pistes ont été explorées."
        if leads == 1:
            return "La dernière reste une piste : ses liens n'ont pas été recherchés."
        return f"Les {leads} autres restent des pistes : leurs liens n'ont pas été recherchés."

    def expansion_row(self, expansion: RecordedExpansion) -> str:
        remarks = []
        if expansion.cap is not None:
            remarks.append(f"limite de {expansion.cap} nouvelles entités atteinte")
        if expansion.cancelled:
            remarks.append("annulée")
        if expansion.failures:
            remarks.append(counted(expansion.failures, "échec", "échecs"))
        return (
            f"| {written_moment(expansion.started_at)} | {escaped(expansion.label)} | "
            f"{expansion.operation.label} | {written_depth(expansion.depth)} | "
            f"{expansion.new_entities} | {', '.join(remarks)} |"
        )

    def computation(self) -> list[str]:
        computed_at = self.content.signals_computed_at
        if computed_at is None:
            text = (
                "Les signaux n'ont pas pu être calculés : le fichier de configuration des "
                "signaux n'est pas valide."
            )
        else:
            text = f"Les signaux ont été calculés le {written_moment(computed_at)}."
        return ["### Signaux", "", text, ""]

    def findings(self) -> list[str]:
        content = self.content
        lines = ["## Constats", "", FINDINGS_INTRODUCTION, ""]
        if not content.findings:
            return [*lines, "Aucune entité n'a encore de verdict.", ""]
        for verdict in VERDICT_ORDER:
            found = content.findings_with(verdict)
            if not found:
                continue
            lines += [f"### {verdict.label} ({len(found)})", ""]
            for finding in found:
                lines += self.finding(finding)
            lines.append("")
        if content.without_verdict:
            undecided = counted(content.without_verdict, NO_VERDICT_SINGULAR, NO_VERDICT_PLURAL)
            lines += [f"{undecided} pas encore de verdict.", ""]
        return lines

    def finding(self, finding: Finding) -> list[str]:
        verdict = finding.verdict
        lines = [f"- {entity_heading(finding.entity)}"]
        reason = escaped(verdict.reason.strip()) or "aucune raison donnée"
        lines.append(f"  - Raison : {reason}")
        if finding.entity.tags:
            lines.append(f"  - Tags : {written_tags(finding.entity.tags)}")
        lines.append(f"  - Verdict posé le {written_moment(verdict.decided_at)}")
        return lines

    def signals(self) -> list[str]:
        lines = ["## Signaux", "", SIGNALS_INTRODUCTION, ""]
        if not self.content.signals:
            return [*lines, "Aucun signal ne concerne les entités de ce rapport.", ""]
        for reported in self.content.signals:
            lines += self.signal(reported)
        return lines

    def signal(self, reported: ReportedSignal) -> list[str]:
        signal = reported.signal
        score = f"{signal.score:.2f}".replace(".", ",")
        lines = [
            f"### {escaped(signal.title)} : {escaped(reported.subject)}",
            "",
            f"Gravité {signal.severity.label.lower()}, score {score}.",
            "",
        ]
        if signal.explanation:
            lines += [escaped(signal.explanation), ""]
        if reported.entities:
            names = ", ".join(escaped(name) for name in reported.entities)
            lines += [f"Entités en cause : {names}.", ""]
        return lines

    def notes(self) -> list[str]:
        lines = ["## Notes", ""]
        if not self.content.notes:
            return [*lines, "Aucune note.", ""]
        for reported in self.content.notes:
            lines += self.note(reported)
        return lines

    def note(self, reported: ReportedNote) -> list[str]:
        entity = reported.entity
        return [
            f"### {escaped(entity.label)} ({entity.kind_label})",
            "",
            *quoted(reported.note.text),
            "",
            f"Note modifiée le {written_moment(reported.note.changed_at)}.",
            "",
        ]

    def reserves(self) -> list[str]:
        content = self.content
        items = [PUBLIC_DATA_RESERVE, SIGNAL_RESERVE]
        decisions = content.same_person_decisions
        items.append(
            "Deux personnes homonymes ne sont jamais fusionnées sans décision de l'enquêteur : "
            f"{counted(decisions, 'rapprochement a été décidé', 'rapprochements ont été décidés')}"
            "."
        )
        if content.failed_requests:
            items.append(
                f"{counted(content.failed_requests, 'requête a échoué', 'requêtes ont échoué')}"
                " pendant la collecte : des informations peuvent manquer."
            )
        if content.size.leads:
            items.append(f"{counted(content.size.leads, UNEXPANDED_SINGULAR, UNEXPANDED_PLURAL)}.")
        if content.filtered:
            items.append(FILTERED_RESERVE)
        return ["## Réserves", "", *(f"- {item}" for item in items), ""]

    def appendix(self) -> list[str]:
        lines = ["## Annexe : preuves", "", APPENDIX_INTRODUCTION, ""]
        if not self.content.evidence:
            return [*lines, "Aucun fait de ce rapport ne repose sur une réponse des sources.", ""]
        for response in self.content.evidence:
            number = self.numbers[response.identifier]
            entry = (
                f'- <a id="{EVIDENCE_ANCHOR}{number}"></a>**R{number}** : '
                f"{SOURCE_NAMES[response.source]}, collectée le "
                f"{written_moment(response.collected_at)}, <{response.url}>"
            )
            if response.parameters:
                entry += f", paramètres `{urlencode(sorted(response.parameters.items()))}`"
            lines.append(f"{entry}, empreinte SHA-256 `{response.fingerprint}`")
        return [*lines, ""]


def markdown_text(content: ReportContent) -> str:
    return MarkdownReport(content).text()


def write_markdown(text: str, destination: Path) -> None:
    destination.write_text(text, encoding="utf-8", newline="\n")
