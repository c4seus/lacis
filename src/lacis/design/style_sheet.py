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

QMenu::separator {{
    height: 1px;
    margin: {spacing.step_1}px 0;
    background-color: {colours.border};
}}

QSplitter::handle {{
    background-color: {colours.border};
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
