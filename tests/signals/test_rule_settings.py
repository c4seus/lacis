import pytest

from lacis.signals.rule_settings import (
    SEVERITY,
    WEIGHT,
    RuleSettings,
    Threshold,
    ThresholdKind,
    shown_value,
)
from lacis.signals.signal import Severity

WHOLE = Threshold("minimum_companies", ThresholdKind.WHOLE_NUMBER, minimum=2)
SHARE = Threshold("recent_share", ThresholdKind.NUMBER, minimum=0, maximum=1)
FREE_NUMBER = Threshold("factor", ThresholdKind.NUMBER)
AT_MOST = Threshold("maximum_months", ThresholdKind.WHOLE_NUMBER, maximum=120)
SWITCH = Threshold("include_probable", ThresholdKind.SWITCH)
TEXTS = Threshold("excluded_roles", ThresholdKind.TEXTS)


@pytest.mark.parametrize(
    ("threshold", "value", "accepted"),
    [
        (WHOLE, 2, True),
        (WHOLE, 1, False),
        (WHOLE, 2.0, False),
        (WHOLE, True, False),
        (SHARE, 0.5, True),
        (SHARE, 1, True),
        (SHARE, 1.5, False),
        (SHARE, False, False),
        (SHARE, "0.5", False),
        (AT_MOST, 121, False),
        (SWITCH, False, True),
        (SWITCH, 0, False),
        (TEXTS, ["Commissaire aux comptes"], True),
        (TEXTS, [], True),
        (TEXTS, ["Gérant", 3], False),
        (TEXTS, "Gérant", False),
        (SEVERITY, "high", True),
        (SEVERITY, "forte", False),
        (WEIGHT, 0, True),
    ],
)
def test_a_threshold_accepts_only_its_kind_of_value(
    threshold: Threshold, value: object, accepted: bool
) -> None:
    assert threshold.accepts(value) is accepted


@pytest.mark.parametrize(
    ("threshold", "expected"),
    [
        (WHOLE, "un nombre entier d'au moins 2"),
        (SHARE, "un nombre entre 0 et 1"),
        (FREE_NUMBER, "un nombre"),
        (AT_MOST, "un nombre entier d'au plus 120"),
        (SWITCH, "true ou false"),
        (TEXTS, 'une liste de textes, par exemple ["Commissaire aux comptes"]'),
        (SEVERITY, "« low », « medium » ou « high »"),
        (Threshold("ratio", ThresholdKind.NUMBER, minimum=0.25), "un nombre d'au moins 0,25"),
    ],
)
def test_a_threshold_describes_the_value_it_expects_in_french(
    threshold: Threshold, expected: str
) -> None:
    assert threshold.expected() == expected


@pytest.mark.parametrize(
    ("value", "shown"),
    [
        (True, "true"),
        (False, "false"),
        ("deux", "« deux »"),
        ([1, "a"], "[1, « a »]"),
        ({"a": 1}, "une table"),
        (2.5, "2.5"),
    ],
)
def test_a_value_is_shown_as_written_in_the_file(value: object, shown: str) -> None:
    assert shown_value(value) == shown


def test_settings_give_typed_thresholds() -> None:
    settings = RuleSettings(
        enabled=True,
        severity=Severity.MEDIUM,
        weight=1.0,
        thresholds={
            "minimum_companies": 10,
            "recent_share": 1,
            "include_probable": False,
            "excluded_roles": ["Commissaire aux comptes"],
        },
    )
    assert settings.whole_number("minimum_companies") == 10
    assert settings.number("recent_share") == 1.0
    assert isinstance(settings.number("recent_share"), float)
    assert settings.switch("include_probable") is False
    assert settings.texts("excluded_roles") == ("Commissaire aux comptes",)
