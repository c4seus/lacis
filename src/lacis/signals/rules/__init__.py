from lacis.signals.rule import Rule
from lacis.signals.rules.creation_burst import CreationBurstRule
from lacis.signals.rules.foreign_office_transfer import ForeignOfficeTransferRule
from lacis.signals.rules.mass_domiciliation import MassDomiciliationRule
from lacis.signals.rules.phoenix_scheme import PhoenixSchemeRule
from lacis.signals.rules.short_lived_companies import ShortLivedCompaniesRule

RULES: tuple[Rule, ...] = (
    MassDomiciliationRule(),
    ForeignOfficeTransferRule(),
    ShortLivedCompaniesRule(),
    PhoenixSchemeRule(),
    CreationBurstRule(),
)
