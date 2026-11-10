from pathlib import Path

import pytest

from lacis.signals.configuration import (
    DEFAULT_CONFIGURATION_PATH,
    SignalConfigurationError,
    load_configuration,
)
from lacis.signals.rules import RULES
from lacis.signals.signal import Severity
from signal_rules import (
    FIXED_DEFAULTS,
    WELL_CONNECTED_DEFAULTS,
    FixedRule,
    WellConnectedRule,
)

RULES_UNDER_TEST = (WellConnectedRule(), FixedRule(()))
DEFAULTS = WELL_CONNECTED_DEFAULTS + FIXED_DEFAULTS


@pytest.fixture
def user_file(tmp_path: Path) -> Path:
    return tmp_path / "signals.toml"


def loaded(user_path: Path | None = None, defaults: str = DEFAULTS) -> dict[str, object]:
    return dict(load_configuration(RULES_UNDER_TEST, user_path, defaults))


def problem_of(user_file: Path, text: str) -> str:
    user_file.write_text(text, encoding="utf-8")
    with pytest.raises(SignalConfigurationError) as refused:
        load_configuration(RULES_UNDER_TEST, user_file, DEFAULTS)
    return str(refused.value)


def test_the_defaults_give_the_settings_of_every_rule() -> None:
    configuration = load_configuration(RULES_UNDER_TEST, None, DEFAULTS)
    well_connected = configuration["well_connected"]
    assert well_connected.enabled
    assert well_connected.severity is Severity.MEDIUM
    assert well_connected.weight == 1.0
    assert dict(well_connected.thresholds) == {
        "minimum_links": 2,
        "share": 0.5,
        "include_probable": False,
        "excluded_roles": ["Commissaire aux comptes"],
    }
    assert configuration["fixed"].severity is Severity.LOW
    assert configuration["fixed"].weight == 0.5


def test_a_missing_user_file_keeps_the_defaults(user_file: Path) -> None:
    assert loaded(user_file) == loaded()


def test_a_rule_can_be_disabled_in_the_user_file(user_file: Path) -> None:
    user_file.write_text("[rules.fixed]\nenabled = false\n", encoding="utf-8")
    configuration = load_configuration(RULES_UNDER_TEST, user_file, DEFAULTS)
    assert not configuration["fixed"].enabled
    assert configuration["fixed"].weight == 0.5
    assert configuration["well_connected"].enabled


def test_a_rule_can_be_tuned_in_the_user_file_key_by_key(user_file: Path) -> None:
    user_file.write_text(
        '[rules.well_connected]\nminimum_links = 5\nseverity = "high"\n', encoding="utf-8"
    )
    settings = load_configuration(RULES_UNDER_TEST, user_file, DEFAULTS)["well_connected"]
    assert settings.whole_number("minimum_links") == 5
    assert settings.severity is Severity.HIGH
    assert settings.number("share") == 0.5
    assert settings.texts("excluded_roles") == ("Commissaire aux comptes",)


def test_an_invalid_value_is_refused_with_its_key_and_the_expected_value(
    user_file: Path,
) -> None:
    assert problem_of(user_file, '[rules.well_connected]\nminimum_links = "deux"\n') == (
        f"Le fichier {user_file} : « rules.well_connected.minimum_links » doit être "
        "un nombre entier d'au moins 1, pas « deux »."
    )


@pytest.mark.parametrize(
    ("text", "key", "expected"),
    [
        ("share = 1.5", "share", "un nombre entre 0 et 1, pas 1.5"),
        ("include_probable = 1", "include_probable", "true ou false, pas 1"),
        ('severity = "forte"', "severity", "« low », « medium » ou « high », pas « forte »"),
        ("weight = -1", "weight", "un nombre entre 0 et 1, pas -1"),
        ('enabled = "non"', "enabled", "true ou false, pas « non »"),
    ],
)
def test_each_kind_of_invalid_value_names_what_is_expected(
    user_file: Path, text: str, key: str, expected: str
) -> None:
    assert problem_of(user_file, f"[rules.well_connected]\n{text}\n") == (
        f"Le fichier {user_file} : « rules.well_connected.{key} » doit être {expected}."
    )


def test_an_unknown_setting_is_refused_with_the_possible_ones(user_file: Path) -> None:
    assert problem_of(user_file, "[rules.fixed]\nminimum_links = 3\n") == (
        f"Le fichier {user_file} : « rules.fixed.minimum_links » n'est pas un réglage "
        "de cette règle. Réglages possibles : enabled, severity, weight."
    )


def test_an_unknown_rule_is_refused_with_the_known_ones(user_file: Path) -> None:
    assert problem_of(user_file, "[rules.phenix]\nenabled = false\n") == (
        f"Le fichier {user_file} : la règle « phenix » n'existe pas. "
        "Règles connues : fixed, well_connected."
    )


def test_settings_outside_the_rules_tables_are_refused(user_file: Path) -> None:
    assert problem_of(user_file, "minimum_links = 3\n") == (
        f"Le fichier {user_file} : « minimum_links » n'est pas reconnu. "
        "Les réglages se placent dans des tables [rules.<règle>]."
    )


def test_rules_must_be_a_table(user_file: Path) -> None:
    assert problem_of(user_file, "rules = 3\n") == (
        f"Le fichier {user_file} : « rules » doit être une table de règles."
    )


def test_a_rule_must_be_a_table(user_file: Path) -> None:
    assert problem_of(user_file, "[rules]\nfixed = false\n") == (
        f"Le fichier {user_file} : « rules.fixed » doit être une table [rules.fixed]."
    )


def test_a_file_that_is_not_toml_is_refused(user_file: Path) -> None:
    problem = problem_of(user_file, "[rules.fixed\nenabled = false\n")
    assert problem.startswith(f"Le fichier {user_file} n'est pas un fichier TOML valide : ")
    assert "line 1" in problem


def test_an_unreadable_user_file_is_refused(user_file: Path) -> None:
    user_file.write_bytes(b"\xff\xfe enabled = false")
    with pytest.raises(SignalConfigurationError) as refused:
        load_configuration(RULES_UNDER_TEST, user_file, DEFAULTS)
    assert str(refused.value).startswith(f"Le fichier {user_file} est illisible : ")


def test_a_user_path_that_is_a_folder_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SignalConfigurationError) as refused:
        load_configuration(RULES_UNDER_TEST, tmp_path, DEFAULTS)
    assert str(refused.value).startswith(f"Le fichier {tmp_path} est illisible : ")


def test_defaults_missing_a_setting_are_refused() -> None:
    with pytest.raises(SignalConfigurationError) as refused:
        load_configuration(RULES_UNDER_TEST, None, WELL_CONNECTED_DEFAULTS)
    assert str(refused.value) == (
        "Le fichier des réglages par défaut ne donne pas « rules.fixed.enabled »."
    )


def test_invalid_defaults_are_refused_too() -> None:
    with pytest.raises(SignalConfigurationError) as refused:
        load_configuration(RULES_UNDER_TEST, None, DEFAULTS.replace("weight = 0.5", "weight = 2"))
    assert str(refused.value) == (
        "Le fichier des réglages par défaut : « rules.fixed.weight » doit être "
        "un nombre entre 0 et 1, pas 2."
    )


def test_the_bundled_defaults_set_every_registered_rule() -> None:
    configuration = load_configuration(RULES)
    assert set(configuration) == {rule.name for rule in RULES}
    assert DEFAULT_CONFIGURATION_PATH.is_file()
