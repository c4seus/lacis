from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Self

from lacis.storage.comparison_keys import person_name_key
from lacis.storage.entities import Entity, EntityKind, LinkKind
from lacis.storage.graph_store import GraphStore
from lacis.storage.homonym_decisions import HomonymDecisionStore


class FirstNameRelation(StrEnum):
    SAME = "same"
    COMPOUND = "compound"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PersonIdentity:
    identifier: str
    label: str
    last_name: str
    first_names: tuple[str, ...]
    birth_month: str | None
    written_first_names: str = ""

    @classmethod
    def of(cls, person: Entity) -> Self:
        birth_month = person.attributes.get("birth_month")
        return cls(
            person.identifier,
            person.label,
            person_name_key(str(person.attributes.get("last_name") or "")),
            tuple(person_name_key(str(person.attributes.get("first_names") or "")).split()),
            birth_month if isinstance(birth_month, str) and birth_month else None,
            str(person.attributes.get("first_names") or ""),
        )


@dataclass(frozen=True)
class HomonymPair:
    first: PersonIdentity
    second: PersonIdentity
    first_name_relation: FirstNameRelation

    @property
    def people(self) -> tuple[str, str]:
        first, second = sorted((self.first.identifier, self.second.identifier))
        return first, second

    @property
    def same_birth_month(self) -> bool:
        return self.first.birth_month is not None and self.first.birth_month == (
            self.second.birth_month
        )


def first_name_relation(
    first: tuple[str, ...], second: tuple[str, ...]
) -> FirstNameRelation | None:
    if not first or not second:
        return FirstNameRelation.UNKNOWN
    if first == second:
        return FirstNameRelation.SAME
    shorter, longer = sorted((first, second), key=len)
    if longer[: len(shorter)] == shorter:
        return FirstNameRelation.COMPOUND
    return None


def births_agree(first: PersonIdentity, second: PersonIdentity) -> bool:
    return None in (first.birth_month, second.birth_month) or (
        first.birth_month == second.birth_month
    )


def homonym_pair(first: PersonIdentity, second: PersonIdentity) -> HomonymPair | None:
    if not first.last_name or first.last_name != second.last_name:
        return None
    if not births_agree(first, second):
        return None
    relation = first_name_relation(first.first_names, second.first_names)
    if relation is None:
        return None
    ordered = sorted((first, second), key=lambda person: (person.label, person.identifier))
    return HomonymPair(ordered[0], ordered[1], relation)


def homonym_pairs(graph_store: GraphStore) -> list[HomonymPair]:
    people_by_last_name: dict[str, list[PersonIdentity]] = defaultdict(list)
    for entity in graph_store.entities():
        if entity.kind is EntityKind.PERSON:
            person = PersonIdentity.of(entity)
            people_by_last_name[person.last_name].append(person)
    candidates = [
        homonym_pair(first, second)
        for people in people_by_last_name.values()
        for first, second in combinations(people, 2)
    ]
    pairs = [pair for pair in candidates if pair is not None]
    return sorted(pairs, key=lambda pair: (pair.first.label, pair.second.label))


class Confidence(StrEnum):
    CERTAIN = "certain"
    PROBABLE = "probable"
    WEAK = "faible"


CONFIDENCE_ORDER = (Confidence.CERTAIN, Confidence.PROBABLE, Confidence.WEAK)
STRONG_CORROBORATION = 2


@dataclass(frozen=True)
class HomonymProposal:
    pair: HomonymPair
    confidence: Confidence
    reasons: tuple[str, ...]


def written_month(birth_month: str) -> str:
    year, month = birth_month.split("-")
    return f"{month}/{year}"


def identity_reasons(pair: HomonymPair) -> list[str]:
    reasons = ["Même nom de famille"]
    if pair.first_name_relation is FirstNameRelation.SAME:
        reasons.append("Mêmes prénoms")
    elif pair.first_name_relation is FirstNameRelation.COMPOUND:
        names = sorted((pair.first.written_first_names, pair.second.written_first_names), key=len)
        reasons.append(f"Prénom composé : {names[0]} / {names[1]}")
    else:
        reasons.append("Prénoms inconnus d'un côté")
    if pair.first.birth_month is not None and pair.same_birth_month:
        reasons.append(f"Même mois de naissance ({written_month(pair.first.birth_month)})")
    else:
        reasons.append("Mois de naissance inconnu d'un côté")
    return reasons


class Corroboration:
    def __init__(self, graph_store: GraphStore) -> None:
        self.graph_store = graph_store

    def label(self, identifier: str) -> str:
        entity = self.graph_store.entity(identifier)
        return entity.label if entity is not None else identifier

    def companies_directed_by(self, identifier: str) -> set[str]:
        return {
            link.target
            for link in self.graph_store.links_of(identifier)
            if link.kind is LinkKind.MANDATE and link.source == identifier
        }

    def addresses_of(self, companies: set[str]) -> set[str]:
        return {
            link.target
            for company in companies
            for link in self.graph_store.links_of(company)
            if link.kind is LinkKind.REGISTERED_OFFICE and link.source == company
        }

    def reasons(self, pair: HomonymPair) -> list[str]:
        first_companies = self.companies_directed_by(pair.first.identifier)
        second_companies = self.companies_directed_by(pair.second.identifier)
        reasons = [
            f"Dirigeants tous deux de {self.label(company)}"
            for company in sorted(first_companies & second_companies)
        ]
        for director, directed in (
            (first_companies, second_companies),
            (second_companies, first_companies),
        ):
            reasons.extend(
                f"{self.label(company)} dirige {self.label(other)}"
                for company in sorted(director - directed)
                for other in sorted(self.companies_directed_by(company) & directed)
            )
        shared_addresses = self.addresses_of(first_companies) & self.addresses_of(second_companies)
        reasons.extend(
            f"Entreprises domiciliées à la même adresse : {self.label(address)}"
            for address in sorted(shared_addresses)
        )
        return reasons


def confidence_of(pair: HomonymPair, corroborations: list[str]) -> Confidence:
    identity_known = pair.same_birth_month and (
        pair.first_name_relation is not FirstNameRelation.UNKNOWN
    )
    well_corroborated = len(corroborations) >= STRONG_CORROBORATION
    if identity_known:
        return Confidence.CERTAIN if well_corroborated else Confidence.PROBABLE
    return Confidence.PROBABLE if well_corroborated else Confidence.WEAK


def homonym_proposals(
    graph_store: GraphStore, decision_store: HomonymDecisionStore
) -> list[HomonymProposal]:
    corroboration = Corroboration(graph_store)
    decided_pairs = decision_store.decided_pairs()
    proposals = []
    for pair in homonym_pairs(graph_store):
        if pair.people in decided_pairs:
            continue
        corroborations = corroboration.reasons(pair)
        proposals.append(
            HomonymProposal(
                pair,
                confidence_of(pair, corroborations),
                (*identity_reasons(pair), *corroborations),
            )
        )
    return sorted(proposals, key=lambda proposal: CONFIDENCE_ORDER.index(proposal.confidence))
