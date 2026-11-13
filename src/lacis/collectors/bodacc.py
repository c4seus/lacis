import json
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from typing import Any

from lacis.collectors.company_register import SIREN_LENGTH, siren_of
from lacis.collectors.endpoints import BODACC_RECORDS_URL, MAXIMUM_NOTICES_PER_PAGE
from lacis.collectors.http_client import SOURCE_NAMES, CollectionError, CollectorHttpClient
from lacis.storage.comparison_keys import normalise_text
from lacis.storage.entities import company_identifier, remove_spaces
from lacis.storage.notices import CollectedNotice, NoticeFamily, NoticeRole, OfficeTransfer
from lacis.storage.responses import ResponseSource, ResponseSummary, StoredResponse

SOURCE = ResponseSource.BODACC
DEFAULT_MAXIMUM_PAGES = 10
SUMMARY_LENGTH = 400
NOTICE_URL = "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:{identifier}"
FAMILY_OF_CODE = {
    "creation": NoticeFamily.CREATION,
    "immatriculation": NoticeFamily.REGISTRATION,
    "modification": NoticeFamily.AMENDMENT,
    "collective": NoticeFamily.INSOLVENCY,
    "conciliation": NoticeFamily.CONCILIATION,
    "retablissement_professionnel": NoticeFamily.PROFESSIONAL_RECOVERY,
    "vente": NoticeFamily.SALE,
    "dpc": NoticeFamily.ACCOUNTS,
    "radiation": NoticeFamily.REMOVAL,
    "divers": NoticeFamily.MISCELLANEOUS,
}
FAMILY_OF_LABEL_WORD = (
    ("RETABLISSEMENT", NoticeFamily.PROFESSIONAL_RECOVERY),
    ("CONCILIATION", NoticeFamily.CONCILIATION),
    ("COLLECTIVE", NoticeFamily.INSOLVENCY),
    ("RADIATION", NoticeFamily.REMOVAL),
    ("COMPTES", NoticeFamily.ACCOUNTS),
    ("VENTE", NoticeFamily.SALE),
    ("CESSION", NoticeFamily.SALE),
    ("IMMATRICULATION", NoticeFamily.REGISTRATION),
    ("CREATION", NoticeFamily.CREATION),
    ("MODIFICATION", NoticeFamily.AMENDMENT),
)
JUDGMENT_FAMILIES = frozenset(
    {
        NoticeFamily.INSOLVENCY,
        NoticeFamily.CONCILIATION,
        NoticeFamily.PROFESSIONAL_RECOVERY,
    }
)
DEED_FAMILIES = frozenset({NoticeFamily.CREATION, NoticeFamily.REGISTRATION, NoticeFamily.SALE})
ROLE_FIELDS = (
    ("listepersonnes", NoticeRole.SUBJECT),
    ("listeprecedentexploitant", NoticeRole.PREVIOUS_OPERATOR),
    ("listeprecedentproprietaire", NoticeRole.PREVIOUS_OWNER),
)
TRANSFER_FIELDS = ("modificationsgenerales", "radiationaurcs", "divers", "acte")
ABROAD_WORDS = (" ETRANGER ", " HORS DE FRANCE ")
COUNTRIES = (
    "Allemagne",
    "Andorre",
    "Autriche",
    "Belgique",
    "Bulgarie",
    "Canada",
    "Chypre",
    "Croatie",
    "Danemark",
    "Émirats arabes unis",
    "Espagne",
    "Estonie",
    "États-Unis",
    "Finlande",
    "Grèce",
    "Hong Kong",
    "Hongrie",
    "Irlande",
    "Israël",
    "Italie",
    "Lettonie",
    "Lituanie",
    "Luxembourg",
    "Malte",
    "Maroc",
    "Monaco",
    "Pays-Bas",
    "Pologne",
    "Portugal",
    "République tchèque",
    "Roumanie",
    "Royaume-Uni",
    "Singapour",
    "Slovaquie",
    "Slovénie",
    "Suède",
    "Suisse",
    "Tunisie",
)
COUNTRY_OF_NORMALISED_NAME = {normalise_text(country): country for country in COUNTRIES}
DOMESTIC_COUNTRY = "FRANCE"
EFFECTIVE_DATE_KEYS = (
    "dateEffet",
    "dateCessationActivitePM",
    "dateCessationActivitePP",
    "dateCommencementActivite",
    "dateDebutActivite",
)
MONTHS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)
MONTH_OF_NAME = {normalise_text(month): number for number, month in enumerate(MONTHS, 1)}
WRITTEN_DATE = re.compile(r"\b(\d{1,2})(?:er)? ([A-Za-zéû]+) (\d{4})\b")
NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
PARENTHESISED_TEXT = re.compile(r"\(([^()]+)\)")


