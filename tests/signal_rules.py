import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime

from lacis.signals.context import InvestigationContext
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.signal import Finding, Severity
from lacis.storage.entities import (
    CollectedEntity,
    EntityKind,
    address_identifier,
    mandate_link,
    person_identifier,
    registered_office_link,
)
from lacis.storage.graph_store import GraphStore
from lacis.storage.notices import CollectedNotice, NoticeFamily, NoticeRole, NoticeStore
from lacis.storage.responses import CollectedResponse, ResponseSource, ResponseStore

MINIMUM_LINKS = Threshold("minimum_links", ThresholdKind.WHOLE_NUMBER, minimum=1)
SHARE = Threshold("share", ThresholdKind.NUMBER, minimum=0, maximum=1)
INCLUDE_PROBABLE = Threshold("include_probable", ThresholdKind.SWITCH)
EXCLUDED_ROLES = Threshold("excluded_roles", ThresholdKind.TEXTS)

WELL_CONNECTED_DEFAULTS = """
[rules.well_connected]
enabled = true
severity = "medium"
weight = 1.0
minimum_links = 2
share = 0.5
include_probable = false
excluded_roles = ["Commissaire aux comptes"]
"""

FIXED_DEFAULTS = """
[rules.fixed]
enabled = true
severity = "low"
weight = 0.5
"""


@dataclass(frozen=True)
class WellConnectedRule:
    name: str = "well_connected"
    title: str = "Entreprise très reliée"
    thresholds: tuple[Threshold, ...] = (MINIMUM_LINKS, SHARE, INCLUDE_PROBABLE, EXCLUDED_ROLES)

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        minimum_links = settings.whole_number(MINIMUM_LINKS.name)
        findings: list[Finding] = []
        for company in context.entities_of(EntityKind.COMPANY):
            neighbours = context.neighbours(company.identifier)
            if len(neighbours) < minimum_links:
                continue
            findings.append(
                Finding(
                    company.identifier,
                    len(neighbours) / (minimum_links * 2),
                    f"{company.label} est reliée à {len(neighbours)} entités.",
                    tuple(neighbour.identifier for neighbour in neighbours) * 2,
                )
            )
        return findings


@dataclass(frozen=True)
class FixedRule:
    findings: tuple[Finding, ...]
    name: str = "fixed"
    title: str = "Règle fixe"
    thresholds: tuple[Threshold, ...] = ()

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        return list(self.findings)


def strong_finding(subject: str, strength: float = 1.0) -> Finding:
    return Finding(subject, strength, f"{subject} se démarque.", (), Severity.HIGH)


COLLECTED_AT = datetime(2026, 11, 2, 23, 11, tzinfo=UTC)
JEAN_DUPONT = person_identifier("DUPONT", "Jean", "1980-05")
LILAS_ADDRESS = address_identifier("12 rue des Lilas 31000 Toulouse")
ACME = "company:111111111"
DUPONT_SERVICES = "company:222222222"
LILAS_BOULANGERIE = "company:555555555"


def fill_small_investigation(connection: sqlite3.Connection) -> None:
    response = ResponseStore(connection).save(
        CollectedResponse(
            ResponseSource.COMPANY_REGISTER,
            "https://recherche-entreprises.api.gouv.fr/search",
            b"{}",
            COLLECTED_AT,
            {"q": "lilas"},
        )
    )
    graph_store = GraphStore(connection)
    for identifier, label in (
        (ACME, "ACME PLOMBERIE"),
        (DUPONT_SERVICES, "DUPONT SERVICES"),
        (LILAS_BOULANGERIE, "LILAS BOULANGERIE"),
        (JEAN_DUPONT, "Jean DUPONT"),
        (LILAS_ADDRESS, "12 RUE DES LILAS 31000 TOULOUSE"),
    ):
        graph_store.save_entity(CollectedEntity(identifier, label), response)
    for link in (
        mandate_link(JEAN_DUPONT, ACME, "Gérant"),
        mandate_link(JEAN_DUPONT, DUPONT_SERVICES, "Gérant"),
        registered_office_link(ACME, LILAS_ADDRESS),
        registered_office_link(DUPONT_SERVICES, LILAS_ADDRESS),
    ):
        graph_store.save_link(link, response)
    NoticeStore(connection).save_notice(
        CollectedNotice(
            "B202300150001",
            NoticeFamily.REMOVAL,
            date(2023, 1, 20),
            "GREFFE DU TRIBUNAL DE COMMERCE DE TOULOUSE",
            "Radiation du registre du commerce et des sociétés",
            "",
            {DUPONT_SERVICES: NoticeRole.SUBJECT},
        ),
        response,
    )


DEFAULTS_BY_RULE = {"well_connected": WELL_CONNECTED_DEFAULTS, "fixed": FIXED_DEFAULTS}


def defaults_for(rule_names: list[str]) -> str:
    return "".join(DEFAULTS_BY_RULE[name] for name in rule_names)
