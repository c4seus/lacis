from lacis.signals.signal import Severity


def test_severities_have_french_labels() -> None:
    assert [severity.label for severity in Severity] == ["Faible", "Moyenne", "Forte"]


def test_severities_are_ranked_from_low_to_high() -> None:
    assert Severity.LOW.rank < Severity.MEDIUM.rank < Severity.HIGH.rank
