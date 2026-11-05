from dataclasses import dataclass

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
