from dataclasses import astuple, dataclass, replace

FONT_FAMILIES = ("Inter", "Segoe UI", "Noto Sans", "Liberation Sans", "Arial", "sans-serif")
MONOSPACE_FONT_FAMILIES = (
    "JetBrains Mono",
    "Cascadia Mono",
    "Consolas",
    "DejaVu Sans Mono",
    "Liberation Mono",
    "monospace",
)


@dataclass(frozen=True)
class Colours:
    background: str
    surface: str
    raised_surface: str
    border: str
    strong_border: str
    text: str
    muted_text: str
    faint_text: str
    accent: str
    soft_accent: str
    text_on_accent: str
    high_severity: str
    soft_high_severity: str
    medium_severity: str
    soft_medium_severity: str
    low_severity: str
    soft_low_severity: str
    information: str
    soft_information: str
    success: str
    soft_success: str
    closed: str
    soft_closed: str
    demonstration: str
    soft_demonstration: str
    company: str
    person: str
    address: str
    establishment: str
    foreign_company: str
    identity: str
    graph_background: str
    graph_grid: str
    graph_edge: str


@dataclass(frozen=True)
class Spacing:
    step_1: int = 4
    step_2: int = 8
    step_3: int = 12
    step_4: int = 16
    step_5: int = 20
    step_6: int = 24
    step_8: int = 32
    step_10: int = 40
    step_12: int = 48


@dataclass(frozen=True)
class Radii:
    small: int = 4
    medium: int = 8
    pill: int = 999


@dataclass(frozen=True)
class FontSizes:
    caption: int = 12
    small: int = 13
    body: int = 14
    large: int = 16
    title: int = 19
    heading: int = 24

    def scaled(self, factor: float) -> "FontSizes":
        return FontSizes(*(max(1, round(size * factor)) for size in astuple(self)))


@dataclass(frozen=True)
class FontWeights:
    regular: int = 400
    medium: int = 500
    bold: int = 600


@dataclass(frozen=True)
class Theme:
    name: str
    colours: Colours
    spacing: Spacing = Spacing()
    radii: Radii = Radii()
    font_sizes: FontSizes = FontSizes()
    font_weights: FontWeights = FontWeights()
    high_contrast: bool = False

    def with_text_scale(self, factor: float) -> "Theme":
        font_sizes = FontSizes().scaled(factor)
        return self if font_sizes == self.font_sizes else replace(self, font_sizes=font_sizes)


LIGHT_THEME = Theme(
    name="light",
    colours=Colours(
        background="#f4f5f7",
        surface="#ffffff",
        raised_surface="#f8f9fb",
        border="#e2e5ea",
        strong_border="#7f8898",
        text="#171a1f",
        muted_text="#545c69",
        faint_text="#687180",
        accent="#2f55d4",
        soft_accent="#e8eefc",
        text_on_accent="#ffffff",
        high_severity="#b42318",
        soft_high_severity="#fdecea",
        medium_severity="#a84d00",
        soft_medium_severity="#fff1e3",
        low_severity="#7a5c00",
        soft_low_severity="#fdf6d8",
        information="#545c69",
        soft_information="#eef0f3",
        success="#17693f",
        soft_success="#e4f4ec",
        closed="#5f6773",
        soft_closed="#eceef1",
        demonstration="#6e4400",
        soft_demonstration="#fff4dc",
        company="#3d63dd",
        person="#c9831b",
        address="#1f9a6e",
        establishment="#379db3",
        foreign_company="#8a5cd6",
        identity="#bc37b4",
        graph_background="#fbfbfc",
        graph_grid="#eef0f3",
        graph_edge="#8893a4",
    ),
)

DARK_THEME = Theme(
    name="dark",
    colours=Colours(
        background="#0f1115",
        surface="#171a20",
        raised_surface="#1c2027",
        border="#2a2f38",
        strong_border="#6b7383",
        text="#e8eaee",
        muted_text="#a9b1bd",
        faint_text="#8f98a6",
        accent="#7c9cff",
        soft_accent="#1e2a4a",
        text_on_accent="#0f1115",
        high_severity="#ff7b72",
        soft_high_severity="#3a1717",
        medium_severity="#ffab5e",
        soft_medium_severity="#3a2614",
        low_severity="#e6c84f",
        soft_low_severity="#353010",
        information="#a9b1bd",
        soft_information="#252a33",
        success="#5fd39a",
        soft_success="#13301f",
        closed="#a3abb7",
        soft_closed="#262b33",
        demonstration="#f3c46b",
        soft_demonstration="#2e2510",
        company="#7c9cff",
        person="#f2b04e",
        address="#4cc79a",
        establishment="#5cc3d8",
        foreign_company="#b28cf5",
        identity="#ec72e2",
        graph_background="#12151a",
        graph_grid="#1a1e25",
        graph_edge="#5a6374",
    ),
)

HIGH_CONTRAST_LIGHT_THEME = Theme(
    name="high-contrast-light",
    high_contrast=True,
    colours=Colours(
        background="#ffffff",
        surface="#ffffff",
        raised_surface="#f2f2f2",
        border="#6b6b6b",
        strong_border="#000000",
        text="#000000",
        muted_text="#1f1f1f",
        faint_text="#333333",
        accent="#0033b3",
        soft_accent="#dde6ff",
        text_on_accent="#ffffff",
        high_severity="#8f0000",
        soft_high_severity="#ffe5e5",
        medium_severity="#803a00",
        soft_medium_severity="#fff0e0",
        low_severity="#5c4600",
        soft_low_severity="#fff8d6",
        information="#1f1f1f",
        soft_information="#ededed",
        success="#00592f",
        soft_success="#e0f5ea",
        closed="#3d3d3d",
        soft_closed="#ebebeb",
        demonstration="#5c3a00",
        soft_demonstration="#fff2d6",
        company="#1f4fd1",
        person="#9a5200",
        address="#00704d",
        establishment="#006b80",
        foreign_company="#6a2fc4",
        identity="#8a0f78",
        graph_background="#ffffff",
        graph_grid="#f0f0f0",
        graph_edge="#4d4d4d",
    ),
)

HIGH_CONTRAST_DARK_THEME = Theme(
    name="high-contrast-dark",
    high_contrast=True,
    colours=Colours(
        background="#000000",
        surface="#000000",
        raised_surface="#141414",
        border="#9a9a9a",
        strong_border="#ffffff",
        text="#ffffff",
        muted_text="#e6e6e6",
        faint_text="#cccccc",
        accent="#ffd60a",
        soft_accent="#2b2400",
        text_on_accent="#000000",
        high_severity="#ff8080",
        soft_high_severity="#330000",
        medium_severity="#ffb366",
        soft_medium_severity="#331a00",
        low_severity="#ffe14d",
        soft_low_severity="#2e2600",
        information="#e6e6e6",
        soft_information="#1f1f1f",
        success="#66e0a3",
        soft_success="#002614",
        closed="#d9d9d9",
        soft_closed="#262626",
        demonstration="#ffd27a",
        soft_demonstration="#2e2200",
        company="#8fb3ff",
        person="#ffbf47",
        address="#4de0a8",
        establishment="#5ce1f5",
        foreign_company="#d1a8ff",
        identity="#ff8ae8",
        graph_background="#000000",
        graph_grid="#1a1a1a",
        graph_edge="#b3b3b3",
    ),
)

THEMES = (LIGHT_THEME, DARK_THEME, HIGH_CONTRAST_LIGHT_THEME, HIGH_CONTRAST_DARK_THEME)
