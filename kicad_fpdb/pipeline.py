import math

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.geometry import Line, Poly, Rect, Text, pad_bounding_box
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
}

# Margin, in mm, between the pad bounding box and the Reference/Value text
# placed above/below it. Generic default until real silkscreen/courtyard
# geometry exists to anchor text to instead.
TEXT_MARGIN_MM = 1.0

# Generic outline conventions: not meant to pixel-match real KiCad's own
# family-specific outline styles (which vary a lot), just to produce a
# reasonable, consistent courtyard/silkscreen outline for any generator.
SILK_MARGIN_MM = 0.2
COURTYARD_MARGIN_MM = 0.5
# Size of the filled pin-1 marker triangle. Matches real KiCad's own
# convention of a small solid silkscreen triangle pointing at pin 1
# (much more visible than a thin outline notch).
PIN1_MARKER_MM = 0.6
# Length, in mm, of each leg of a QFP-style corner-mark bracket. Real
# KiCad varies this per package (0.3mm for LQFP-32, 0.45mm for LQFP-48);
# this project uses one fixed value for all QFP variants, consistent
# with the "symbolic, not exact" approach documented in
# docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md.
CORNER_MARK_MM = 0.3


def _nearest_corner(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
    cx = x0 if abs(px - x0) <= abs(px - x1) else x1
    cy = y0 if abs(py - y0) <= abs(py - y1) else y1
    return cx, cy


def _pad_center_extent(pads, axis: int) -> tuple[float, float]:
    values = [p.at[axis] for p in pads]
    return min(values), max(values)


def _add_corner_marks(geometry, sx0: float, sy0: float, sx1: float, sy1: float) -> None:
    corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
    for cx, cy in corners:
        x_dir = 1.0 if cx == sx0 else -1.0
        y_dir = 1.0 if cy == sy0 else -1.0
        geometry.lines.append(Line(start=(cx, cy), end=(cx + x_dir * CORNER_MARK_MM, cy), layer="F.SilkS"))
        geometry.lines.append(Line(start=(cx, cy), end=(cx, cy + y_dir * CORNER_MARK_MM), layer="F.SilkS"))


def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  silk_y: float | None = None, silk_half_length: float | None = None,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
    cy0x, cy0y = min_x - mx, min_y - my
    cy1x, cy1y = max_x + mx, max_y + my
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))

    if body_width is not None and body_margin is not None:
        # Real body dimensions: a physical package constant, independent of
        # the pad bounding box. Width is centered on the pad-row centerline;
        # length runs from the first/last pad *center* (not pad edge) plus
        # a fixed margin. See docs/superpowers/specs/2026-09-14-real-body-
        # silk-outline-design.md for the derivation.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        sx0, sx1 = center_x - body_width / 2, center_x + body_width / 2
        sy0, sy1 = min_py - body_margin, max_py + body_margin
        corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
        for i in range(4):
            start, end = corners[i], corners[(i + 1) % 4]
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))
    elif body_size is not None:
        # Real square body size (a physical constant, independent of pad
        # position), centered on the pad centroid. See docs/superpowers/
        # specs/2026-09-14-qfp-corner-mark-silk-design.md.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        center_y = (min_py + max_py) / 2
        half = body_size / 2
        sx0, sx1 = center_x - half, center_x + half
        sy0, sy1 = center_y - half, center_y + half
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1)
    elif silk_y is not None and silk_half_length is not None:
        # Real KiCad draws chip resistors/capacitors with two short
        # silk lines, not a box — the component body is always smaller
        # than its pads, so a box would just outline the pads
        # themselves. Both values are copied verbatim from real
        # reference footprints per variant (no shared formula holds
        # across pad sizes) — see docs/superpowers/specs/2026-09-14-
        # chip-passive-silk-lines-design.md. This mode never computes a
        # body-corner rectangle, so it must not be combined with
        # pin1_marker=True (would raise NameError below) — a non-issue
        # today since every variant using this mode declares
        # pin1_marker: false.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        center_x = (min_px + max_px) / 2
        center_y = (min_py + max_py) / 2
        for y in (center_y - silk_y, center_y + silk_y):
            geometry.lines.append(Line(
                start=(center_x - silk_half_length, y),
                end=(center_x + silk_half_length, y),
                layer="F.SilkS",
            ))
    else:
        sx0, sy0 = min_x - SILK_MARGIN_MM, min_y - SILK_MARGIN_MM
        sx1, sy1 = max_x + SILK_MARGIN_MM, max_y + SILK_MARGIN_MM
        corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
        for i in range(4):
            start, end = corners[i], corners[(i + 1) % 4]
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))

    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None:
        cx, cy = _nearest_corner(pad1.at[0], pad1.at[1], sx0, sy0, sx1, sy1)

        # An isoceles triangle whose sharp tip sits at the body corner,
        # pointing toward pad 1's actual center, with its base offset
        # outward (away from the pad) — an arrow aimed at pin 1, not just
        # a wedge sitting in the corner.
        vx, vy = pad1.at[0] - cx, pad1.at[1] - cy
        length = math.hypot(vx, vy) or 1.0
        ux, uy = vx / length, vy / length
        px, py = -uy, ux

        tip = (cx, cy)
        base_x, base_y = cx - ux * PIN1_MARKER_MM, cy - uy * PIN1_MARKER_MM
        half_width = PIN1_MARKER_MM / 2
        base1 = (base_x + px * half_width, base_y + py * half_width)
        base2 = (base_x - px * half_width, base_y - py * half_width)

        geometry.polys.append(Poly(points=[tip, base1, base2], layer="F.SilkS"))


def _add_reference_and_value_text(geometry, name: str) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)
    center_x = (min_x + max_x) / 2
    geometry.texts.append(
        Text(kind="reference", text="REF**", at=(center_x, min_y - TEXT_MARGIN_MM), layer="F.SilkS")
    )
    geometry.texts.append(
        Text(kind="value", text=name, at=(center_x, max_y + TEXT_MARGIN_MM), layer="F.Fab")
    )


def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    params = dict(resolved.params)
    body_width = params.pop("body_width", None)
    body_margin = params.pop("body_margin", None)
    body_size = params.pop("body_size", None)
    pin1_marker = params.pop("pin1_marker", True)
    silk_y = params.pop("silk_y", None)
    silk_half_length = params.pop("silk_half_length", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
