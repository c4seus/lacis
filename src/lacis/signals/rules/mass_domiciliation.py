from collections import Counter
from dataclasses import dataclass

from lacis.graph.expansion import EXPANDED_AT_ATTRIBUTE
from lacis.signals.context import InvestigationContext
from lacis.signals.facts import activity, counted, creation_date, years_before
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.signal import Finding, Severity
from lacis.storage.entities import Entity, EntityKind, LinkKind

MINIMUM_COMPANIES = Threshold("minimum_companies", ThresholdKind.WHOLE_NUMBER, minimum=2)
RECENT_YEARS = Threshold("recent_years", ThresholdKind.WHOLE_NUMBER, minimum=1)
MINIMUM_RECENT_SHARE = Threshold(
    "minimum_recent_share", ThresholdKind.NUMBER, minimum=0, maximum=1
)
MINIMUM_SAME_ACTIVITY_SHARE = Threshold(
    "minimum_same_activity_share", ThresholdKind.NUMBER, minimum=0, maximum=1
)
NOT_EXPANDED_TEXT = " ; l'adresse n'a pas encore été étendue et peut en compter d'autres"


@dataclass(frozen=True)
class AddressCompanies:
    address: Entity
    companies: tuple[Entity, ...]
    recent_count: int
    dominant_activity: str | None
    dominant_activity_count: int

    @property
    def count(self) -> int:
        return len(self.companies)

    @property
    def recent_share(self) -> float:
        return self.recent_count / self.count

    @property
    def same_activity_share(self) -> float:
        return self.dominant_activity_count / self.count


def address_companies(
    context: InvestigationContext, address: Entity, recent_years: int
) -> AddressCompanies:
    companies = tuple(
        sorted(
            context.neighbours(address.identifier, LinkKind.REGISTERED_OFFICE, EntityKind.COMPANY),
            key=lambda company: (company.label, company.identifier),
        )
    )
    cutoff = years_before(context.today, recent_years)
    recent_count = sum(
        1
        for company in companies
        if (created_on := creation_date(company)) is not None and created_on >= cutoff
    )
    activities = Counter(
        found for company in companies if (found := activity(company)) is not None
    )
    dominant_activity, dominant_count = activities.most_common(1)[0] if activities else (None, 0)
    return AddressCompanies(address, companies, recent_count, dominant_activity, dominant_count)


def explanation_of(found: AddressCompanies, recent_years: int) -> str:
    details = []
    if found.recent_count:
        created = counted(found.recent_count, "créée", "créées")
        details.append(f"{created} depuis moins de {counted(recent_years, 'an', 'ans')}")
    if found.dominant_activity is not None and found.dominant_activity_count > 1:
        details.append(
            f"{found.dominant_activity_count} dans l'activité {found.dominant_activity}"
        )
    detail_text = f", dont {' et '.join(details)}" if details else ""
    expanded = EXPANDED_AT_ATTRIBUTE in found.address.attributes
    return (
        f"{found.count} entreprises de l'enquête ont leur siège à cette adresse{detail_text}"
        f"{'' if expanded else NOT_EXPANDED_TEXT}."
    )


@dataclass(frozen=True)
class MassDomiciliationRule:
    name: str = "mass_domiciliation"
    title: str = "Domiciliation de masse"
    thresholds: tuple[Threshold, ...] = (
        MINIMUM_COMPANIES,
        RECENT_YEARS,
        MINIMUM_RECENT_SHARE,
        MINIMUM_SAME_ACTIVITY_SHARE,
    )

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        minimum_companies = settings.whole_number(MINIMUM_COMPANIES.name)
        recent_years = settings.whole_number(RECENT_YEARS.name)
        findings = []
        for address in context.entities_of(EntityKind.ADDRESS):
            found = address_companies(context, address, recent_years)
            if found.count < minimum_companies:
                continue
            many_recent = found.recent_share >= settings.number(MINIMUM_RECENT_SHARE.name)
            same_activity = found.same_activity_share >= settings.number(
                MINIMUM_SAME_ACTIVITY_SHARE.name
            )
            if not (many_recent or same_activity):
                continue
            findings.append(
                Finding(
                    subject=address.identifier,
                    strength=min(1.0, found.count / (2 * minimum_companies))
                    * (0.5 + 0.25 * found.recent_share + 0.25 * found.same_activity_share),
                    explanation=explanation_of(found, recent_years),
                    justifying_entities=tuple(company.identifier for company in found.companies),
                    severity=severity_of(found, minimum_companies, many_recent and same_activity),
                )
            )
        return findings


def severity_of(found: AddressCompanies, minimum_companies: int, both: bool) -> Severity | None:
    if not both:
        return None
    return Severity.HIGH if found.count >= 2 * minimum_companies else Severity.MEDIUM
