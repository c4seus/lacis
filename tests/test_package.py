import re

import lacis


def test_version_follows_semantic_versioning() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", lacis.__version__)
