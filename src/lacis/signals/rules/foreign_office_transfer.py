from dataclasses import dataclass

from lacis.signals.context import InvestigationContext
from lacis.signals.facts import french_date, years_before
from lacis.signals.rule_settings import RuleSettings, Threshold, ThresholdKind
from lacis.signals.signal import Finding, Severity
from lacis.storage.entities import Entity, EntityKind
from lacis.storage.notices import Notice, NoticeRole, OfficeTransfer

RECENT_YEARS = Threshold("recent_years", ThresholdKind.WHOLE_NUMBER, minimum=1)
UNKNOWN_COUNTRY = "pays non précisé"
OLD_TRANSFER_STRENGTH = 0.5


@dataclass(frozen=True)
class TransferNotice:
    notice: Notice
    transfer: OfficeTransfer


def transfers_of(context: InvestigationContext, company: Entity) -> list[TransferNotice]:
    found = [
        TransferNotice(company_notice.notice, company_notice.notice.office_transfer)
        for family_notices in context.notices_of(company.identifier).values()
        for company_notice in family_notices
        if company_notice.role is NoticeRole.SUBJECT
        and not company_notice.notice.is_withdrawn
        and company_notice.notice.office_transfer is not None
    ]
    return sorted(
        found,
        key=lambda found_transfer: (
            found_transfer.transfer.effective_on,
            found_transfer.notice.published_on,
        ),
        reverse=True,
    )


def explanation_of(transfers: list[TransferNotice]) -> str:
    latest = transfers[0]
    country = latest.transfer.country or UNKNOWN_COUNTRY
    effective = (
        f" le {french_date(latest.transfer.effective_on)}"
        if latest.transfer.effective_date_stated
        else ""
    )
    court = f" ({latest.notice.court})" if latest.notice.court else ""
    others = (
        f", la plus récente de {len(transfers)} annonces de transfert"
        if len(transfers) > 1
        else ""
    )
    return (
        f"Siège transféré à l'étranger ({country}){effective}, selon l'annonce publiée au "
        f"BODACC le {french_date(latest.notice.published_on)}{court}{others}."
    )


@dataclass(frozen=True)
class ForeignOfficeTransferRule:
    name: str = "foreign_office_transfer"
    title: str = "Transfert du siège à l'étranger"
    thresholds: tuple[Threshold, ...] = (RECENT_YEARS,)

    def evaluate(self, context: InvestigationContext, settings: RuleSettings) -> list[Finding]:
        cutoff = years_before(context.today, settings.whole_number(RECENT_YEARS.name))
        findings = []
        for company in context.entities_of(EntityKind.COMPANY):
            transfers = transfers_of(context, company)
            if not transfers:
                continue
            recent = transfers[0].transfer.effective_on >= cutoff
            findings.append(
                Finding(
                    subject=company.identifier,
                    strength=1.0 if recent else OLD_TRANSFER_STRENGTH,
                    explanation=explanation_of(transfers),
                    justifying_entities=(company.identifier,),
                    severity=Severity.MEDIUM if recent else None,
                )
            )
        return findings
