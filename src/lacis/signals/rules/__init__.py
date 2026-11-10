from lacis.signals.rule import Rule
from lacis.signals.rules.foreign_office_transfer import ForeignOfficeTransferRule
from lacis.signals.rules.mass_domiciliation import MassDomiciliationRule
from lacis.signals.rules.short_lived_companies import ShortLivedCompaniesRule

RULES: tuple[Rule, ...] = (
    MassDomiciliationRule(),
    ForeignOfficeTransferRule(),
    ShortLivedCompaniesRule(),
)
