from dataclasses import dataclass, replace
from datetime import date
from typing import Self

from lacis.collectors.company_register import Company, CompanyRegister, CompanySearchPage
from lacis.graph.mapping import company_label, shown, spaced_siren
from lacis.storage.entities import company_identifier
from lacis.storage.graph_store import GraphStore

MINIMUM_QUERY_LENGTH = 3
SHORT_QUERY_MESSAGE = f"Saisissez au moins {MINIMUM_QUERY_LENGTH} caractères pour rechercher."
ACTIVE_STATUS = "Active"
CLOSED_STATUS = "Fermée"
IN_INVESTIGATION_TEXT = "Déjà dans l'enquête"
DETAIL_SEPARATOR = " · "
THOUSANDS_SEPARATOR = "\u00a0"


def query_problem(text: str) -> str:
    if len(text.strip()) < MINIMUM_QUERY_LENGTH:
        return SHORT_QUERY_MESSAGE
    return ""


def grouped(number: int) -> str:
    return f"{number:,}".replace(",", THOUSANDS_SEPARATOR)


def french_date(iso_date: str) -> str:
    try:
        return date.fromisoformat(iso_date).strftime("%d/%m/%Y")
    except ValueError:
        return iso_date


def place_of(company: Company) -> str:
    if company.head_office is None:
        return ""
    address = company.head_office.address
    parts = [shown(address.postcode), shown(address.city)]
    place = " ".join(part for part in parts if part)
    return place or (address.country or "")


@dataclass(frozen=True)
class RegisterSearchResult:
    company: Company
    in_investigation: bool

    @property
    def identifier(self) -> str:
        return company_identifier(self.company.siren)

    @property
    def title(self) -> str:
        return company_label(self.company)

    @property
    def status(self) -> str:
        return ACTIVE_STATUS if self.company.is_active else CLOSED_STATUS

    @property
    def details(self) -> str:
        company = self.company
        parts = [
            spaced_siren(company.siren),
            f"NAF {company.activity}" if company.activity else "",
            place_of(company),
            f"créée le {french_date(company.creation_date)}" if company.creation_date else "",
        ]
        return DETAIL_SEPARATOR.join(part for part in parts if part)

    @property
    def spoken(self) -> str:
        parts = [self.title, self.status, IN_INVESTIGATION_TEXT if self.in_investigation else ""]
        return ", ".join(part for part in parts if part)

    def added(self) -> Self:
        return replace(self, in_investigation=True)


@dataclass(frozen=True)
class RegisterSearchResults:
    page: CompanySearchPage
    results: tuple[RegisterSearchResult, ...]

    @property
    def count_text(self) -> str:
        total = self.page.total_results
        if total == 0:
            return "Aucun résultat dans le registre national"
        noun = "résultat" if total == 1 else "résultats"
        return f"{grouped(total)} {noun} dans le registre national"

    @property
    def truncation_text(self) -> str:
        if self.page.total_results <= len(self.results):
            return ""
        return (
            f"Les {len(self.results)} premiers sont affichés : "
            "précisez la recherche pour trouver les autres."
        )

    @property
    def announcement(self) -> str:
        return f"{self.count_text}. {self.truncation_text}".strip()


def search_register(
    company_register: CompanyRegister, graph_store: GraphStore, text: str
) -> RegisterSearchResults:
    page = company_register.search(text)
    results = tuple(
        RegisterSearchResult(
            company, graph_store.entity(company_identifier(company.siren)) is not None
        )
        for company in page.companies
    )
    return RegisterSearchResults(page, results)
