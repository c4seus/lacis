from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from lacis.product import RESOURCE_DIRECTORY

APPLICATION_ICON_DIRECTORY = RESOURCE_DIRECTORY / "icons"
LARGE_MASTER = "application.svg"
SMALL_MASTERS = {
    16: "application-16.svg",
    24: "application-24.svg",
    32: "application-16.svg",
    48: "application-24.svg",
}
WINDOW_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)


def master_for(size: int) -> Path:
    return APPLICATION_ICON_DIRECTORY / SMALL_MASTERS.get(size, LARGE_MASTER)


def rendered_application_icon(size: int) -> QImage:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(str(master_for(size))).render(painter, QRectF(0, 0, size, size))
    painter.end()
    return image


def application_icon() -> QIcon:
    icon = QIcon()
    for size in WINDOW_ICON_SIZES:
        icon.addPixmap(QPixmap.fromImage(rendered_application_icon(size)))
    return icon
