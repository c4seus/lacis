from dataclasses import dataclass

from lacis.collectors.bodacc import COUNTRY_OF_NORMALISED_NAME
from lacis.collectors.company_register import Company
from lacis.storage.comparison_keys import normalise_text

COUNTRY_OF_LEGAL_FORM = {
    ("LTD",): "Royaume-Uni",
    ("LIMITED",): "Royaume-Uni",
    ("PLC",): "Royaume-Uni",
    ("LLP",): "Royaume-Uni",
    ("GMBH",): "Allemagne",
    ("BV",): "Pays-Bas",
    ("BVBA",): "Belgique",
    ("SPRL",): "Belgique",
    ("SPA",): "Italie",
    ("SL",): "Espagne",
    ("SLU",): "Espagne",
    ("LDA",): "Portugal",
    ("SP", "ZOO"): "Pologne",
    ("KFT",): "Hongrie",
    ("OY",): "Finlande",
    ("APS",): "Danemark",
    ("SAGL",): "Suisse",
    ("LLC",): "États-Unis",
    ("INC",): "États-Unis",
    ("CORP",): "États-Unis",
}
LEGAL_FORM_SOURCE = "Forme juridique {legal_form}"
HEAD_OFFICE_SOURCE = "Adresse du siège"
FOREIGN_LAW_PREFIX = "3"


@dataclass(frozen=True)
class ForeignCountry:
    country: str
    source: str


def joined_initials(words: list[str]) -> tuple[str, ...]:
    joined: list[str] = []
    in_initials = False
    for word in words:
        if len(word) == 1 and in_initials:
            joined[-1] += word
        else:
            joined.append(word)
        in_initials = len(word) == 1
    return tuple(joined)


def country_of_legal_form(name: str) -> ForeignCountry | None:
    words = joined_initials(normalise_text(name).split())
    for legal_form, country in COUNTRY_OF_LEGAL_FORM.items():
        if words[-len(legal_form) :] == legal_form:
            return ForeignCountry(
                country, LEGAL_FORM_SOURCE.format(legal_form=" ".join(legal_form))
            )
    return None


def country_name(api_label: str) -> str:
    known_name = COUNTRY_OF_NORMALISED_NAME.get(normalise_text(api_label))
    return known_name or api_label.strip().title()


def is_under_foreign_law(company: Company) -> bool:
    legal_form = company.legal_form or ""
    head_office_country = company.head_office.address.country if company.head_office else None
    return legal_form.startswith(FOREIGN_LAW_PREFIX) or head_office_country is not None


def country_of_company(company: Company) -> ForeignCountry | None:
    if company.head_office is not None and company.head_office.address.country is not None:
        return ForeignCountry(
            country_name(company.head_office.address.country), HEAD_OFFICE_SOURCE
        )
    name = company.name if isinstance(company.name, str) else ""
    return country_of_legal_form(name) if is_under_foreign_law(company) else None
