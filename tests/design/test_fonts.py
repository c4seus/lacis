from pathlib import Path

import pytest
from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
from PySide6.QtWidgets import QApplication

from lacis.design import fonts
from lacis.design.fonts import (
    BUNDLED_FONT_FILES,
    FONT_DIRECTORY,
    FontLoadingError,
    application_font,
    load_bundled_fonts,
    system_text_scale,
)
from lacis.design.tokens import FontSizes


def test_the_bundled_font_files_are_in_the_package() -> None:
    for font_file in BUNDLED_FONT_FILES:
        assert (FONT_DIRECTORY / font_file).is_file()


def test_the_font_license_is_shipped_with_the_fonts() -> None:
    assert "SIL Open Font License" in (FONT_DIRECTORY / "OFL.txt").read_text(encoding="utf-8")


def test_loading_the_bundled_fonts_provides_inter(qapp: QApplication) -> None:
    assert "Inter" in load_bundled_fonts()
    assert "Inter" in QFontDatabase.families()


def test_inter_is_available_in_the_three_weights_of_the_tokens(qapp: QApplication) -> None:
    load_bundled_fonts()
    available_styles = set(QFontDatabase.styles("Inter"))
    assert {"Regular", "Medium", "SemiBold"} <= available_styles


def test_the_application_font_is_inter_at_the_body_size(qapp: QApplication) -> None:
    load_bundled_fonts()
    font = application_font()
    assert QFontInfo(font).family() == "Inter"
    assert font.pixelSize() == FontSizes().body


def test_a_missing_font_file_is_reported(
    qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(fonts, "FONT_DIRECTORY", tmp_path)
    with pytest.raises(FontLoadingError, match=r"Inter-Regular\.ttf"):
        load_bundled_fonts()


def test_the_application_font_follows_the_given_sizes(qapp: QApplication) -> None:
    assert application_font(FontSizes().scaled(2)).pixelSize() == 28


def pixel_font(pixel_size: int) -> QFont:
    font = QFont()
    font.setPixelSize(pixel_size)
    return font


def test_a_larger_system_font_enlarges_the_text(qapp: QApplication) -> None:
    assert system_text_scale(pixel_font(30)) == 2.0
    assert system_text_scale(pixel_font(18)) == 1.2


def test_a_usual_or_smaller_system_font_keeps_the_text_as_designed(qapp: QApplication) -> None:
    assert system_text_scale(pixel_font(15)) == 1.0
    assert system_text_scale(pixel_font(12)) == 1.0
    assert system_text_scale() == 1.0
