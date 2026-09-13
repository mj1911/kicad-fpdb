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


@dataclass
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
