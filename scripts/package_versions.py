import re
from datetime import UTC, datetime

MAINTAINER = "c4seus <c4seus@proton.me>"
RELEASES_URL = "https://github.com/c4seus/lacis/releases"
PRE_RELEASE = re.compile(r"(?<=\d)\.?(dev|a|b|rc)(?=\d)")
VERSION_PATTERN = re.compile(r"\d+(\.\d+)*((a|b|rc)\d+)?(\.post\d+)?(\.dev\d+)?(\+[\w.]+)?")


def is_valid_version(version: str) -> bool:
    return VERSION_PATTERN.fullmatch(version) is not None


def package_version(version: str) -> str:
    public, separator, local = version.partition("+")
    return PRE_RELEASE.sub(lambda match: f"~{match.group(1)}", public) + separator + local


def build_date(environment: dict[str, str]) -> datetime:
    epoch = environment.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), UTC)
    return datetime.now(UTC)
