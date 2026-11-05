import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from lacis.storage.comparison_keys import (
    address_key,
    company_name_key,
    normalise_text,
    person_name_key,
)

AttributeValue = str | int | float | bool | None
Attributes = dict[str, AttributeValue]

SIREN_PATTERN = re.compile(r"\d{9}")
SIRET_PATTERN = re.compile(r"\d{14}")
MONTH_OF_BIRTH_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
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
    if not person_name_key(last_name):
        raise InvalidIdentifierError("A person needs a last name")
    key = KEY_SEPARATOR.join(
        [person_name_key(last_name), person_name_key(first_names), month_of_birth or ""]
    )
    return identifier(EntityKind.PERSON, digest(key))


def address_identifier(address: str) -> str:
    normalised_address = address_key(address)
    if not normalised_address:
        raise InvalidIdentifierError("An address cannot be empty")
    return identifier(EntityKind.ADDRESS, digest(normalised_address))


def foreign_company_identifier(name: str, country: str) -> str:
    normalised_name = company_name_key(name)
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


class LinkKind(StrEnum):
    MANDATE = "mandate"
    REGISTERED_OFFICE = "registered_office"
    LOCATED_AT = "located_at"
    ESTABLISHMENT_OF = "establishment_of"
    SAME_PERSON = "same_person"


DIRECTOR_KINDS = frozenset({EntityKind.PERSON, EntityKind.COMPANY, EntityKind.FOREIGN_COMPANY})
LINK_ENDPOINT_KINDS = {
    LinkKind.MANDATE: (DIRECTOR_KINDS, frozenset({EntityKind.COMPANY})),
    LinkKind.REGISTERED_OFFICE: (frozenset({EntityKind.COMPANY}), frozenset({EntityKind.ADDRESS})),
    LinkKind.LOCATED_AT: (frozenset({EntityKind.ESTABLISHMENT}), frozenset({EntityKind.ADDRESS})),
    LinkKind.ESTABLISHMENT_OF: (
        frozenset({EntityKind.ESTABLISHMENT}),
        frozenset({EntityKind.COMPANY}),
    ),
    LinkKind.SAME_PERSON: (frozenset({EntityKind.PERSON}), frozenset({EntityKind.PERSON})),
}
LINK_IDENTIFIER_PREFIX = "link"


class InvalidLinkError(ValueError):
    pass


@dataclass(frozen=True)
class CollectedLink:
    source: str
    target: str
    kind: LinkKind
    role: str = ""

    def __post_init__(self) -> None:
        source_kinds, target_kinds = LINK_ENDPOINT_KINDS[self.kind]
        if kind_of(self.source) not in source_kinds or kind_of(self.target) not in target_kinds:
            raise InvalidLinkError(
                f"A {self.kind} link cannot go from {kind_of(self.source)} "
                f"to {kind_of(self.target)}"
            )
        if self.source == self.target:
            raise InvalidLinkError("A link needs two different entities")
        if (self.kind == LinkKind.MANDATE) != bool(self.role.strip()):
            raise InvalidLinkError("A mandate has a role, and only a mandate has one")

    @property
    def identifier(self) -> str:
        key = KEY_SEPARATOR.join([self.source, self.kind, self.target, normalise_text(self.role)])
        return f"{LINK_IDENTIFIER_PREFIX}{IDENTIFIER_SEPARATOR}{digest(key)}"


def mandate_link(director: str, company: str, role: str) -> CollectedLink:
    return CollectedLink(director, company, LinkKind.MANDATE, " ".join(role.split()))


def registered_office_link(company: str, address: str) -> CollectedLink:
    return CollectedLink(company, address, LinkKind.REGISTERED_OFFICE)


def located_at_link(establishment: str, address: str) -> CollectedLink:
    return CollectedLink(establishment, address, LinkKind.LOCATED_AT)


def establishment_of_link(establishment: str, company: str) -> CollectedLink:
    return CollectedLink(establishment, company, LinkKind.ESTABLISHMENT_OF)


def same_person_link(first_person: str, second_person: str) -> CollectedLink:
    source, target = sorted([first_person, second_person])
    return CollectedLink(source, target, LinkKind.SAME_PERSON)


@dataclass(frozen=True)
class Link:
    identifier: str
    kind: LinkKind
    source: str
    target: str
    role: str
    first_collected_at: datetime
    last_collected_at: datetime
