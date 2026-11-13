import json
import re
from dataclasses import dataclass
from enum import Enum, StrEnum
from typing import Any

from lacis.collectors.endpoints import COMPANY_SEARCH_URL, MAXIMUM_COMPANIES_PER_PAGE
from lacis.collectors.http_client import SOURCE_NAMES, CollectionError, CollectorHttpClient
from lacis.storage.responses import ResponseSource, ResponseSummary, StoredResponse

SIREN_LENGTH = 9
SIRET_LENGTH = 14
NON_DIFFUSIBLE_MARK = "[NON-DIFFUSIBLE]"
PARTIALLY_DIFFUSIBLE_STATUS = "P"
CLOSED_STATES = {"C", "F"}
NATURAL_PERSON_TYPE = "personne physique"
IDENTIFIER_SEPARATORS = re.compile(r"[\s.\-]+")
SOURCE = ResponseSource.COMPANY_REGISTER


class Withheld(Enum):
    NON_DIFFUSIBLE = NON_DIFFUSIBLE_MARK


NON_DIFFUSIBLE = Withheld.NON_DIFFUSIBLE

type Disclosed = str | Withheld


class InvalidQueryError(ValueError):
    pass


class IdentifierKind(StrEnum):
    SIREN = "siren"
    SIRET = "siret"


@dataclass(frozen=True)
class Identifier:
    kind: IdentifierKind
    digits: str


def identifier_in(text: str) -> Identifier | None:
    digits = IDENTIFIER_SEPARATORS.sub("", text)
    if not digits.isdigit():
        return None
    if len(digits) == SIREN_LENGTH:
        return Identifier(IdentifierKind.SIREN, digits)
    if len(digits) == SIRET_LENGTH:
        return Identifier(IdentifierKind.SIRET, digits)
    return None


def siren_of(text: str) -> str:
    identifier = identifier_in(text)
    if identifier is None or identifier.kind is not IdentifierKind.SIREN:
        raise InvalidQueryError(f"« {text.strip()} » n'est pas un SIREN : il faut 9 chiffres.")
    return identifier.digits


def disclosed(value: object) -> Disclosed | None:
    if value is None or value == "":
        return None
    if value == NON_DIFFUSIBLE_MARK:
        return NON_DIFFUSIBLE
    return str(value)


def optional_text(value: object) -> str | None:
    shown = disclosed(value)
    return shown if isinstance(shown, str) else None


@dataclass(frozen=True)
class Address:
    number: Disclosed | None
    street_type: Disclosed | None
    street_name: Disclosed | None
    complement: Disclosed | None
    postcode: Disclosed | None
    city: Disclosed | None
    city_code: str | None
    country: str | None
    full_text: Disclosed | None

    @property
    def street_withheld(self) -> bool:
        return NON_DIFFUSIBLE in (self.number, self.street_type, self.street_name)


@dataclass(frozen=True)
class Establishment:
    siret: str
    is_head_office: bool
    is_open: bool
    address: Address
    activity: str | None
    creation_date: str | None
    closing_date: str | None
    trade_name: Disclosed | None
    diffusible: bool


@dataclass(frozen=True)
class NaturalPersonDirector:
    last_name: Disclosed | None
    first_names: Disclosed | None
    birth_month: Disclosed | None
    role: str | None
    nationality: Disclosed | None

    @property
    def diffusible(self) -> bool:
        return NON_DIFFUSIBLE not in (self.last_name, self.first_names)


@dataclass(frozen=True)
class LegalPersonDirector:
    name: Disclosed | None
    siren: str | None
    role: str | None


type Director = NaturalPersonDirector | LegalPersonDirector


@dataclass(frozen=True)
class Company:
    siren: str
    name: Disclosed | None
    acronym: Disclosed | None
    is_active: bool
    diffusible: bool
    legal_form: str | None
    activity: str | None
    creation_date: str | None
    closing_date: str | None
    head_office: Establishment | None
    matching_establishments: tuple[Establishment, ...]
    establishment_count: int
    open_establishment_count: int
    directors: tuple[Director, ...]

    @property
    def lists_every_establishment(self) -> bool:
        return len(self.matching_establishments) >= self.establishment_count


@dataclass(frozen=True)
class CompanySearchPage:
    companies: tuple[Company, ...]
    page: int
    per_page: int
    total_results: int
    total_pages: int
    response: ResponseSummary

    @property
    def has_next_page(self) -> bool:
        return self.page < self.total_pages


@dataclass(frozen=True)
class SourcedCompany:
    company: Company
    response: ResponseSummary


def address_from(record: dict[str, Any]) -> Address:
    city = record.get("libelle_commune") or record.get("libelle_commune_etranger")
    return Address(
        number=disclosed(record.get("numero_voie")),
        street_type=disclosed(record.get("type_voie")),
        street_name=disclosed(record.get("libelle_voie")),
        complement=disclosed(record.get("complement_adresse")),
        postcode=disclosed(record.get("code_postal")),
        city=disclosed(city),
        city_code=optional_text(record.get("commune")),
        country=optional_text(record.get("libelle_pays_etranger")),
        full_text=disclosed(record.get("adresse")),
    )


