"""Derives a descriptive dimension suffix for a generated footprint's
identity/Value text, mirroring each family's own real KiCad naming
convention -- verified against real reference footprints -- so a user
assigning a footprint can sanity-check it at a glance (e.g. "LQFP-32
must be wrong, I know the pitch is 0.85mm"). Families with no natural
single dimension to show (SOT/TSOT: asymmetric per-pin offsets, no
shared pitch) get no suffix, matching real KiCad, which doesn't add
one for these either.
"""

# Standard imperial (inch-derived) chip passive size code -> its metric
# (mm-derived) equivalent, as used in real KiCad's own footprint names
# (e.g. "R_0603_1608Metric"). Not derivable from our own params -- it's
# a fixed industry pairing, not a formula.
IMPERIAL_TO_METRIC = {
    "0201": "0603",
    "0402": "1005",
    "0603": "1608",
    "0805": "2012",
    "1206": "3216",
}


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def fab_outline_bounding_box(geometry) -> tuple[float, float, float, float] | None:
    """Bounding box of the true-body F.Fab outline (a rect or chamfered
    poly, whichever _add_outline drew) -- None if the geometry has no
    F.Fab rect/poly."""
    xs: list[float] = []
    ys: list[float] = []
    for rect in geometry.rects:
        if rect.layer == "F.Fab":
            xs += [rect.start[0], rect.end[0]]
            ys += [rect.start[1], rect.end[1]]
    for poly in geometry.polys:
        if poly.layer == "F.Fab":
            for point in poly.points:
                xs.append(point[0])
                ys.append(point[1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def descriptive_suffix(family: str, variant: str, params: dict, geometry) -> str:
    # The descriptor grammar splits on the first hyphen only, so
    # "R-AXIAL0204" parses to family="R", variant="AXIAL0204" -- check
    # this before the plain chip-resistor/capacitor branch below, or
    # "AXIAL0204" would be (mis)treated as an unknown metric code.
    if family in ("R", "C") and variant.startswith("AXIAL"):
        pad_pitch = params.get("pad_pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pad_pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        return f"_L{_fmt(max_x - min_x)}_D{_fmt(max_y - min_y)}_P{_fmt(pad_pitch)}mm"

    if family == "DIP":
        row_spacing = params.get("row_spacing")
        if row_spacing is None:
            return ""
        return f"_W{_fmt(row_spacing)}mm"

    if family in ("SOIC", "LQFP"):
        pitch = params.get("pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        return f"_{_fmt(max_x - min_x)}x{_fmt(max_y - min_y)}mm_P{_fmt(pitch)}mm"

    if family in ("R", "C"):
        metric = IMPERIAL_TO_METRIC.get(variant)
        if metric is None:
            return ""
        return f"_{metric}Metric"

    return ""
