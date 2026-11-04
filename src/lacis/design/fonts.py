from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase

from lacis.design.tokens import FONT_FAMILIES, FontSizes

FONT_DIRECTORY = Path(__file__).resolve().parent.parent / "resources" / "fonts"
BUNDLED_FONT_FILES = ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf")
FONT_LOADING_FAILURE = -1


class FontLoadingError(RuntimeError):
    pass


def load_bundled_fonts() -> set[str]:
    loaded_families: set[str] = set()
    for font_file in BUNDLED_FONT_FILES:
        font_path = FONT_DIRECTORY / font_file
        font_identifier = QFontDatabase.addApplicationFont(str(font_path))
        if font_identifier == FONT_LOADING_FAILURE:
            raise FontLoadingError(f"Cannot load the bundled font {font_path}")
        loaded_families.update(QFontDatabase.applicationFontFamilies(font_identifier))
    return loaded_families


def application_font() -> QFont:
    font = QFont()
    font.setFamilies(list(FONT_FAMILIES))
    font.setPixelSize(FontSizes().body)
    return font
