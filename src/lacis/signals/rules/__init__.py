from lacis.signals.rule import Rule
from lacis.signals.rules.mass_domiciliation import MassDomiciliationRule

RULES: tuple[Rule, ...] = (MassDomiciliationRule(),)
