from dataclasses import dataclass, field


@dataclass
class Pad:
    number: str
    pad_type: str  # "thru_hole" | "smd"
    shape: str  # "circle" | "roundrect"
    at: tuple[float, float]
    size: tuple[float, float]
    drill: float | None = None
    roundrect_rratio: float | None = None

    def __post_init__(self):
        # Generators pass `at`/`size` through from YAML-derived lists in
        # some code paths (dual_row.py, two_pad.py) and rebuild tuples in
        # others (quad_perimeter.py), leaving Pad.size (and potentially
        # .at) inconsistent with its own `tuple[float, float]` annotation.
        # Normalize once here rather than at every generator call site.
        self.at = tuple(self.at)
        self.size = tuple(self.size)


@dataclass
class Text:
    kind: str  # "reference" | "value"
    text: str
    at: tuple[float, float]
    layer: str


@dataclass
class Line:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str
    width: float = 0.12


@dataclass
class Rect:
    start: tuple[float, float]
    end: tuple[float, float]
    layer: str
    width: float = 0.05
    fill: str = "no"


@dataclass
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)


def pad_bounding_box(pads: list[Pad]) -> tuple[float, float, float, float]:
    """Returns (min_x, min_y, max_x, max_y) spanning all pads, using each
    pad's size as a symmetric extent around its center regardless of shape."""
    min_x = min(p.at[0] - p.size[0] / 2 for p in pads)
    max_x = max(p.at[0] + p.size[0] / 2 for p in pads)
    min_y = min(p.at[1] - p.size[1] / 2 for p in pads)
    max_y = max(p.at[1] + p.size[1] / 2 for p in pads)
    return min_x, min_y, max_x, max_y
