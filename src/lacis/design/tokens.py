from dataclasses import dataclass

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
        person="#0b7fa3",
        address="#178a60",
        establishment="#6b86d6",
        foreign_company="#8a5cd6",
        identity="#b8329f",
        graph_background="#fbfbfc",
        graph_grid="#eef0f3",
        graph_edge="#7f8898",
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
        person="#4cc3e6",
        address="#4cc79a",
        establishment="#a3b5ef",
        foreign_company="#b28cf5",
        identity="#ec72e2",
        graph_background="#12151a",
        graph_grid="#1a1e25",
        graph_edge="#5f6878",
    ),
)

THEMES = (LIGHT_THEME, DARK_THEME)
