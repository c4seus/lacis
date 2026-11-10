import math
from typing import override

from PySide6.QtCore import QEvent, QLineF, QPointF, QRect, QRectF, Qt
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
from lacis.graph.drawing import SHAPES, EdgeKind, GraphDrawing, GraphEdge, GraphNode, NodeShape
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
EDGE_WIDTHS = {EdgeKind.DIRECTS: 1.6, EdgeKind.STRUCTURE: 1.0, EdgeKind.IDENTITY: 2.0}
IDENTITY_DASH_PATTERN = (3.0, 2.0)
ARROW_LENGTH = 8.0
ARROW_HALF_WIDTH = 4.0
EDGE_LABEL_PIXEL_SIZE = 10
EDGE_MARGIN = 4.0
BOUNDARY_STEPS = 24
RIGHT_ANGLE = 90.0
HALF_TURN = 180.0
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


def edge_colour(colours: Colours, kind: EdgeKind) -> QColor:
    if kind is EdgeKind.DIRECTS:
        return QColor(colours.person)
    if kind is EdgeKind.IDENTITY:
        return QColor(colours.identity)
    return QColor(colours.graph_edge)


def edge_pen(colours: Colours, kind: EdgeKind) -> QPen:
    pen = QPen(edge_colour(colours, kind), EDGE_WIDTHS[kind])
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    if kind is EdgeKind.IDENTITY:
        pen.setDashPattern(list(IDENTITY_DASH_PATTERN))
    return pen


def edge_label_font(kind: EdgeKind) -> QFont:
    font = QFont(list(FONT_FAMILIES))
    font.setPixelSize(EDGE_LABEL_PIXEL_SIZE)
    font.setWeight(QFont.Weight.DemiBold if kind is EdgeKind.IDENTITY else QFont.Weight.Normal)
    return font


def edge_label_colour(colours: Colours, kind: EdgeKind) -> QColor:
    return QColor(colours.identity if kind is EdgeKind.IDENTITY else colours.muted_text)


def boundary_point(path: QPainterPath, centre: QPointF, towards: QPointF) -> QPointF:
    inside = 0.0
    outside = 1.0
    for _ in range(BOUNDARY_STEPS):
        middle = (inside + outside) / 2
        if path.contains((towards - centre) * middle):
            inside = middle
        else:
            outside = middle
    return centre + (towards - centre) * outside


def upright_angle(start: QPointF, end: QPointF) -> float:
    angle = math.degrees(math.atan2(end.y() - start.y(), end.x() - start.x()))
    if angle > RIGHT_ANGLE:
        return angle - HALF_TURN
    if angle <= -RIGHT_ANGLE:
        return angle + HALF_TURN
    return angle


def arrow_head(tip: QPointF, start: QPointF) -> QPolygonF:
    line = QLineF(tip, start)
    if line.length() == 0:
        return QPolygonF()
    direction = line.unitVector()
    along = QPointF(direction.dx(), direction.dy()) * ARROW_LENGTH
    across = QPointF(-direction.dy(), direction.dx()) * ARROW_HALF_WIDTH
    base = tip + along
    return QPolygonF([tip, base + across, base - across])


class GraphScene(QGraphicsScene):
    def __init__(self, colours_provider: ColoursProvider, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.colours_provider = colours_provider
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []

    def colours(self) -> Colours:
        return self.colours_provider()

    def show_drawing(self, drawing: GraphDrawing) -> None:
        self.clear()
        self.node_items = {}
        for node in drawing.nodes:
            item = NodeItem(node)
            self.addItem(item)
            self.node_items[node.identifier] = item
        self.edge_items = []
        for edge in drawing.edges:
            source = self.node_items[edge.source]
            target = self.node_items[edge.target]
            edge_item = EdgeItem(edge, source, target)
            self.addItem(edge_item)
            self.edge_items.append(edge_item)


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


class EdgeItem(QGraphicsItem):
    def __init__(self, edge: GraphEdge, source: "NodeItem", target: "NodeItem") -> None:
        super().__init__()
        self.edge = edge
        self.setZValue(-1)
        source_centre = source.pos()
        target_centre = target.pos()
        self.start = boundary_point(source.path, source_centre, target_centre)
        self.end = boundary_point(target.path, target_centre, source_centre)
        self.arrow = arrow_head(self.end, self.start) if edge.has_arrow else QPolygonF()
        self.line_end = (
            (self.arrow.at(1) + self.arrow.at(2)) / 2
            if edge.has_arrow and self.arrow
            else self.end
        )
        self.font = edge_label_font(edge.kind)
        self.label_area = QFontMetricsF(self.font).boundingRect(edge.label)
        self.label_area.moveCenter(QPointF(0, 0))
        self.label_angle = upright_angle(self.start, self.end)

    @property
    def middle(self) -> QPointF:
        return (self.start + self.end) / 2

    def colours(self) -> Colours:
        scene = self.scene()
        assert isinstance(scene, GraphScene)
        return scene.colours()

    @override
    def boundingRect(self) -> QRectF:
        line_area = QRectF(self.start, self.end).normalized()
        line_area = line_area.united(self.arrow.boundingRect())
        reach = max(self.label_area.width(), self.label_area.height()) / 2 + LABEL_PADDING
        label_area = QRectF(
            self.middle - QPointF(reach, reach), self.middle + QPointF(reach, reach)
        )
        if self.edge.label:
            line_area = line_area.united(label_area)
        return line_area.adjusted(-EDGE_MARGIN, -EDGE_MARGIN, EDGE_MARGIN, EDGE_MARGIN)

    @override
    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        colours = self.colours()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(edge_pen(colours, self.edge.kind))
        painter.drawLine(QLineF(self.start, self.line_end))
        if self.edge.has_arrow:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(edge_colour(colours, self.edge.kind))
            painter.drawPolygon(self.arrow)
        if not self.edge.label:
            return
        painter.save()
        painter.translate(self.middle)
        painter.rotate(self.label_angle)
        draw_label_background(painter, self.label_area, colours)
        painter.setFont(self.font)
        painter.setPen(edge_label_colour(colours, self.edge.kind))
        painter.drawText(self.label_area, Qt.AlignmentFlag.AlignCenter, self.edge.label)
        painter.restore()


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
