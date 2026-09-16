from collections.abc import Sequence
from dataclasses import dataclass, field


@dataclass
class Pad:
    number: str
    pad_type: str  # "thru_hole" | "smd"
    shape: str  # "circle" | "roundrect"
    # Accepts any 2-element float sequence -- generators pass `at`/`size`
    # through from YAML-derived lists in some code paths (dual_row.py,
    # two_pad.py) and rebuild tuples in others (quad_perimeter.py).
    # __post_init__ normalizes either input to tuple[float, float], the
    # type every reader (writer.py, pipeline.py, etc.) can rely on.
    at: Sequence[float]
    size: Sequence[float]
    drill: float | None = None
    roundrect_rratio: float | None = None
    solder_mask_margin: float | None = None
    solder_paste_margin: float | None = None
    # Overrides for the small set of pads that don't fit the plain
    # pad_type-derived layer set (an exposed-pad heatsink pad, its
    # optional separate mask-opening pad, and its paste-stencil
    # sub-pads) -- see kicad_fpdb.pipeline._add_exposed_pad.
    layers: tuple[str, ...] | None = None
    pad_prop: str | None = None
    zone_connect: int | None = None

    def __post_init__(self):
        at_x, at_y = self.at
        self.at = (at_x, at_y)
        size_x, size_y = self.size
        self.size = (size_x, size_y)


@dataclass
class Text:
    kind: str  # "reference" | "value" | "fab_reference"
    text: str
    at: tuple[float, float]
    layer: str
    font_size: float = 1.0
    thickness: float = 0.15
    rotation: float = 0.0


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
class Poly:
    points: list[tuple[float, float]]
    layer: str
    width: float = 0.12
    fill: str = "yes"


@dataclass
class Circle:
    center: tuple[float, float]
    radius: float
    layer: str
    width: float = 0.12
    fill: str = "yes"


@dataclass
class Arc:
    start: tuple[float, float]
    mid: tuple[float, float]
    end: tuple[float, float]
    layer: str
    width: float = 0.12


@dataclass
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
    texts: list[Text] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)
    rects: list[Rect] = field(default_factory=list)
    polys: list[Poly] = field(default_factory=list)
    circles: list[Circle] = field(default_factory=list)
    arcs: list[Arc] = field(default_factory=list)


def clamped_roundrect_rratio(pad_size: tuple[float, float], nominal: float = 0.25,
                              max_radius_mm: float = 0.25) -> float:
    """Real KiCad's roundrect corner ratio: nominally 0.25, but clamped so
    the resulting corner radius (ratio * min pad dimension) never exceeds
    an absolute 0.25mm -- only visible once a pad's min dimension exceeds
    1mm (0.25 * 1mm == the 0.25mm cap already)."""
    return min(nominal, max_radius_mm / min(pad_size))


def pad_bounding_box(pads: list[Pad]) -> tuple[float, float, float, float]:
    """Returns (min_x, min_y, max_x, max_y) spanning all pads, using each
    pad's size as a symmetric extent around its center regardless of shape."""
    min_x = min(p.at[0] - p.size[0] / 2 for p in pads)
    max_x = max(p.at[0] + p.size[0] / 2 for p in pads)
    min_y = min(p.at[1] - p.size[1] / 2 for p in pads)
    max_y = max(p.at[1] + p.size[1] / 2 for p in pads)
    return min_x, min_y, max_x, max_y
