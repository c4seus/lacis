import pytest

from lacis.storage.errors import InvalidInvestigationNameError
from lacis.storage.names import MAXIMUM_NAME_LENGTH, validate_investigation_name


@pytest.mark.parametrize(
    "name",
    ["faux-plombiers-31", "dossier2026", "a", "x" * MAXIMUM_NAME_LENGTH, "12-rue-des-lilas"],
)
def test_lowercase_letters_digits_and_hyphens_are_accepted(name: str) -> None:
    assert validate_investigation_name(name) == name


@pytest.mark.parametrize(
    ("name", "expected_message"),
    [
        ("", "obligatoire"),
        ("x" * (MAXIMUM_NAME_LENGTH + 1), "64 caractères"),
        ("Faux-Plombiers", "minuscules"),
        ("faux plombiers", "minuscules"),
        ("enquête", "sans accent"),
        ("faux_plombiers", "tirets"),
        ("-faux", "début"),
        ("faux-", "fin"),
        ("faux--plombiers", "deux tirets"),
        ("../autre", "minuscules"),
    ],
)
def test_other_names_are_refused_with_a_french_explanation(
    name: str, expected_message: str
) -> None:
    with pytest.raises(InvalidInvestigationNameError, match=expected_message):
        validate_investigation_name(name)
