from typing import override

from PySide6.QtCore import QEvent, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPen,
    QPolygonF,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QStyleOptionGraphicsItem,
    QWidget,
)

from lacis.design.icons import ColoursProvider
from lacis.design.tokens import FONT_FAMILIES, Colours
from lacis.graph.drawing import SHAPES, GraphDrawing, GraphNode, NodeShape
from lacis.storage.entities import EntityKind

GRAPH_ACCESSIBLE_NAME = "Graphe de l'enquête"
LEGEND_ACCESSIBLE_NAME = "Légende du graphe"
GRID_STEP = 18.0
GRID_DOT_RADIUS = 1.0
FIT_PADDING = 60.0
MAXIMUM_FIT_SCALE = 1.0
BORDER_WIDTH = 2.0
CLOSED_FILL_OPACITY = 0.35
DASH_PATTERN = (3.0, 2.0)
LABEL_MARGIN = 7.0
LABEL_PADDING = 2.0
LABEL_BACKGROUND_OPACITY = 0.92
LABEL_PIXEL_SIZE = 12
SMALL_LABEL_PIXEL_SIZE = 10
NODE_MARGIN = 12.0
LEGEND_MARGIN = 12
LEGEND_SWATCH_SIZE = 10
LEGEND_ENTRIES = (
    (EntityKind.COMPANY, "Entreprise"),
    (EntityKind.PERSON, "Personne"),
    (EntityKind.ADDRESS, "Adresse"),
    (EntityKind.ESTABLISHMENT, "Établissement"),
    (EntityKind.FOREIGN_COMPANY, "Étranger"),
)
HEXAGON_POINTS = ((-0.5, -1.0), (0.5, -1.0), (1.0, 0.0), (0.5, 1.0), (-0.5, 1.0), (-1.0, 0.0))
DIAMOND_POINTS = ((0.0, -1.0), (1.0, 0.0), (0.0, 1.0), (-1.0, 0.0))


def kind_colour(colours: Colours, kind: EntityKind) -> QColor:
    return QColor(getattr(colours, kind.value))


def polygon(points: tuple[tuple[float, float], ...], half_size: float) -> QPolygonF:
    return QPolygonF([QPointF(x * half_size, y * half_size) for x, y in points])


def shape_path(shape: NodeShape, size: float) -> QPainterPath:
    half_size = size / 2
    area = QRectF(-half_size, -half_size, size, size)
    path = QPainterPath()
    if shape is NodeShape.ROUNDED_SQUARE:
        path.addRoundedRect(area, size / 4, size / 4)
    elif shape is NodeShape.DIAMOND:
        path.addPolygon(polygon(DIAMOND_POINTS, half_size))
        path.closeSubpath()
    elif shape is NodeShape.HEXAGON:
        path.addPolygon(polygon(HEXAGON_POINTS, half_size))
        path.closeSubpath()
    else:
        path.addEllipse(area)
    return path


def label_font(kind: EntityKind) -> QFont:
    font = QFont(list(FONT_FAMILIES))
    if kind is EntityKind.ESTABLISHMENT:
        font.setPixelSize(SMALL_LABEL_PIXEL_SIZE)
        font.setWeight(QFont.Weight.Medium)
    else:
        font.setPixelSize(LABEL_PIXEL_SIZE)
        font.setWeight(QFont.Weight.DemiBold)
    return font


def node_fill(colours: Colours, node: GraphNode) -> QColor:
    colour = kind_colour(colours, node.kind)
    if node.closed:
        colour.setAlphaF(CLOSED_FILL_OPACITY)
    return colour


def node_border(colours: Colours, node: GraphNode) -> QPen:
    if node.closed:
        pen = QPen(kind_colour(colours, node.kind), BORDER_WIDTH)
    elif node.partial:
        pen = QPen(QColor(colours.faint_text), BORDER_WIDTH)
    else:
        return QPen(QColor(colours.surface), BORDER_WIDTH)
    pen.setDashPattern(list(DASH_PATTERN))
    return pen


def label_colour(colours: Colours, kind: EntityKind) -> QColor:
    return QColor(colours.muted_text if kind is EntityKind.ESTABLISHMENT else colours.text)


def draw_label_background(painter: QPainter, area: QRectF, colours: Colours) -> None:
    background = QColor(colours.graph_background)
    background.setAlphaF(LABEL_BACKGROUND_OPACITY)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(background)
    padded = area.adjusted(-LABEL_PADDING, -LABEL_PADDING, LABEL_PADDING, LABEL_PADDING)
    painter.drawRoundedRect(padded, LABEL_PADDING * 2, LABEL_PADDING * 2)


