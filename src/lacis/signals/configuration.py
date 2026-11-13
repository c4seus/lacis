import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from lacis.signals.rule import Rule
from lacis.signals.rule_settings import (
    COMMON_SETTINGS,
    ENABLED,
    SEVERITY,
    WEIGHT,
    RuleSettings,
    Threshold,
    quoted,
    shown_value,
)
from lacis.signals.signal import Severity

DEFAULT_CONFIGURATION_PATH = Path(__file__).resolve().parent / "default_rules.toml"
USER_CONFIGURATION_FILE_NAME = "signals.toml"
RULES_TABLE = "rules"
DEFAULT_ORIGIN = "Le fichier des réglages par défaut"

type RawSettings = dict[str, dict[str, object]]


class SignalConfigurationError(Exception):
    pass


def origin_of(path: Path) -> str:
    return f"Le fichier {path}"


def key_of(rule: str, setting: str | None = None) -> str:
    return quoted(f"{RULES_TABLE}.{rule}" + (f".{setting}" if setting else ""))


def listed(names: Sequence[str]) -> str:
    return ", ".join(sorted(names)) or "aucune"


def parsed(text: str, origin: str) -> dict[str, object]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as invalid:
        raise SignalConfigurationError(
            f"{origin} n'est pas un fichier TOML valide : {invalid}."
        ) from invalid


def rule_tables(
    document: Mapping[str, object], rules: Mapping[str, Rule], origin: str
) -> RawSettings:
    for key in document:
        if key != RULES_TABLE:
            raise SignalConfigurationError(
                f"{origin} : {quoted(key)} n'est pas reconnu. "
                f"Les réglages se placent dans des tables [{RULES_TABLE}.<règle>]."
            )
    tables = document.get(RULES_TABLE, {})
    if not isinstance(tables, dict):
        raise SignalConfigurationError(
            f"{origin} : {quoted(RULES_TABLE)} doit être une table de règles."
        )
    raw_settings: RawSettings = {}
    for rule_name, table in tables.items():
        if rule_name not in rules:
            raise SignalConfigurationError(
                f"{origin} : la règle {quoted(rule_name)} n'existe pas. "
                f"Règles connues : {listed(list(rules))}."
            )
        if not isinstance(table, dict):
            raise SignalConfigurationError(
                f"{origin} : {key_of(rule_name)} doit être une table [{RULES_TABLE}.{rule_name}]."
            )
        raw_settings[rule_name] = table
    return raw_settings


def checked_values(rule: Rule, values: Mapping[str, object], origin: str) -> dict[str, object]:
    accepted = {threshold.name: threshold for threshold in (*COMMON_SETTINGS, *rule.thresholds)}
    for name, value in values.items():
        threshold = accepted.get(name)
        if threshold is None:
            raise SignalConfigurationError(
                f"{origin} : {key_of(rule.name, name)} n'est pas un réglage de cette règle. "
                f"Réglages possibles : {listed(list(accepted))}."
            )
        reject_invalid(rule.name, threshold, value, origin)
    return dict(values)


def reject_invalid(rule_name: str, threshold: Threshold, value: object, origin: str) -> None:
    if not threshold.accepts(value):
        raise SignalConfigurationError(
            f"{origin} : {key_of(rule_name, threshold.name)} doit être "
            f"{threshold.expected()}, pas {shown_value(value)}."
        )


def complete_settings(rule: Rule, values: Mapping[str, object]) -> RuleSettings:
    for threshold in (*COMMON_SETTINGS, *rule.thresholds):
        if threshold.name not in values:
            raise SignalConfigurationError(
                f"{DEFAULT_ORIGIN} ne donne pas {key_of(rule.name, threshold.name)}."
            )
    rule_threshold_names = {threshold.name for threshold in rule.thresholds}
    return RuleSettings(
        enabled=cast(bool, values[ENABLED.name]),
        severity=Severity(cast(str, values[SEVERITY.name])),
        weight=float(cast(float, values[WEIGHT.name])),
        thresholds={name: value for name, value in values.items() if name in rule_threshold_names},
    )


def read_user_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as unreadable:
        raise SignalConfigurationError(
            f"{origin_of(path)} est illisible : {unreadable}."
        ) from unreadable


def checked_settings(text: str, rules: Mapping[str, Rule], origin: str) -> RawSettings:
    tables = rule_tables(parsed(text, origin), rules, origin)
    return {name: checked_values(rules[name], values, origin) for name, values in tables.items()}


def load_configuration(
    rules: Sequence[Rule],
    user_path: Path | None = None,
    default_text: str | None = None,
) -> dict[str, RuleSettings]:
    rules_by_name = {rule.name: rule for rule in rules}
    text = (
        default_text
        if default_text is not None
        else DEFAULT_CONFIGURATION_PATH.read_text(encoding="utf-8")
    )
    merged = checked_settings(text, rules_by_name, DEFAULT_ORIGIN)
    user_text = read_user_text(user_path) if user_path is not None else None
    if user_path is not None and user_text is not None:
        overrides = checked_settings(user_text, rules_by_name, origin_of(user_path))
        for name, values in overrides.items():
            merged[name] = {**merged.get(name, {}), **values}
    return {rule.name: complete_settings(rule, merged.get(rule.name, {})) for rule in rules}
