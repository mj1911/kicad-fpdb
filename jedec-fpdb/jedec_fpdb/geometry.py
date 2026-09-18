"""Plain geometry dataclasses for jedec-fpdb. Independent of
kicad-fpdb's own geometry module -- no shared code between the two
projects (see the design spec's Code sharing section)."""

from dataclasses import dataclass, field


@dataclass
class Pad:
    number: int
    x_mm: float
    y_mm: float
    drill_mm: float
    diameter_mm: float
    shape: str = "circle"  # "circle" (round) or "rect" (pin 1, square)


@dataclass
class RectOutline:
    layer: str
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float


@dataclass
class Footprint:
    name: str
    pads: list[Pad] = field(default_factory=list)
    silk_body: RectOutline | None = None
    courtyard: RectOutline | None = None
