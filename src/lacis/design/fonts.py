from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo

from lacis.design.tokens import FONT_FAMILIES, FontSizes

FONT_DIRECTORY = Path(__file__).resolve().parent.parent / "resources" / "fonts"
BUNDLED_FONT_FILES = ("Inter-Regular.ttf", "Inter-Medium.ttf", "Inter-SemiBold.ttf")
FONT_LOADING_FAILURE = -1
USUAL_SYSTEM_PIXEL_SIZE = 15


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


def application_font(font_sizes: FontSizes | None = None) -> QFont:
    font = QFont()
    font.setFamilies(list(FONT_FAMILIES))
    font.setPixelSize((font_sizes or FontSizes()).body)
    return font


def system_text_scale(system_font: QFont | None = None) -> float:
    font = system_font or QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    return max(1.0, QFontInfo(font).pixelSize() / USUAL_SYSTEM_PIXEL_SIZE)