def establishment_from(record: dict[str, Any]) -> Establishment:
    return Establishment(
        siret=str(record["siret"]),
        is_head_office=bool(record.get("est_siege")),
        is_open=record.get("etat_administratif") not in CLOSED_STATES,
        address=address_from(record),
        activity=optional_text(record.get("activite_principale")),
        creation_date=optional_text(record.get("date_creation")),
        closing_date=optional_text(record.get("date_fermeture")),
        trade_name=disclosed(record.get("nom_commercial")),
        diffusible=record.get("statut_diffusion_etablissement") != PARTIALLY_DIFFUSIBLE_STATUS,
    )


def director_from(record: dict[str, Any]) -> Director:
    if record.get("type_dirigeant") == NATURAL_PERSON_TYPE:
        return NaturalPersonDirector(
            last_name=disclosed(record.get("nom")),
            first_names=disclosed(record.get("prenoms")),
            birth_month=disclosed(record.get("date_de_naissance")),
            role=optional_text(record.get("qualite")),
            nationality=disclosed(record.get("nationalite")),
        )
    return LegalPersonDirector(
        name=disclosed(record.get("denomination")),
        siren=optional_text(record.get("siren")),
        role=optional_text(record.get("qualite")),
    )


def company_from(record: dict[str, Any]) -> Company:
    head_office = record.get("siege")
    return Company(
        siren=str(record["siren"]),
        name=disclosed(record.get("nom_complet") or record.get("nom_raison_sociale")),
        acronym=disclosed(record.get("sigle")),
        is_active=record.get("etat_administratif") not in CLOSED_STATES,
        diffusible=record.get("statut_diffusion") != PARTIALLY_DIFFUSIBLE_STATUS,
        legal_form=optional_text(record.get("nature_juridique")),
        activity=optional_text(record.get("activite_principale")),
        creation_date=optional_text(record.get("date_creation")),
        closing_date=optional_text(record.get("date_fermeture")),
        head_office=establishment_from(head_office) if isinstance(head_office, dict) else None,
        matching_establishments=tuple(
            establishment_from(item) for item in record.get("matching_etablissements") or []
        ),
        establishment_count=int(record.get("nombre_etablissements") or 0),
        open_establishment_count=int(record.get("nombre_etablissements_ouverts") or 0),
        directors=tuple(director_from(item) for item in record.get("dirigeants") or []),
    )


def unreadable_response_message() -> str:
    return f"La réponse du service {SOURCE_NAMES[SOURCE]} est illisible. Réessayez plus tard."


def search_page_from(stored_response: StoredResponse) -> CompanySearchPage:
    try:
        payload = json.loads(stored_response.body)
        return CompanySearchPage(
            companies=tuple(company_from(record) for record in payload["results"]),
            page=int(payload["page"]),
            per_page=int(payload["per_page"]),
            total_results=int(payload["total_results"]),
            total_pages=int(payload["total_pages"]),
            response=stored_response.summary,
        )
    except (KeyError, TypeError, ValueError) as unreadable:
        raise CollectionError(unreadable_response_message(), SOURCE, None) from unreadable


class CompanyRegister:
    def __init__(
        self,
        http_client: CollectorHttpClient,
        results_per_page: int = MAXIMUM_COMPANIES_PER_PAGE,
    ) -> None:
        self.http_client = http_client
        self.results_per_page = results_per_page

    def search(self, text: str, page: int = 1, *, refresh: bool = False) -> CompanySearchPage:
        query = text.strip()
        if not query:
            raise InvalidQueryError(
                "Saisissez un nom, un SIREN, un SIRET, un dirigeant ou une adresse."
            )
        identifier = identifier_in(query)
        if identifier is not None:
            query = identifier.digits
        return self.search_page({"q": query}, page, refresh)

    def search_director(
        self, last_name: str, first_names: str = "", page: int = 1, *, refresh: bool = False
    ) -> CompanySearchPage:
        parameters = {"nom_personne": last_name.strip()}
        if not parameters["nom_personne"]:
            raise InvalidQueryError("Saisissez le nom du dirigeant.")
        if first_names.strip():
            parameters["prenoms_personne"] = first_names.strip()
        return self.search_page(parameters, page, refresh)

    def company(self, siren: str, *, refresh: bool = False) -> Company | None:
        sourced_company = self.sourced_company(siren, refresh=refresh)
        return sourced_company.company if sourced_company is not None else None

    def sourced_company(self, siren: str, *, refresh: bool = False) -> SourcedCompany | None:
        digits = siren_of(siren)
        search_page = self.search_page({"q": digits}, 1, refresh)
        for company in search_page.companies:
            if company.siren == digits:
                return SourcedCompany(company, search_page.response)
        return None

    def search_page(
        self, parameters: dict[str, str], page: int, refresh: bool
    ) -> CompanySearchPage:
        if page < 1:
            raise InvalidQueryError(f"La page {page} n'existe pas : les pages commencent à 1.")
        stored_response = self.http_client.get(
            SOURCE,
            COMPANY_SEARCH_URL,
            {**parameters, "page": str(page), "per_page": str(self.results_per_page)},
            refresh=refresh,
        )
        return search_page_from(stored_response)
