from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lacis.exports.gexf import write_gexf
from lacis.exports.graph_snapshot import graph_snapshot
from lacis.exports.html_graph import HtmlGraph, write_html_graph
from lacis.exports.json_export import ExportScope, InvestigationExport, write_json
from lacis.exports.maltego import write_maltego_csv
from lacis.exports.markdown_report import markdown_text, write_markdown
from lacis.exports.obsidian_vault import ObsidianVault
from lacis.exports.pdf_report import write_pdf_report
from lacis.exports.report import ReportBuilder
from lacis.signals.store import SignalReport
from lacis.storage.investigations import OpenInvestigation

type Writer = Callable[[OpenInvestigation, SignalReport | None, ExportScope, Path, datetime], None]


def export_json(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    export = InvestigationExport(opened.connection, report, scope)
    write_json(export.document(opened.investigation, exported_at), destination)


def export_markdown_report(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    builder = ReportBuilder(opened.connection, report, scope)
    write_markdown(markdown_text(builder.content(opened.investigation, exported_at)), destination)


def export_pdf_report(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    builder = ReportBuilder(opened.connection, report, scope)
    write_pdf_report(builder.content(opened.investigation, exported_at), destination)


def export_obsidian_vault(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    vault = ObsidianVault(opened.connection, report, scope)
    vault.write(opened.investigation, destination, exported_at)


def export_gexf(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    snapshot = graph_snapshot(opened.connection, report, scope)
    write_gexf(snapshot, opened.investigation, destination, exported_at)


def export_maltego(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    write_maltego_csv(graph_snapshot(opened.connection, report, scope), destination)


def export_html_graph(
    opened: OpenInvestigation,
    report: SignalReport | None,
    scope: ExportScope,
    destination: Path,
    exported_at: datetime,
) -> None:
    graph = HtmlGraph(opened.connection, report, scope)
    write_html_graph(graph, opened.investigation, destination, exported_at)


@dataclass(frozen=True)
class ExportFormat:
    key: str
    label: str
    menu_text: str
    description: str
    extension: str
    write: Writer
    folder: bool = False


JSON_FORMAT = ExportFormat(
    "json",
    "JSON",
    "&JSON…",
    "Export complet et sans perte : entités, liens, signaux, notes, verdicts et provenance",
    ".json",
    export_json,
)
MARKDOWN_REPORT_FORMAT = ExportFormat(
    "markdown_report",
    "Rapport Markdown",
    "&Rapport Markdown…",
    "Rapport lisible sans Lacis : question, méthode, constats, signaux, notes et réserves",
    ".md",
    export_markdown_report,
)
OBSIDIAN_FORMAT = ExportFormat(
    "obsidian",
    "Coffre Obsidian",
    "&Obsidian…",
    "Un dossier de notes liées : une note par entité et une note d'index",
    "",
    export_obsidian_vault,
    folder=True,
)
GEXF_FORMAT = ExportFormat(
    "gexf",
    "Gephi (GEXF)",
    "&Gephi…",
    "Le graphe pour Gephi, avec le type, les signaux et le score de chaque entité",
    ".gexf",
    export_gexf,
)
MALTEGO_FORMAT = ExportFormat(
    "maltego",
    "Maltego (CSV)",
    "&Maltego…",
    "Une ligne par lien, avec les types d'entités de Maltego, à importer comme tableau",
    ".csv",
    export_maltego,
)
HTML_GRAPH_FORMAT = ExportFormat(
    "html_graph",
    "Graphe HTML",
    "Format &HTML…",
    "Une page autonome pour explorer le graphe sans Lacis, même hors ligne",
    ".html",
    export_html_graph,
)
PDF_REPORT_FORMAT = ExportFormat(
    "pdf_report",
    "Rapport PDF",
    "Rapport &PDF…",
    "Le rapport mis en page, balisé pour les lecteurs d'écran, prêt à envoyer",
    ".pdf",
    export_pdf_report,
)
EXPORT_FORMATS = (
    MARKDOWN_REPORT_FORMAT,
    PDF_REPORT_FORMAT,
    JSON_FORMAT,
    OBSIDIAN_FORMAT,
    GEXF_FORMAT,
    MALTEGO_FORMAT,
    HTML_GRAPH_FORMAT,
)


def export_format(key: str) -> ExportFormat:
    return next(candidate for candidate in EXPORT_FORMATS if candidate.key == key)
