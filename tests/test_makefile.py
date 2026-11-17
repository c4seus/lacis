import re
from pathlib import Path

MAKEFILE = Path(__file__).resolve().parent.parent / "Makefile"
CONTRIBUTING = MAKEFILE.parent / "CONTRIBUTING.md"
RULE = re.compile(r"^([a-z][a-z-]*):")
PLATFORM_TARGETS = ("deb", "rpm", "arch", "windows")
WEBSITE_TARGETS = ("site", "site-preview")


def makefile() -> str:
    return MAKEFILE.read_text(encoding="utf-8")


def phony_targets() -> list[str]:
    found = re.search(r"^\.PHONY: (.+)$", makefile().replace("\\\n", " "), re.MULTILINE)
    assert found is not None
    return found.group(1).split()


def summarized_targets() -> list[str]:
    return re.findall(r'^\t@echo "  ([a-z-]+) ', makefile(), re.MULTILINE)


def recipes() -> dict[str, list[str]]:
    rules: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in makefile().splitlines():
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


def test_every_website_target_checks_the_version_of_node_of_the_website_first() -> None:
    assert "\nSITE_NODE := $(shell cat site/.node-version)\n" in makefile()
    first_lines = [recipes()[target][0] for target in WEBSITE_TARGETS]
    assert first_lines == ["@$(CHECK_SITE_NODE)"] * len(WEBSITE_TARGETS)
    assert "\t@$(CHECK_SITE_NODE)\n\tnpm --prefix site ci\n" in makefile()


def test_make_deb_lints_only_the_package_it_has_just_built() -> None:
    lint = [line for line in recipes()["deb"] if line.startswith("lintian")]
    assert lint == [
        'lintian --fail-on error "dist/lacis_$$(dpkg-parsechangelog --show-field Version)_all.deb"'
    ]


def test_make_alone_prints_the_summary_of_the_targets() -> None:
    assert re.search(r"^\.DEFAULT_GOAL := help$", makefile(), re.MULTILINE)
    assert recipes()["help"][0] == '@echo "Usage: make TARGET"'


def test_every_target_is_phony_and_in_the_summary() -> None:
    assert sorted(recipes()) == sorted(phony_targets())
    assert sorted(summarized_targets()) == sorted(set(phony_targets()) - {"help"})


def test_the_contributing_guide_describes_every_target() -> None:
    guide = CONTRIBUTING.read_text(encoding="utf-8")
    described = re.findall(r"^\| `make ([a-z-]+)` \|", guide, re.MULTILINE)
    assert sorted(described) == sorted(set(phony_targets()) - {"help"})
