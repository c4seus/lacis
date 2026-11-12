from datetime import UTC, datetime

import pytest

from package_versions import build_date, is_valid_version, package_version


def test_python_versions_become_package_versions_that_sort_the_same_way() -> None:
    assert package_version("0.1.0") == "0.1.0"
    assert package_version("0.1.0rc1") == "0.1.0~rc1"
    assert package_version("1.0.0a2") == "1.0.0~a2"
    assert package_version("1.0.0b1") == "1.0.0~b1"
    assert package_version("0.1.dev67+g1a2b3c4") == "0.1~dev67+g1a2b3c4"
    assert package_version("0.1.dev67+g1a2b3c4.d20261112") == "0.1~dev67+g1a2b3c4.d20261112"
    assert package_version("1.2.0.post1") == "1.2.0.post1"


@pytest.mark.parametrize(
    "version",
    ["0.1.0", "1.0.0", "0.1.0rc1", "1.2.0.post1", "0.1.dev67+g1a2b3c4.d20261112"],
)
def test_every_version_hatchling_gives_is_valid(version: str) -> None:
    assert is_valid_version(version)


@pytest.mark.parametrize("version", ["", "unknown", "v0.1.0", "0.1.0 ", "0.1.0-1"])
def test_anything_else_is_not_a_version(version: str) -> None:
    assert not is_valid_version(version)


def test_the_build_date_follows_source_date_epoch() -> None:
    assert build_date({"SOURCE_DATE_EPOCH": "1794499200"}) == datetime(
        2026, 11, 12, 16, 0, tzinfo=UTC
    )
    assert build_date({}).tzinfo is UTC
