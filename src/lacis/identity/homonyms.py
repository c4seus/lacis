from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from itertools import combinations
from typing import Self

from lacis.storage.comparison_keys import person_name_key
from lacis.storage.entities import Entity, EntityKind
from lacis.storage.graph_store import GraphStore


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

    @classmethod
    def of(cls, person: Entity) -> Self:
        birth_month = person.attributes.get("birth_month")
        return cls(
            person.identifier,
            person.label,
            person_name_key(str(person.attributes.get("last_name") or "")),
            tuple(person_name_key(str(person.attributes.get("first_names") or "")).split()),
            birth_month if isinstance(birth_month, str) and birth_month else None,
        )


@dataclass(frozen=True)
class HomonymPair:
    first: PersonIdentity
    second: PersonIdentity
    first_name_relation: FirstNameRelation

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
