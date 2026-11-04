import re

from lacis.storage.errors import InvalidInvestigationNameError

MAXIMUM_NAME_LENGTH = 64
INVESTIGATION_NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
EMPTY_NAME_MESSAGE = "Le nom de l'enquête est obligatoire."
TOO_LONG_NAME_MESSAGE = (
    f"Le nom de l'enquête ne doit pas dépasser {MAXIMUM_NAME_LENGTH} caractères."
)
INVALID_CHARACTERS_MESSAGE = (
    "Le nom de l'enquête ne peut contenir que des lettres minuscules sans accent, "
    "des chiffres et des tirets, sans tiret au début, à la fin ni deux tirets de suite."
)


def validate_investigation_name(name: str) -> str:
    if not name:
        raise InvalidInvestigationNameError(EMPTY_NAME_MESSAGE)
    if len(name) > MAXIMUM_NAME_LENGTH:
        raise InvalidInvestigationNameError(TOO_LONG_NAME_MESSAGE)
    if not INVESTIGATION_NAME_PATTERN.fullmatch(name):
        raise InvalidInvestigationNameError(INVALID_CHARACTERS_MESSAGE)
    return name
