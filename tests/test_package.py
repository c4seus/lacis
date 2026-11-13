import re
from importlib.metadata import version

import pytest

import lacis

PUBLIC_OR_DEVELOPMENT_VERSION = re.compile(
    r"\d+(?:\.\d+)*(?:(?:a|b|rc)\d+)?(?:\.post\d+)?(?:\.dev\d+)?(?:\+[0-9a-z.]+)?"
)


def test_version_is_a_valid_python_package_version() -> None:
    assert PUBLIC_OR_DEVELOPMENT_VERSION.fullmatch(lacis.__version__)


def test_version_is_the_one_of_the_installed_package() -> None:
    assert lacis.__version__ == version("lacis")


@pytest.mark.parametrize(
    "valid_version",
    ["0.3.1", "0.2.0rc1", "0.3.2.dev4+g1a2b3c4", "0.1.dev20+g8068efc40.d20261104"],
)
def test_version_pattern_accepts_releases_pre_releases_and_development_versions(
    valid_version: str,
) -> None:
    assert PUBLIC_OR_DEVELOPMENT_VERSION.fullmatch(valid_version)


@pytest.mark.parametrize("invalid_version", ["v0.3.1", "0.2.0-rc.1", "0.3.", "latest"])
def test_version_pattern_rejects_malformed_versions(invalid_version: str) -> None:
    assert not PUBLIC_OR_DEVELOPMENT_VERSION.fullmatch(invalid_version)