def decoded(value: object) -> object:
    if isinstance(value, str) and value.strip()[:1] in {"{", "["}:
        try:
            return json.loads(value)
        except ValueError:
            return value
    return value


def strings_in(value: object) -> Iterator[str]:
    if isinstance(value, str):
        if value.strip():
            yield value.strip()
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)


def values_of(value: object, key: str) -> Iterator[str]:
    if isinstance(value, dict):
        for name, item in value.items():
            if name == key and isinstance(item, str) and item.strip():
                yield item.strip()
            else:
                yield from values_of(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from values_of(item, key)


def first_value(value: object, keys: tuple[str, ...]) -> str:
    for key in keys:
        for found in values_of(value, key):
            return found
    return ""


def shortened(text: str) -> str:
    single_line = " ".join(text.split())
    if len(single_line) <= SUMMARY_LENGTH:
        return single_line
    return single_line[: SUMMARY_LENGTH - 1].rstrip() + "…"


def family_of(code: str, label: str) -> NoticeFamily:
    family = FAMILY_OF_CODE.get(code.strip().lower())
    if family is not None:
        return family
    words = normalise_text(f"{label} {code}")
    for word, candidate in FAMILY_OF_LABEL_WORD:
        if word in words:
            return candidate
    return NoticeFamily.MISCELLANEOUS


def judgment_summary(judgment: object) -> str:
    nature = first_value(judgment, ("nature", "famille"))
    complement = first_value(judgment, ("complementJugement",))
    if complement and normalise_text(complement) != normalise_text(nature):
        return f"{nature}. {complement}" if nature else complement
    return nature


def accounts_summary(deposit: object) -> str:
    kind = first_value(deposit, ("typeDepot", "descriptif"))
    closing = first_value(deposit, ("dateCloture",))
    if kind and closing:
        return f"{kind} (clôture au {closing})"
    return kind or (f"Clôture au {closing}" if closing else "")


def summary_of(family: NoticeFamily, record: dict[str, Any]) -> str:
    if family in JUDGMENT_FAMILIES:
        return judgment_summary(decoded(record.get("jugement")))
    if family is NoticeFamily.ACCOUNTS:
        return accounts_summary(decoded(record.get("depot")))
    if family is NoticeFamily.REMOVAL:
        removal = decoded(record.get("radiationaurcs"))
        keys = ("radiationPM", "radiationPP", "commentaire", "descriptif")
        return first_value(removal, keys) or next(strings_in(removal), "")
    if family is NoticeFamily.AMENDMENT:
        return first_value(decoded(record.get("modificationsgenerales")), ("descriptif",))
    if family in DEED_FAMILIES:
        keys = ("descriptif", "categorieVente", "categorieImmatriculation", "categorieCreation")
        return first_value(decoded(record.get("acte")), keys)
    return first_value(decoded(record.get("divers")), ("texte", "descriptif"))


def sirens_in(value: object) -> list[str]:
    sirens = []
    for number in values_of(value, "numeroIdentification"):
        digits = remove_spaces(number)[-9:]
        if digits.isdigit() and len(digits) == SIREN_LENGTH:
            sirens.append(digits)
    return sirens


def roles_in(record: dict[str, Any]) -> dict[str, NoticeRole]:
    roles: dict[str, NoticeRole] = {}
    for field_name, role in ROLE_FIELDS:
        for siren in sirens_in(decoded(record.get(field_name))):
            roles.setdefault(siren, role)
    other_role = NoticeRole.MENTIONED if roles else NoticeRole.SUBJECT
    registered = record.get("registre") or []
    for number in registered if isinstance(registered, list) else [registered]:
        digits = remove_spaces(str(number))
        if digits.isdigit() and len(digits) == SIREN_LENGTH:
            roles.setdefault(digits, other_role)
    return roles


def valid_date(year: str, month: int | str, day: str) -> date | None:
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        return None


def dates_in_text(text: str) -> Iterator[date | None]:
    for match in WRITTEN_DATE.finditer(text):
        month = MONTH_OF_NAME.get(normalise_text(match[2]))
        if month is not None:
            yield valid_date(match[3], month, match[1])
    for match in NUMERIC_DATE.finditer(text):
        yield valid_date(match[3], match[2], match[1])
    for match in ISO_DATE.finditer(text):
        yield valid_date(match[1], match[2], match[3])


def date_in_text(text: str) -> date | None:
    return next((found for found in dates_in_text(text) if found is not None), None)


def country_in(details: list[object], texts: list[str]) -> str | None:
    for detail in details:
        for country in values_of(detail, "pays"):
            normalised_country = normalise_text(country)
            if normalised_country != DOMESTIC_COUNTRY:
                return COUNTRY_OF_NORMALISED_NAME.get(normalised_country, country)
    candidates = [group for text in texts for group in PARENTHESISED_TEXT.findall(text)]
    candidates.extend(texts)
    for candidate in candidates:
        words = f" {normalise_text(candidate)} "
        for normalised_country, country in COUNTRY_OF_NORMALISED_NAME.items():
            if f" {normalised_country} " in words:
                return country
    return None


def effective_date_in(details: list[object], texts: list[str]) -> date | None:
    for detail in details:
        stated = date_in_text(first_value(detail, EFFECTIVE_DATE_KEYS))
        if stated is not None:
            return stated
    for text in texts:
        found = date_in_text(text)
        if found is not None:
            return found
    return None


def office_transfer_in(record: dict[str, Any], published_on: date) -> OfficeTransfer | None:
    details = [decoded(record.get(field_name)) for field_name in TRANSFER_FIELDS]
    texts = [text for detail in details for text in strings_in(detail)]
    words = f" {normalise_text(' '.join(texts))} "
    if " TRANSFERT " not in words or " SIEGE " not in words:
        return None
    country = country_in([*details, decoded(record.get("listepersonnes"))], texts)
    if country is None and not any(word in words for word in ABROAD_WORDS):
        return None
    effective_on = effective_date_in(details, texts)
    if effective_on is None:
        return OfficeTransfer(country, published_on, effective_date_stated=False)
    return OfficeTransfer(country, effective_on, effective_date_stated=True)


@dataclass(frozen=True)
class BodaccNotice:
    identifier: str
    family: NoticeFamily
    family_label: str
    published_on: date
    court: str
    judgment: str
    judgment_date: date | None
    summary: str
    company_roles: dict[str, NoticeRole]
    url: str
    office_transfer: OfficeTransfer | None
    response: ResponseSummary

    def collected_notice(self) -> CollectedNotice:
        return CollectedNotice(
            identifier=self.identifier,
            family=self.family,
            published_on=self.published_on,
            court=self.court,
            summary=self.summary,
            judgment=self.judgment,
            companies={
                company_identifier(siren): role for siren, role in self.company_roles.items()
            },
            office_transfer=self.office_transfer,
        )


def text_of(record: dict[str, Any], key: str) -> str:
    value = record.get(key)
    return str(value).strip() if value is not None else ""


def notice_from(record: dict[str, Any], response: ResponseSummary) -> BodaccNotice:
    identifier = text_of(record, "id")
    if not identifier:
        raise ValueError("A notice has no identifier")
    family_label = text_of(record, "familleavis_lib")
    family = family_of(text_of(record, "familleavis"), family_label)
    published_on = date.fromisoformat(text_of(record, "dateparution")[:10])
    judgment = decoded(record.get("jugement")) if family in JUDGMENT_FAMILIES else None
    judgment_date = first_value(judgment, ("date",))
    summary = summary_of(family, record) or text_of(record, "typeavis_lib") or family_label
    return BodaccNotice(
        identifier=identifier,
        family=family,
        family_label=family_label,
        published_on=published_on,
        court=text_of(record, "tribunal"),
        judgment=first_value(judgment, ("nature", "famille")),
        judgment_date=date_in_text(judgment_date),
        summary=shortened(summary),
        company_roles=roles_in(record),
        url=text_of(record, "url_complete") or NOTICE_URL.format(identifier=identifier),
        office_transfer=office_transfer_in(record, published_on),
        response=response,
    )


@dataclass(frozen=True)
class NoticePage:
    records: tuple[dict[str, Any], ...]
    total_count: int
    response: ResponseSummary


@dataclass(frozen=True)
class CompanyNotices:
    siren: str
    pages: tuple[NoticePage, ...]

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(record for page in self.pages for record in page.records)

    @property
    def total_count(self) -> int:
        return self.pages[-1].total_count

    @property
    def is_complete(self) -> bool:
        return len(self.records) >= self.total_count

    @property
    def notices(self) -> tuple[BodaccNotice, ...]:
        try:
            return tuple(
                notice_from(record, page.response)
                for page in self.pages
                for record in page.records
            )
        except (TypeError, ValueError) as unreadable:
            raise CollectionError(unreadable_response_message(), SOURCE, None) from unreadable


def unreadable_response_message() -> str:
    return f"La réponse du service {SOURCE_NAMES[SOURCE]} est illisible. Réessayez plus tard."


def notice_page_from(stored_response: StoredResponse) -> NoticePage:
    try:
        payload = json.loads(stored_response.body)
        records = payload["results"]
        if not all(isinstance(record, dict) for record in records):
            raise TypeError("A notice is not an object")
        return NoticePage(tuple(records), int(payload["total_count"]), stored_response.summary)
    except (KeyError, TypeError, ValueError) as unreadable:
        raise CollectionError(unreadable_response_message(), SOURCE, None) from unreadable


class Bodacc:
    def __init__(
        self,
        http_client: CollectorHttpClient,
        notices_per_page: int = MAXIMUM_NOTICES_PER_PAGE,
        maximum_pages: int = DEFAULT_MAXIMUM_PAGES,
    ) -> None:
        self.http_client = http_client
        self.notices_per_page = notices_per_page
        self.maximum_pages = maximum_pages

    def notices_of(self, siren: str, *, refresh: bool = False) -> CompanyNotices:
        digits = siren_of(siren)
        pages: list[NoticePage] = []
        offset = 0
        while len(pages) < self.maximum_pages:
            page = self.notice_page(digits, offset, refresh)
            pages.append(page)
            offset += len(page.records)
            if not page.records or offset >= page.total_count:
                break
        return CompanyNotices(digits, tuple(pages))

    def notice_page(self, siren: str, offset: int, refresh: bool) -> NoticePage:
        stored_response = self.http_client.get(
            SOURCE,
            BODACC_RECORDS_URL,
            {
                "where": f'registre="{siren}"',
                "order_by": "dateparution desc",
                "limit": str(self.notices_per_page),
                "offset": str(offset),
            },
            refresh=refresh,
        )
        return notice_page_from(stored_response)
