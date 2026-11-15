import json
import re
from collections.abc import Iterator
from datetime import date
from typing import Any

from lacis.storage.comparison_keys import normalise_text
from lacis.storage.notices import OfficeTransfer

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
OFFICE_ADDRESS_KEY = "adresseSiegeSocial"
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


def objects_of(value: object, key: str) -> Iterator[object]:
    if isinstance(value, dict):
        for name, item in value.items():
            if name == key:
                yield item
            else:
                yield from objects_of(item, key)
    elif isinstance(value, list):
        for item in value:
            yield from objects_of(item, key)


def stated_country(sources: list[object]) -> str | None:
    return next((country for source in sources for country in values_of(source, "pays")), None)


def country_in(texts: list[str]) -> str | None:
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
    persons = decoded(record.get("listepersonnes"))
    stated = stated_country([*details, *objects_of(persons, OFFICE_ADDRESS_KEY)])
    if stated is None:
        country = country_in(texts)
        if country is None and not any(word in words for word in ABROAD_WORDS):
            return None
    elif normalise_text(stated) == DOMESTIC_COUNTRY:
        return None
    else:
        country = COUNTRY_OF_NORMALISED_NAME.get(normalise_text(stated), stated)
    effective_on = effective_date_in(details, texts)
    if effective_on is None:
        return OfficeTransfer(country, published_on, effective_date_stated=False)
    return OfficeTransfer(country, effective_on, effective_date_stated=True)
