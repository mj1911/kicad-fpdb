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
class FootprintGeometry:
    name: str
    pads: list[Pad] = field(default_factory=list)
