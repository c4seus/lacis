import re
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"
RULE = re.compile(r"^([a-z][a-z-]*):")


def recipes() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        rule = RULE.match(line)
        if rule is not None:
            current = rules.setdefault(rule.group(1), [])
        elif line.startswith("\t") and current is not None:
            current.append(line.strip())
        else:
            current = None
    return rules


def test_no_recipe_hides_the_failure_of_a_command_behind_a_pipe() -> None:
    piped = [line for lines in recipes().values() for line in lines if " | " in line]
    assert piped == []


def test_make_arch_fails_on_a_namcap_error() -> None:
    assert '! grep -q " E: " build/arch/namcap.txt' in recipes()["arch"]
