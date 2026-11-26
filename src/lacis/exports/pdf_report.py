import base64
import html
import importlib
import re
from pathlib import Path
from types import ModuleType

import markdown
from markdown.extensions.tables import TableExtension

from lacis import __version__
from lacis.design.tokens import LIGHT_THEME
from lacis.exports.html_graph import colour_variables
from lacis.exports.markdown_report import markdown_text
from lacis.exports.report import ReportContent
from lacis.product import RESOURCE_DIRECTORY

PDF_VARIANT = "pdf/ua-1"
FONT_DIRECTORY = RESOURCE_DIRECTORY / "fonts"
STYLE_FILE = RESOURCE_DIRECTORY / "export" / "report.css"
FONT_FILES = (("Inter-Regular.ttf", 400), ("Inter-Medium.ttf", 500), ("Inter-SemiBold.ttf", 600))
ANCHOR = re.compile(r'<a id="(preuve-\d+)"></a>')
ANCHOR_TOKEN = re.compile(r"⟦(preuve-\d+)⟧")
RAW_HTML_PROCESSORS = ("html_block",)
REMOTE_INLINE_PATTERNS = ("html", "image_link", "image_reference", "short_image_ref")
UNAVAILABLE_TEXT = (
    "l'export PDF a besoin de WeasyPrint et de la bibliothèque Pango, "
    "qui ne sont pas disponibles sur cet ordinateur"
)
TITLE_PREFIX = "Rapport d'enquête : "


class PdfUnavailableError(OSError):
    pass


def font_faces() -> str:
    faces = []
    for file_name, weight in FONT_FILES:
        data = base64.b64encode((FONT_DIRECTORY / file_name).read_bytes()).decode("ascii")
        faces.append(
            f'@font-face{{font-family:"Inter";font-weight:{weight};'
            f"src:url(data:font/ttf;base64,{data});}}"
        )
    return "".join(faces)


def report_body(text: str) -> str:
    converter = markdown.Markdown(extensions=[TableExtension()], output_format="html")
    for processor in RAW_HTML_PROCESSORS:
        converter.preprocessors.deregister(processor)
    for pattern in REMOTE_INLINE_PATTERNS:
        converter.inlinePatterns.deregister(pattern)
    tokenized = ANCHOR.sub(lambda found: f"⟦{found[1]}⟧", text)
    return ANCHOR_TOKEN.sub(r'<a id="\1"></a>', converter.convert(tokenized))


def report_html(content: ReportContent) -> str:
    title = html.escape(f"{TITLE_PREFIX}{content.investigation.name}")
    style = "".join(
        [
            font_faces(),
            f":root{{{colour_variables(LIGHT_THEME.colours)}}}",
            STYLE_FILE.read_text(encoding="utf-8"),
        ]
    )
    return (
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
        f"<title>{title}</title>"
        '<meta name="author" content="Lacis">'
        f'<meta name="generator" content="Lacis {html.escape(__version__)}">'
        f"<style>{style}</style></head>"
        f"<body>{report_body(markdown_text(content))}</body></html>"
    )


def weasyprint_module() -> ModuleType:
    return importlib.import_module("weasyprint")


def write_pdf_report(content: ReportContent, destination: Path) -> None:
    try:
        weasyprint = weasyprint_module()
    except (ImportError, OSError) as problem:
        raise PdfUnavailableError(UNAVAILABLE_TEXT) from problem
    document = weasyprint.HTML(string=report_html(content))
    document.write_pdf(destination, pdf_variant=PDF_VARIANT)