class GraphScene(QGraphicsScene):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colours_provider = colours_provider
        self.node_items: dict[str, NodeItem] = {}

    def colours(self) -> Colours:
        return self.colours_provider()

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.clear()
        self.node_items = {}
        for node in drawing.nodes:
            item = NodeItem(node)
            self.addItem(item)
            self.node_items[node.identifier] = item


class NodeItem(QGraphicsItem):
    def __init__(self, node: GraphNode) -> None:
        super().__init__()
        self.node = node
        self.setPos(node.x, node.y)
        self.font = label_font(node.kind)
        self.path = shape_path(node.shape, node.size)
        text_area = QFontMetricsF(self.font).boundingRect(
            QRectF(), Qt.AlignmentFlag.AlignHCenter, node.label
        )
        text_area.moveCenter(QPointF(0, 0))
        text_area.moveTop(node.size / 2 + LABEL_MARGIN)
        self.label_area = text_area

    def colours(self) -> Colours:
        scene = self.scene()
        assert isinstance(scene, GraphScene)
        return scene.colours()

    @override
    def boundingRect(self) -> QRectF:
        half_size = self.node.size / 2 + NODE_MARGIN
        shape_area = QRectF(-half_size, -half_size, half_size * 2, half_size * 2)
        label_area = self.label_area.adjusted(
            -LABEL_PADDING, -LABEL_PADDING, LABEL_PADDING, LABEL_PADDING
        )
        return shape_area.united(label_area)

    @override
    def shape(self) -> QPainterPath:
        return self.path

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        colours = self.colours()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(node_border(colours, self.node))
        painter.setBrush(node_fill(colours, self.node))
        painter.drawPath(self.path)
        draw_label_background(painter, self.label_area, colours)
        painter.setFont(self.font)
        painter.setPen(label_colour(colours, self.node.kind))
        painter.drawText(self.label_area, Qt.AlignmentFlag.AlignHCenter, self.node.label)


class GraphView(QGraphicsView):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphView")
        self.setAccessibleName(GRAPH_ACCESSIBLE_NAME)
        self.graph_scene = GraphScene(colours_provider, self)
        self.setScene(self.graph_scene)
        self.drawing = GraphDrawing()
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.drawing = drawing
        self.graph_scene.show_drawing(drawing)
        self.fit()

    def fit(self) -> None:
        self.resetTransform()
        if not self.drawing.nodes:
            self.setSceneRect(QRectF())
            return
        area = self.graph_scene.itemsBoundingRect().adjusted(
            -FIT_PADDING, -FIT_PADDING, FIT_PADDING, FIT_PADDING
        )
        self.setSceneRect(
            area.adjusted(-area.width(), -area.height(), area.width(), area.height())
        )
        viewport = self.viewport().rect()
        scale = min(
            viewport.width() / area.width(), viewport.height() / area.height(), MAXIMUM_FIT_SCALE
        )
        self.scale(scale, scale)
        self.centerOn(area.center())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self.fit()

    @override
    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in {QEvent.Type.StyleChange, QEvent.Type.PaletteChange}:
            self.viewport().update()

    @override
    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        colours = self.graph_scene.colours()
        painter.fillRect(QRectF(rect), QColor(colours.graph_background))
        painter.save()
        painter.resetTransform()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(colours.graph_grid))
        area = self.viewport().rect()
        row = GRID_STEP / 2
        while row < area.height():
            column = GRID_STEP / 2
            while column < area.width():
                painter.drawEllipse(QPointF(column, row), GRID_DOT_RADIUS, GRID_DOT_RADIUS)
                column += GRID_STEP
            row += GRID_STEP
        painter.restore()


class LegendSwatch(QWidget):
    def __init__(
        self, kind: EntityKind, colours_provider: ColoursProvider, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.colours_provider = colours_provider
        self.setFixedSize(LEGEND_SWATCH_SIZE, LEGEND_SWATCH_SIZE)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QBrush(kind_colour(self.colours_provider(), self.kind)))
        size = LEGEND_SWATCH_SIZE * (0.6 if self.kind is EntityKind.ESTABLISHMENT else 0.9)
        painter.drawPath(shape_path(SHAPES[self.kind], size))
        painter.end()


class GraphLegend(QFrame):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("graphLegend")
        self.setAccessibleName(LEGEND_ACCESSIBLE_NAME)
        self.entry_labels: list[QLabel] = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(10)
        for kind, text in LEGEND_ENTRIES:
            entry = QHBoxLayout()
            entry.setSpacing(5)
            entry.addWidget(LegendSwatch(kind, colours_provider, self))
            label = QLabel(text, self)
            label.setProperty("tone", "legend")
            entry.addWidget(label)
            self.entry_labels.append(label)
            layout.addLayout(entry)

    @property
    def texts(self) -> list[str]:
        return [label.text() for label in self.entry_labels]
