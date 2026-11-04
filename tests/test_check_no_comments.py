from pathlib import Path

from check_no_comments import comment_lines, main


def test_comments_are_reported_with_their_line() -> None:
    source = "value = 1\n# explain the value\nother = 2  # trailing note\n"
    assert list(comment_lines(source)) == [(2, "# explain the value"), (3, "# trailing note")]


def test_shebang_and_tool_directives_are_allowed() -> None:
    source = (
        "#!/usr/bin/env python3\n"
        "import thing  # type: ignore[import-not-found]\n"
        "value = 1  # noqa: E501\n"
        "if False:  # pragma: no cover\n"
        "    pass\n"
    )
    assert list(comment_lines(source)) == []


def test_hash_inside_a_string_is_not_a_comment() -> None:
    assert list(comment_lines('color = "#ffffff"\n')) == []


def test_main_fails_when_a_comment_is_found(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("value = 1  # why\n", encoding="utf-8")
    assert main(tmp_path) == 1


def test_main_passes_on_clean_code(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
    assert main(tmp_path) == 0
