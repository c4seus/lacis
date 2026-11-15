from lacis.signals.signal import Severity


def test_severities_have_french_labels() -> None:
    assert [severity.label for severity in Severity] == ["Faible", "Moyenne", "Forte"]


def test_severities_are_ranked_from_low_to_high() -> None:
    assert Severity.LOW.rank < Severity.MEDIUM.rank < Severity.HIGH.rank


def test_a_raised_severity_goes_up_one_step_and_stops_at_high() -> None:
    assert [severity.raised for severity in Severity] == [
        Severity.MEDIUM,
        Severity.HIGH,
        Severity.HIGH,
    ]
