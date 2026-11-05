from collections.abc import Iterable
from dataclasses import dataclass

from lacis.collectors.company_register import (
    Address,
    Company,
    Director,
    Disclosed,
    Establishment,
    LegalPersonDirector,
    NaturalPersonDirector,
)
from lacis.graph.foreign import country_of_legal_form
from lacis.graph.roles import director_role
from lacis.storage.entities import (
    MONTH_OF_BIRTH_PATTERN,
    CollectedEntity,
    CollectedLink,
    EntityKind,
    address_identifier,
    company_identifier,
    establishment_identifier,
    establishment_of_link,
    foreign_company_identifier,
    located_at_link,
    mandate_link,
    person_identifier,
    registered_office_link,
)

HEAD_OFFICE_LABEL = "Siège"
ESTABLISHMENT_LABEL = "Établissement"
LABEL_SEPARATOR = " — "


def shown(value: Disclosed | None) -> str | None:
    return value if isinstance(value, str) else None


def is_withheld(value: Disclosed | None) -> bool:
    return value is not None and not isinstance(value, str)


def spaced_siren(siren: str) -> str:
    return f"{siren[:3]} {siren[3:6]} {siren[6:]}"


@dataclass(frozen=True)
class GraphFragment:
    entities: tuple[CollectedEntity, ...] = ()
    links: tuple[CollectedLink, ...] = ()


def merged_entities(entities: Iterable[CollectedEntity]) -> tuple[CollectedEntity, ...]:
    merged: dict[str, CollectedEntity] = {}
    for entity in entities:
        known = merged.get(entity.identifier)
        if known is None:
            merged[entity.identifier] = entity
        else:
            known_values = {
                name: value for name, value in known.attributes.items() if value is not None
            }
            attributes = {**known.attributes, **entity.attributes, **known_values}
            merged[entity.identifier] = CollectedEntity(known.identifier, known.label, attributes)
    return tuple(merged.values())


def combined(fragments: Iterable[GraphFragment]) -> GraphFragment:
    every_fragment = list(fragments)
    links: dict[str, CollectedLink] = {}
    for fragment in every_fragment:
        for link in fragment.links:
            links.setdefault(link.identifier, link)
    return GraphFragment(
        merged_entities(entity for fragment in every_fragment for entity in fragment.entities),
        tuple(links.values()),
    )


def company_label(company: Company) -> str:
    return shown(company.name) or f"Entreprise non diffusible ({spaced_siren(company.siren)})"


def company_entity(company: Company) -> CollectedEntity:
    return CollectedEntity(
        company_identifier(company.siren),
        company_label(company),
        {
            "siren": company.siren,
            "name": shown(company.name),
            "name_withheld": is_withheld(company.name),
            "acronym": shown(company.acronym),
            "is_active": company.is_active,
            "diffusible": company.diffusible,
            "legal_form": company.legal_form,
            "activity": company.activity,
            "creation_date": company.creation_date,
            "closing_date": company.closing_date,
            "establishment_count": company.establishment_count,
            "open_establishment_count": company.open_establishment_count,
            "hidden_director_count": sum(
                isinstance(director, NaturalPersonDirector) and not director.diffusible
                for director in company.directors
            ),
        },
    )


def address_entity(address: Address) -> CollectedEntity | None:
    text = shown(address.full_text)
    if text is None or address.street_withheld:
        return None
    return CollectedEntity(
        address_identifier(text),
        text,
        {
            "text": text,
            "postcode": shown(address.postcode),
            "city": shown(address.city),
            "city_code": address.city_code,
            "country": address.country,
        },
    )


def establishment_label(establishment: Establishment) -> str:
    kind = HEAD_OFFICE_LABEL if establishment.is_head_office else ESTABLISHMENT_LABEL
    parts = [shown(establishment.trade_name) or kind, shown(establishment.address.city)]
    return LABEL_SEPARATOR.join(part for part in parts if part)


