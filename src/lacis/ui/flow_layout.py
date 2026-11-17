from typing import override

from PySide6.QtCore import QMargins, QPoint, QRect, QSize, Qt
from PySide6.QtWidgets import QLayout, QLayoutItem, QWidget


def fitted_size(item: QLayoutItem, available_width: int) -> QSize:
    hint = item.sizeHint()
    width = max(min(hint.width(), available_width), item.minimumSize().width())
    if width == hint.width() or not item.hasHeightForWidth():
        return QSize(width, hint.height())
    return QSize(width, item.heightForWidth(width))


class FlowLayout(QLayout):
    def __init__(
        self,
        parent: QWidget | None = None,
        horizontal_spacing: int = 6,
        vertical_spacing: int = 6,
    ) -> None:
        super().__init__(parent)
        self.items: list[QLayoutItem] = []
        self.horizontal_spacing = horizontal_spacing
        self.vertical_spacing = vertical_spacing
        self.setContentsMargins(QMargins(0, 0, 0, 0))

    @override
    def addItem(self, item: QLayoutItem) -> None:
        self.items.append(item)

    @override
    def count(self) -> int:
        return len(self.items)

    @override
    def itemAt(self, index: int) -> QLayoutItem | None:
        return self.items[index] if 0 <= index < len(self.items) else None

    @override
    def takeAt(self, index: int) -> QLayoutItem | None:
        return self.items.pop(index) if 0 <= index < len(self.items) else None

    @override
    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    @override
    def hasHeightForWidth(self) -> bool:
        return True

    @override
    def heightForWidth(self, width: int) -> int:
        return self.arrange(QRect(0, 0, width, 0), move=False)

    @override
    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self.arrange(rect, move=True)

    @override
    def sizeHint(self) -> QSize:
        shown = [item.sizeHint() for item in self.items if not item.isEmpty()]
        spacing = self.horizontal_spacing * max(len(shown) - 1, 0)
        width = sum(hint.width() for hint in shown) + spacing
        height = max((hint.height() for hint in shown), default=0)
        margins = self.contentsMargins()
        return QSize(
            width + margins.left() + margins.right(), height + margins.top() + margins.bottom()
        )

    @override
    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self.items:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        return size + QSize(margins.left() + margins.right(), margins.top() + margins.bottom())

    def arrange(self, rect: QRect, *, move: bool) -> int:
        margins = self.contentsMargins()
        area = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        y = area.y()
        for line in self.lines(area.width()):
            line_height = max(size.height() for _item, size in line)
            if move:
                x = area.x()
                for item, size in line:
                    top = y + (line_height - size.height()) // 2
                    item.setGeometry(QRect(QPoint(x, top), size))
                    x += size.width() + self.horizontal_spacing
            y += line_height + self.vertical_spacing
        if y > area.y():
            y -= self.vertical_spacing
        return y - rect.y() + margins.bottom()

    def lines(self, width: int) -> list[list[tuple[QLayoutItem, QSize]]]:
        lines: list[list[tuple[QLayoutItem, QSize]]] = []
        line: list[tuple[QLayoutItem, QSize]] = []
        used = 0
        for item in self.items:
            if item.isEmpty():
                continue
            size = fitted_size(item, width)
            if line and used + size.width() > width:
                lines.append(line)
                line = []
                used = 0
            line.append((item, size))
            used += size.width() + self.horizontal_spacing
        if line:
            lines.append(line)
        return lines
