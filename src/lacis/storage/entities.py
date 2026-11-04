import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

AttributeValue = str | int | float | bool | None
Attributes = dict[str, AttributeValue]

SIREN_PATTERN = re.compile(r"\d{9}")
SIRET_PATTERN = re.compile(r"\d{14}")
MONTH_OF_BIRTH_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
NON_ALPHANUMERIC_PATTERN = re.compile(r"[^A-Za-z0-9]+")
DIGEST_LENGTH = 16
KEY_SEPARATOR = "|"
IDENTIFIER_SEPARATOR = ":"


class EntityKind(StrEnum):
    COMPANY = "company"
    ESTABLISHMENT = "establishment"
    PERSON = "person"
    ADDRESS = "address"
    FOREIGN_COMPANY = "foreign_company"


class InvalidIdentifierError(ValueError):
    pass


def normalise_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(NON_ALPHANUMERIC_PATTERN.sub(" ", without_accents).upper().split())


def remove_spaces(text: str) -> str:
    return "".join(text.split())


def digest(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:DIGEST_LENGTH]


def identifier(kind: EntityKind, key: str) -> str:
    return f"{kind}{IDENTIFIER_SEPARATOR}{key}"


def company_identifier(siren: str) -> str:
    cleaned_siren = remove_spaces(siren)
    if not SIREN_PATTERN.fullmatch(cleaned_siren):
        raise InvalidIdentifierError(f"A SIREN has 9 digits, not {siren!r}")
    return identifier(EntityKind.COMPANY, cleaned_siren)


def establishment_identifier(siret: str) -> str:
    cleaned_siret = remove_spaces(siret)
    if not SIRET_PATTERN.fullmatch(cleaned_siret):
        raise InvalidIdentifierError(f"A SIRET has 14 digits, not {siret!r}")
    return identifier(EntityKind.ESTABLISHMENT, cleaned_siret)


def person_identifier(last_name: str, first_names: str, month_of_birth: str | None) -> str:
    if month_of_birth is not None and not MONTH_OF_BIRTH_PATTERN.fullmatch(month_of_birth):
        raise InvalidIdentifierError(f"A month of birth reads YYYY-MM, not {month_of_birth!r}")
    if not normalise_text(last_name):
        raise InvalidIdentifierError("A person needs a last name")
    key = KEY_SEPARATOR.join(
        [normalise_text(last_name), normalise_text(first_names), month_of_birth or ""]
    )
    return identifier(EntityKind.PERSON, digest(key))


def address_identifier(address: str) -> str:
    normalised_address = normalise_text(address)
    if not normalised_address:
        raise InvalidIdentifierError("An address cannot be empty")
    return identifier(EntityKind.ADDRESS, digest(normalised_address))


def foreign_company_identifier(name: str, country: str) -> str:
    normalised_name = normalise_text(name)
    if not normalised_name:
        raise InvalidIdentifierError("A foreign company needs a name")
    key = KEY_SEPARATOR.join([normalised_name, normalise_text(country)])
    return identifier(EntityKind.FOREIGN_COMPANY, digest(key))


def kind_of(entity_identifier: str) -> EntityKind:
    return EntityKind(entity_identifier.split(IDENTIFIER_SEPARATOR, 1)[0])


@dataclass(frozen=True)
class CollectedEntity:
    identifier: str
    label: str
    attributes: Attributes = field(default_factory=dict)

    @property
    def kind(self) -> EntityKind:
        return kind_of(self.identifier)


@dataclass(frozen=True)
class Entity:
    identifier: str
    kind: EntityKind
    label: str
    attributes: Attributes
    first_collected_at: datetime
    last_collected_at: datetime