def establishment_entity(establishment: Establishment) -> CollectedEntity:
    return CollectedEntity(
        establishment_identifier(establishment.siret),
        establishment_label(establishment),
        {
            "siret": establishment.siret,
            "is_head_office": establishment.is_head_office,
            "is_open": establishment.is_open,
            "diffusible": establishment.diffusible,
            "trade_name": shown(establishment.trade_name),
            "activity": establishment.activity,
            "creation_date": establishment.creation_date,
            "closing_date": establishment.closing_date,
            "postcode": shown(establishment.address.postcode),
            "city": shown(establishment.address.city),
        },
    )


def establishment_fragment(company: str, establishment: Establishment) -> GraphFragment:
    entity = establishment_entity(establishment)
    links = [establishment_of_link(entity.identifier, company)]
    entities = [entity]
    address = address_entity(establishment.address) if establishment.diffusible else None
    if address is not None:
        entities.append(address)
        links.append(located_at_link(entity.identifier, address.identifier))
    return GraphFragment(tuple(entities), tuple(links))


def registered_office_fragment(company: Company) -> GraphFragment:
    head_office = company.head_office
    if head_office is None:
        return GraphFragment()
    company_entity_identifier = company_identifier(company.siren)
    fragment = establishment_fragment(company_entity_identifier, head_office)
    address = next(
        (entity for entity in fragment.entities if entity.kind is EntityKind.ADDRESS), None
    )
    if address is None:
        return fragment
    office_link = registered_office_link(company_entity_identifier, address.identifier)
    return GraphFragment(fragment.entities, (*fragment.links, office_link))


def person_entity(director: NaturalPersonDirector) -> CollectedEntity | None:
    last_name = shown(director.last_name)
    if last_name is None or not director.diffusible:
        return None
    first_names = shown(director.first_names) or ""
    birth_month = shown(director.birth_month)
    if birth_month is not None and not MONTH_OF_BIRTH_PATTERN.fullmatch(birth_month):
        birth_month = None
    label = " ".join(part for part in (first_names, last_name.upper()) if part)
    return CollectedEntity(
        person_identifier(last_name, first_names, birth_month),
        label,
        {
            "last_name": last_name,
            "first_names": first_names,
            "birth_month": birth_month,
            "nationality": shown(director.nationality),
        },
    )


def legal_person_entity(director: LegalPersonDirector) -> CollectedEntity | None:
    name = shown(director.name)
    if director.siren is not None:
        return CollectedEntity(
            company_identifier(director.siren),
            name or spaced_siren(director.siren),
            {"siren": director.siren, "name": name},
        )
    if name is None:
        return None
    foreign_country = country_of_legal_form(name)
    return CollectedEntity(
        foreign_company_identifier(name, ""),
        name,
        {
            "name": name,
            "country": foreign_country.country if foreign_country else None,
            "country_source": foreign_country.source if foreign_country else None,
        },
    )


def director_entity(director: Director) -> CollectedEntity | None:
    if isinstance(director, NaturalPersonDirector):
        return person_entity(director)
    return legal_person_entity(director)


def director_fragment(company: str, director: Director) -> GraphFragment:
    entity = director_entity(director)
    if entity is None or entity.identifier == company:
        return GraphFragment()
    role = director_role(director.role).value
    return GraphFragment((entity,), (mandate_link(entity.identifier, company, role),))


def company_fragment(company: Company) -> GraphFragment:
    identifier = company_identifier(company.siren)
    head_office_siret = company.head_office.siret if company.head_office else None
    other_establishments = [
        establishment
        for establishment in company.matching_establishments
        if establishment.siret != head_office_siret
    ]
    return combined(
        [
            GraphFragment((company_entity(company),)),
            registered_office_fragment(company),
            *(establishment_fragment(identifier, item) for item in other_establishments),
            *(director_fragment(identifier, director) for director in company.directors),
        ]
    )
