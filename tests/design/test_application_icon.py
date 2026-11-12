from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from lacis.design.application_icon import (
    APPLICATION_ICON_DIRECTORY,
    WINDOW_ICON_SIZES,
    application_icon,
    master_for,
    rendered_application_icon,
)

COMPANY_BLUE = QColor("#3d63dd")
LINK_GREY = QColor("#545c69")
TILE_WHITE = QColor("#ffffff")


def opaque(image: QImage, x: int, y: int) -> QColor:
    colour = image.pixelColor(x, y)
    assert colour.alpha() == 255
    return colour


def test_small_sizes_use_masters_drawn_on_their_pixel_grid() -> None:
    assert master_for(16).name == "application-16.svg"
    assert master_for(32).name == "application-16.svg"
    assert master_for(24).name == "application-24.svg"
    assert master_for(48).name == "application-24.svg"
    assert master_for(64).name == "application.svg"
    assert master_for(512).name == "application.svg"
    assert all(master_for(size).parent == APPLICATION_ICON_DIRECTORY for size in (16, 512))


def test_the_16_pixel_icon_is_sharp() -> None:
    icon = rendered_application_icon(16)
    assert icon.size() == QSize(16, 16)
    assert all(opaque(icon, x, y) == COMPANY_BLUE for x in range(2, 7) for y in range(2, 7))
    assert opaque(icon, 7, 4) == LINK_GREY
    assert opaque(icon, 8, 4) == LINK_GREY
    assert opaque(icon, 2, 7) == TILE_WHITE
    assert icon.pixelColor(0, 0).alpha() == 0


def test_the_24_pixel_icon_is_sharp() -> None:
    icon = rendered_application_icon(24)
    assert all(opaque(icon, x, y) == COMPANY_BLUE for x in range(4, 8) for y in range(5, 9))
    assert all(opaque(icon, x, y) == LINK_GREY for x in range(10, 14) for y in (6, 7))
    assert opaque(icon, 3, 10) == TILE_WHITE


def test_large_sizes_are_drawn_from_the_vector_master() -> None:
    icon = rendered_application_icon(512)
    assert icon.size() == QSize(512, 512)
    assert opaque(icon, 160, 175) == COMPANY_BLUE
    assert icon.pixelColor(10, 10).alpha() == 0


def test_the_window_icon_has_every_size(qapp: QApplication) -> None:
    icon = application_icon()
    assert icon.availableSizes() == [QSize(size, size) for size in WINDOW_ICON_SIZES]
    small = icon.pixmap(QSize(16, 16)).toImage()
    assert small.pixelColor(4, 4) == COMPANY_BLUE
