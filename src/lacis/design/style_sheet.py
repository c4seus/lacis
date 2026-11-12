from lacis.design.tokens import FONT_FAMILIES, Theme

CONTROL_HEIGHT = 32
SCROLL_BAR_THICKNESS = 10
SCROLL_BAR_MINIMUM_HANDLE_LENGTH = 32


def font_family_list(families: tuple[str, ...]) -> str:
    return ", ".join(f'"{family}"' for family in families)


def build_style_sheet(theme: Theme) -> str:
    colours = theme.colours
    spacing = theme.spacing
    radii = theme.radii
    font_sizes = theme.font_sizes
    font_weights = theme.font_weights
    return f"""
QWidget {{
    color: {colours.text};
    font-family: {font_family_list(FONT_FAMILIES)};
    font-size: {font_sizes.body}px;
    font-weight: {font_weights.regular};
}}

QMainWindow, QDialog {{
    background-color: {colours.background};
}}

QLabel[tone="muted"] {{
    color: {colours.muted_text};
    font-size: {font_sizes.small}px;
}}

QLabel[tone="faint"] {{
    color: {colours.faint_text};
    font-size: {font_sizes.small}px;
}}

QLabel[tone="caption"] {{
    color: {colours.muted_text};
    font-size: {font_sizes.caption}px;
}}

QLabel[tone="current"] {{
    font-size: {font_sizes.small}px;
    font-weight: {font_weights.bold};
}}

QLabel[tone="brand"] {{
    font-size: {font_sizes.large}px;
    font-weight: {font_weights.bold};
}}

QWidget#headerBar {{
    border-bottom: 1px solid {colours.border};
    background-color: {colours.surface};
}}

QLabel[tone="page-title"] {{
    font-size: {font_sizes.heading}px;
    font-weight: {font_weights.bold};
}}

QLabel[tone="subtitle"] {{
    color: {colours.muted_text};
}}

QLabel[tone="card-title"] {{
    font-size: {font_sizes.large}px;
    font-weight: {font_weights.bold};
}}

QScrollArea#homeScreen, QWidget#homePage {{
    background-color: {colours.background};
}}

QFrame#emptyState {{
    border: 1px dashed {colours.strong_border};
    border-radius: {radii.medium}px;
    background-color: transparent;
}}

QLabel[tone="field-label"] {{
    font-size: {font_sizes.small}px;
    font-weight: {font_weights.bold};
}}

QLabel[tone="problem"] {{
    color: {colours.high_severity};
    font-size: {font_sizes.small}px;
}}

QFrame#newInvestigation, QFrame#investigationCard {{
    padding: {spacing.step_2}px;
    border: 1px solid {colours.border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QFrame#investigationCard:hover {{
    border-color: {colours.strong_border};
}}

QFrame#investigationCard:focus {{
    border-color: {colours.accent};
}}

QFrame#notification {{
    border: 1px solid {colours.strong_border};
    border-left: 4px solid {colours.information};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QFrame#notification[kind="success"] {{
    border-left-color: {colours.success};
}}

QFrame#notification[kind="error"] {{
    border-left-color: {colours.high_severity};
}}

QFrame#searchPopup {{
    border: 1px solid {colours.strong_border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QScrollArea#searchList, QWidget#searchListContent {{
    border: none;
    background-color: {colours.surface};
}}

QFrame#searchResult {{
    border-top: 1px solid {colours.border};
    background-color: {colours.surface};
}}

QFrame#searchResult:hover {{
    background-color: {colours.raised_surface};
}}

QFrame#searchResult[current="true"] {{
    background-color: {colours.soft_accent};
}}

QLabel[tone="result-title"] {{
    font-weight: {font_weights.bold};
}}

QLabel[tone="badge-active"], QLabel[tone="badge-closed"], QLabel[tone="badge-outline"] {{
    padding: 1px {spacing.step_2}px;
    border: 1px solid transparent;
    border-radius: {radii.small}px;
    font-size: {font_sizes.caption}px;
    font-weight: {font_weights.medium};
}}

QLabel[tone="badge-active"] {{
    background-color: {colours.soft_success};
    color: {colours.success};
}}

QLabel[tone="badge-closed"] {{
    background-color: {colours.soft_closed};
    color: {colours.closed};
}}

QLabel[tone="badge-outline"] {{
    border-color: {colours.strong_border};
    color: {colours.muted_text};
}}

QLabel[tone="heading"] {{
    font-size: {font_sizes.title}px;
    font-weight: {font_weights.bold};
}}

QPushButton, QToolButton {{
    min-height: {CONTROL_HEIGHT - 2}px;
    padding: 0 {spacing.step_3}px;
    border: 1px solid {colours.strong_border};
    border-radius: {radii.small}px;
    background-color: {colours.surface};
    color: {colours.text};
    font-size: {font_sizes.small}px;
    font-weight: {font_weights.medium};
}}

QPushButton:hover, QToolButton:hover {{
    background-color: {colours.raised_surface};
}}

QPushButton:disabled, QToolButton:disabled {{
    border-color: {colours.border};
    background-color: {colours.raised_surface};
    color: {colours.faint_text};
}}

QPushButton[variant="primary"] {{
    border-color: {colours.accent};
    background-color: {colours.accent};
    color: {colours.text_on_accent};
}}

QPushButton[variant="primary"]:disabled {{
    border-color: {colours.border};
    background-color: {colours.raised_surface};
    color: {colours.faint_text};
}}

QPushButton[variant="subtle"], QToolButton[variant="subtle"] {{
    border-color: transparent;
    background-color: transparent;
    color: {colours.muted_text};
}}

QPushButton[variant="subtle"]:hover, QToolButton[variant="subtle"]:hover {{
    background-color: {colours.raised_surface};
    color: {colours.text};
}}

QPushButton[variant="link"] {{
    min-height: 0;
    padding: 0 2px;
    border: 1px solid transparent;
    background-color: transparent;
    color: {colours.accent};
}}

QPushButton[variant="link"]:hover {{
    text-decoration: underline;
}}

QPushButton[variant="link"]:focus {{
    border-color: {colours.accent};
}}

QFrame#investigationHeader {{
    border-bottom: 1px solid {colours.border};
    background-color: {colours.surface};
}}

QLabel[tone="investigation-title"] {{
    font-size: {font_sizes.large}px;
    font-weight: {font_weights.bold};
}}

QLabel[tone="counter"] {{
    font-weight: {font_weights.bold};
}}

QLabel[tone="counter-alert"] {{
    color: {colours.high_severity};
    font-weight: {font_weights.bold};
}}

QToolButton[variant="icon"] {{
    min-height: 0;
    padding: 0;
    border-color: transparent;
    background-color: transparent;
}}

QToolButton[variant="icon"]:hover {{
    border-color: {colours.border};
    background-color: {colours.raised_surface};
}}

QToolButton[variant="icon"]::menu-indicator {{
    image: none;
    width: 0;
}}

QPushButton:checked, QToolButton:checked {{
    border-color: {colours.accent};
    background-color: {colours.soft_accent};
    color: {colours.accent};
}}

QPushButton:focus, QToolButton:focus {{
    border: 2px solid {colours.accent};
    padding: 0 {spacing.step_3 - 1}px;
}}

QToolButton[variant="icon"]:focus {{
    padding: 0;
}}

QLineEdit, QComboBox, QAbstractSpinBox {{
    min-height: {CONTROL_HEIGHT}px;
    padding: 0 {spacing.step_3}px;
    border: 1px solid {colours.strong_border};
    border-radius: {radii.small}px;
    background-color: {colours.surface};
    color: {colours.text};
    selection-background-color: {colours.soft_accent};
    selection-color: {colours.text};
}}

QLineEdit:focus, QComboBox:focus, QAbstractSpinBox:focus {{
    border: 2px solid {colours.accent};
    padding: 0 {spacing.step_3 - 1}px;
}}

QTextEdit, QPlainTextEdit, QAbstractItemView {{
    border: 1px solid {colours.strong_border};
    border-radius: {radii.small}px;
    background-color: {colours.surface};
    color: {colours.text};
    selection-background-color: {colours.soft_accent};
    selection-color: {colours.text};
}}

QTextEdit:focus, QPlainTextEdit:focus, QAbstractItemView:focus {{
    border: 2px solid {colours.accent};
}}

QCheckBox, QRadioButton {{
    padding: 2px {spacing.step_1}px;
    border: 2px solid transparent;
    border-radius: {radii.small}px;
    spacing: {spacing.step_2}px;
}}

QCheckBox:focus, QRadioButton:focus {{
    border-color: {colours.accent};
}}

QTabBar:focus {{
    border: 2px solid {colours.accent};
    border-radius: {radii.small}px;
}}

QSlider:focus {{
    border: 2px solid {colours.accent};
    border-radius: {radii.small}px;
}}

QLineEdit[problem="true"] {{
    border-color: {colours.high_severity};
}}

QLineEdit[variant="search"] {{
    background-color: {colours.raised_surface};
}}

QLineEdit:disabled, QComboBox:disabled, QAbstractSpinBox:disabled {{
    border-color: {colours.border};
    background-color: {colours.raised_surface};
    color: {colours.faint_text};
}}

QToolTip {{
    padding: {spacing.step_1}px {spacing.step_2}px;
    border: 1px solid {colours.border};
    border-radius: {radii.small}px;
    background-color: {colours.surface};
    color: {colours.text};
    font-size: {font_sizes.small}px;
}}

QMenuBar {{
    border-bottom: 1px solid {colours.border};
    background-color: {colours.surface};
    color: {colours.text};
    font-size: {font_sizes.small}px;
}}

QMenuBar::item {{
    padding: {spacing.step_1}px {spacing.step_3}px;
    border-radius: {radii.small}px;
    background-color: transparent;
    color: {colours.text};
}}

QMenuBar::item:selected {{
    background-color: {colours.soft_accent};
}}

QMenuBar::item:disabled {{
    color: {colours.faint_text};
}}

QMenu {{
    padding: {spacing.step_1}px;
    border: 1px solid {colours.border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QMenu::item {{
    padding: {spacing.step_2}px {spacing.step_3}px;
    border-radius: {radii.small}px;
    color: {colours.text};
}}

QMenu::item:selected {{
    background-color: {colours.soft_accent};
    color: {colours.text};
}}

QMenu::item:disabled {{
    color: {colours.faint_text};
}}

QMenu::separator {{
    height: 1px;
    margin: {spacing.step_1}px 0;
    background-color: {colours.border};
}}

QSplitter::handle {{
    background-color: {colours.border};
}}

QFrame#queueRail {{
    border-right: 1px solid {colours.border};
    background-color: {colours.surface};
}}

QLabel[tone="rail-count"] {{
    min-width: 10px;
    padding: 0 {spacing.step_1}px;
    border-radius: 9px;
    background-color: {colours.high_severity};
    color: {colours.text_on_accent};
    font-size: {font_sizes.caption}px;
    font-weight: {font_weights.bold};
}}

QFrame#queueColumn, QFrame#detailsPanel {{
    background-color: {colours.surface};
}}

QFrame#columnHead {{
    border-bottom: 1px solid {colours.border};
}}

QScrollArea#reviewQueue, QWidget#reviewQueueContent {{
    background-color: {colours.surface};
}}

QFrame#queueRow {{
    border: 1px solid transparent;
    border-radius: {radii.small}px;
}}

QFrame#queueRow:hover {{
    background-color: {colours.raised_surface};
}}

QFrame#queueRow[selected="true"] {{
    border-color: {colours.accent};
    background-color: {colours.soft_accent};
}}

QFrame#queueRow:focus {{
    border: 2px solid {colours.accent};
}}

QLabel[tone="queue-group"] {{
    padding: 10px 10px 4px 10px;
    color: {colours.faint_text};
    font-size: {font_sizes.caption}px;
    font-weight: {font_weights.bold};
    letter-spacing: 1px;
}}

QLabel[tone="queue-title"] {{
    font-size: {font_sizes.small}px;
    font-weight: {font_weights.bold};
}}

QLabel[tone="queue-score"] {{
    color: {colours.faint_text};
    font-size: {font_sizes.caption}px;
    font-weight: {font_weights.medium};
}}

QLabel[tone="queue-detail"] {{
    color: {colours.muted_text};
    font-size: {font_sizes.caption}px;
}}

QLabel[tone="queue-empty"] {{
    padding: 2px 10px 6px 10px;
    color: {colours.muted_text};
    font-size: {font_sizes.caption}px;
}}

QFrame#graphArea {{
    background-color: {colours.graph_background};
}}

QGraphicsView#graphView {{
    border: 2px solid transparent;
}}

QGraphicsView#graphView:focus {{
    border: 2px solid {colours.accent};
}}

QFrame#graphToolbar {{
    border: 1px solid {colours.border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QToolButton#filterChip {{
    min-height: 0;
    padding: 4px 9px;
    border: 1px solid {colours.border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
    color: {colours.text};
    font-size: {font_sizes.small}px;
}}

QToolButton#filterChip[active="true"] {{
    border-color: {colours.accent};
    color: {colours.accent};
}}

QToolButton#filterChip:focus {{
    padding: 3px 8px;
    border: 2px solid {colours.accent};
}}

QToolButton#filterChip::menu-indicator {{
    image: none;
    width: 0;
}}

QFrame#graphLegend {{
    border: 1px solid {colours.border};
    border-radius: {radii.medium}px;
    background-color: {colours.surface};
}}

QLabel[tone="legend"] {{
    color: {colours.muted_text};
    font-size: {font_sizes.caption}px;
}}

QLabel[tone="legend-signal"] {{
    color: {colours.text};
    font-size: {font_sizes.caption}px;
    font-weight: {font_weights.medium};
}}

QLabel[tone="column-title"] {{
    color: {colours.muted_text};
    font-size: {font_sizes.small}px;
    font-weight: {font_weights.bold};
    letter-spacing: 1px;
}}

QTabWidget#detailsTabs::pane {{
    border: none;
    border-top: 1px solid {colours.border};
}}

QTabWidget#detailsTabs QTabBar::tab {{
    padding: {spacing.step_2}px {spacing.step_3}px;
    border: none;
    border-bottom: 2px solid transparent;
    background-color: transparent;
    color: {colours.muted_text};
}}

QTabWidget#detailsTabs QTabBar::tab:selected {{
    border-bottom-color: {colours.accent};
    color: {colours.text};
    font-weight: {font_weights.medium};
}}

QScrollBar:vertical {{
    width: {SCROLL_BAR_THICKNESS}px;
    background-color: transparent;
}}

QScrollBar:horizontal {{
    height: {SCROLL_BAR_THICKNESS}px;
    background-color: transparent;
}}

QScrollBar::handle {{
    border-radius: {SCROLL_BAR_THICKNESS // 2}px;
    background-color: {colours.strong_border};
}}

QScrollBar::handle:vertical {{
    min-height: {SCROLL_BAR_MINIMUM_HANDLE_LENGTH}px;
}}

QScrollBar::handle:horizontal {{
    min-width: {SCROLL_BAR_MINIMUM_HANDLE_LENGTH}px;
}}

QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{
    width: 0;
    height: 0;
    background: none;
}}
""".strip()
