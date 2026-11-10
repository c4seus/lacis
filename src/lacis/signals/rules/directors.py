from collections.abc import Iterator
from dataclasses import dataclass

from lacis.graph.roles import DirectorRole, director_role
from lacis.signals.context import InvestigationContext
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.storage.entities import Entity, EntityKind, LinkKind

INCLUDE_PROBABLE = Threshold("include_probable", ThresholdKind.SWITCH)
EXCLUDED_ROLES = Threshold("excluded_roles", ThresholdKind.TEXTS)


@dataclass(frozen=True)
class Mandate:
    director: Entity
    company: Entity
    identity: str


def excluded_roles(settings: RuleSettings) -> frozenset[DirectorRole]:
    return frozenset(director_role(role) for role in settings.texts(EXCLUDED_ROLES.name))


def mandates(context: InvestigationContext, settings: RuleSettings) -> Iterator[Mandate]:
    identities = context.identities(include_probable=settings.switch(INCLUDE_PROBABLE.name))
    excluded = excluded_roles(settings)
    for link in context.links:
        if link.kind is not LinkKind.MANDATE or director_role(link.role) in excluded:
            continue
        director = context.entities[link.source]
        company = context.entities[link.target]
        identity = (
            identities.representative(director.identifier)
            if director.kind is EntityKind.PERSON
            else director.identifier
        )
        yield Mandate(director, company, identity)
