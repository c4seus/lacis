import re
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"
RULE = re.compile(r"^([a-z][a-z-]*):")
PLATFORM_TARGETS = ("deb", "rpm", "arch", "windows")


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


def test_every_platform_target_stops_early_with_a_message_elsewhere() -> None:
    for target in PLATFORM_TARGETS:
        recipe = recipes()[target]
        assert recipe[0].startswith("@"), target
        assert f'"make {target} needs' in " ".join(recipe[:3]), target


def test_make_deb_lints_only_the_package_it_has_just_built() -> None:
    lint = [line for line in recipes()["deb"] if line.startswith("lintian")]
    assert lint == [
        'lintian --fail-on error "dist/lacis_$$(dpkg-parsechangelog --show-field Version)_all.deb"'
    ]
