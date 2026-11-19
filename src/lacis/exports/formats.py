from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from lacis.exports.json_export import ExportScope, InvestigationExport, write_json
from lacis.exports.markdown_report import markdown_text, write_markdown
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


@dataclass(frozen=True)
class ExportFormat:
    key: str
    label: str
    menu_text: str
    description: str
    extension: str
    write: Writer


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
EXPORT_FORMATS = (MARKDOWN_REPORT_FORMAT, JSON_FORMAT)


def export_format(key: str) -> ExportFormat:
    return next(candidate for candidate in EXPORT_FORMATS if candidate.key == key)
