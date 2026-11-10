from dataclasses import dataclass
from datetime import date

from lacis.signals.context import InvestigationContext
from lacis.signals.facts import activity, creation_date, french_date
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.rules.directors import EXCLUDED_ROLES, INCLUDE_PROBABLE, directed_companies
from lacis.signals.signal import Finding, Severity
from lacis.storage.entities import Entity, EntityKind, LinkKind

MINIMUM_COMPANIES = Threshold("minimum_companies", ThresholdKind.WHOLE_NUMBER, minimum=2)
WINDOW_DAYS = Threshold("window_days", ThresholdKind.WHOLE_NUMBER, minimum=1)
BY_ACTIVITY_AND_DEPARTMENT = Threshold("by_activity_and_department", ThresholdKind.SWITCH)
ACTIVITY_MINIMUM_COMPANIES = Threshold(
    "activity_minimum_companies", ThresholdKind.WHOLE_NUMBER, minimum=2
)
ACTIVITY_WINDOW_DAYS = Threshold("activity_window_days", ThresholdKind.WHOLE_NUMBER, minimum=1)
POSTCODE_LENGTH = 5
CORSICA_PREFIX = "20"
SOUTH_CORSICA_LAST_POSTCODE = 20199
OVERSEAS_PREFIXES = ("97", "98")
VOLUME_SHARE = 0.7
DENSITY_SHARE = 0.3


@dataclass(frozen=True)
class Burst:
    companies: tuple[Entity, ...]
    first: date
    last: date

    @property
    def count(self) -> int:
        return len(self.companies)

    @property
    def days(self) -> int:
        return (self.last - self.first).days + 1


@dataclass(frozen=True)
class BurstLimits:
    minimum_companies: int
    window_days: int


def densest_burst(companies: list[Entity], limits: BurstLimits) -> Burst | None:
    dated = sorted(
        (
            (created_on, company)
            for company in companies
            if (created_on := creation_date(company)) is not None
        ),
        key=lambda dated_company: (dated_company[0], dated_company[1].label),
    )
    best: tuple[int, int] | None = None
    start = 0
    for end in range(len(dated)):
        while (dated[end][0] - dated[start][0]).days >= limits.window_days:
            start += 1
        size = end - start + 1
        if size >= limits.minimum_companies and (best is None or size > best[1] - best[0] + 1):
            best = (start, end)
    if best is None:
        return None
    chosen = dated[best[0] : best[1] + 1]
    return Burst(tuple(company for _, company in chosen), chosen[0][0], chosen[-1][0])


def department_of(postcode: object) -> str | None:
    text = str(postcode or "")
    if len(text) != POSTCODE_LENGTH or not text.isdigit():
        return None
    if text.startswith(CORSICA_PREFIX):
        return "2A" if int(text) <= SOUTH_CORSICA_LAST_POSTCODE else "2B"
    if text.startswith(OVERSEAS_PREFIXES):
        return text[:3]
    return text[:2]


def company_department(context: InvestigationContext, company: Entity) -> str | None:
    for address in context.neighbours(
        company.identifier, LinkKind.REGISTERED_OFFICE, EntityKind.ADDRESS
    ):
        department = department_of(address.attributes.get("postcode"))
        if department is not None:
            return department
    return None


def burst_strength(burst: Burst, limits: BurstLimits) -> float:
    volume = min(1.0, burst.count / (2 * limits.minimum_companies))
    density = 1.0 - min(burst.days, limits.window_days) / (limits.window_days + 1)
    return volume * (VOLUME_SHARE + DENSITY_SHARE * density)


def explanation_of(burst: Burst, where: str) -> str:
    names = ", ".join(company.label for company in burst.companies)
    if burst.first == burst.last:
        period = f"le même jour, le {french_date(burst.first)},"
    else:
        period = (
            f"en {burst.days} jours, du {french_date(burst.first)} au {french_date(burst.last)},"
        )
    return f"{burst.count} entreprises créées {period} {where} : {names}."


def raised_once(severity: Severity | None) -> Severity:
    return Severity.MEDIUM if severity is None else Severity.HIGH


def finding_of(
    subject: str, burst: Burst, limits: BurstLimits, where: str, severity: Severity | None
) -> Finding:
    doubled = burst.count >= 2 * limits.minimum_companies
    return Finding(
        subject=subject,
        strength=burst_strength(burst, limits),
        explanation=explanation_of(burst, where),
        justifying_entities=tuple(
            company.identifier for company in burst.companies if company.identifier != subject
        ),
        severity=raised_once(severity) if doubled else severity,
    )


@dataclass(frozen=True)
class CreationBurstRule:
    name: str = "creation_burst"
    title: str = "Rafale de créations"
    thresholds: tuple[Threshold, ...] = (
        MINIMUM_COMPANIES,
        WINDOW_DAYS,
        BY_ACTIVITY_AND_DEPARTMENT,
        ACTIVITY_MINIMUM_COMPANIES,
        ACTIVITY_WINDOW_DAYS,
        INCLUDE_PROBABLE,
        EXCLUDED_ROLES,
    )

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        limits = BurstLimits(
            settings.whole_number(MINIMUM_COMPANIES.name),
            settings.whole_number(WINDOW_DAYS.name),
        )
        findings = [
            *self.director_bursts(context, settings, limits),
            *self.address_bursts(context, limits),
        ]
        if settings.switch(BY_ACTIVITY_AND_DEPARTMENT.name):
            activity_limits = BurstLimits(
                settings.whole_number(ACTIVITY_MINIMUM_COMPANIES.name),
                settings.whole_number(ACTIVITY_WINDOW_DAYS.name),
            )
            findings.extend(self.activity_bursts(context, activity_limits))
        return findings

    def director_bursts(
        self, context: InvestigationContext, settings: RuleSettings, limits: BurstLimits
    ) -> list[Finding]:
        findings = []
        for identity, directed in sorted(directed_companies(context, settings).items()):
            burst = densest_burst(list(directed.companies.values()), limits)
            if burst is not None:
                where = f"sous la direction de {directed.director.label}"
                findings.append(finding_of(identity, burst, limits, where, Severity.MEDIUM))
        return findings

    def address_bursts(self, context: InvestigationContext, limits: BurstLimits) -> list[Finding]:
        findings = []
        for address in sorted(
            context.entities_of(EntityKind.ADDRESS), key=lambda address: address.identifier
        ):
            companies = context.neighbours(
                address.identifier, LinkKind.REGISTERED_OFFICE, EntityKind.COMPANY
            )
            burst = densest_burst(companies, limits)
            if burst is not None:
                findings.append(
                    finding_of(
                        address.identifier, burst, limits, "à cette adresse", Severity.MEDIUM
                    )
                )
        return findings

    def activity_bursts(self, context: InvestigationContext, limits: BurstLimits) -> list[Finding]:
        groups: dict[tuple[str, str], list[Entity]] = {}
        for company in context.entities_of(EntityKind.COMPANY):
            company_activity = activity(company)
            department = company_department(context, company)
            if company_activity is not None and department is not None:
                groups.setdefault((company_activity, department), []).append(company)
        findings = []
        for (company_activity, department), companies in sorted(groups.items()):
            burst = densest_burst(companies, limits)
            if burst is not None:
                where = f"dans l'activité {company_activity} du département {department}"
                findings.append(
                    finding_of(burst.companies[0].identifier, burst, limits, where, None)
                )
        return findings
