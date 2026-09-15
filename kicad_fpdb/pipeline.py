from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.geometry import Arc, Circle, Line, Rect, Text, pad_bounding_box
from kicad_fpdb.rect_union import union_outline
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
}

# Margin, in mm, between the outermost silk/courtyard outline edge and
# the Reference/Value text placed above/below it. Real KiCad's own gap
# here varies a little per family (~0.7-0.8mm checked); this project
# uses one flat value, then snaps the result to TEXT_GRID_MM.
TEXT_MARGIN_MM = 0.7
# Grid, in mm, that Reference/Value text placement snaps to (0.05in),
# matching a common KiCad hand-placement convention rather than real
# KiCad's own generator scripts, whose exact per-family text offsets
# aren't themselves grid-aligned.
TEXT_GRID_MM = 1.27

# Generic outline conventions: not meant to pixel-match real KiCad's own
# family-specific outline styles (which vary a lot), just to produce a
# reasonable, consistent courtyard/silkscreen outline for any generator.
SILK_MARGIN_MM = 0.2
COURTYARD_MARGIN_MM = 0.5
# Diameter, in mm, of the filled pin-1 marker circle.
PIN1_MARKER_MM = 0.6
# Gap, in mm, between pad 1's own edge and the pin-1 marker circle
# drawn above it. No per-pad solder-mask margin is modeled in this
# project's data, so this is sized generously (well beyond typical
# ~0.05-0.1mm mask expansion) to clear the mask opening too, not just
# the copper pad.
PIN1_MARKER_CLEARANCE_MM = 0.3
# Length, in mm, of each leg of a QFP-style corner-mark bracket. Real
# KiCad varies this per package (0.3mm for LQFP-32, 0.45mm for LQFP-48);
# this project uses one fixed value for all QFP variants, consistent
# with the "symbolic, not exact" approach documented in
# docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md.
CORNER_MARK_MM = 0.3


def _pad_center_extent(pads, axis: int) -> tuple[float, float]:
    values = [p.at[axis] for p in pads]
    return min(values), max(values)


def _quad_side_groups(pads) -> dict[str, tuple[float, float, float, float]]:
    groups: dict[str, list] = {"left": [], "right": [], "top": [], "bottom": []}
    for p in pads:
        w, h = p.size
        if w > h:
            groups["left" if p.at[0] < 0 else "right"].append(p)
        else:
            groups["top" if p.at[1] < 0 else "bottom"].append(p)
    return {
        side: (
            min(p.at[0] - p.size[0] / 2 for p in group),
            min(p.at[1] - p.size[1] / 2 for p in group),
            max(p.at[0] + p.size[0] / 2 for p in group),
            max(p.at[1] + p.size[1] / 2 for p in group),
        )
        for side, group in groups.items() if group
    }


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
                  silk_two_lines: bool = False,
                  no_silk: bool = False,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None,
                  courtyard_body_width: float | None = None, courtyard_body_margin: float | None = None,
                  courtyard_body_size: float | None = None,
                  notch_radius: float | None = None) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM

    if courtyard_body_width is not None and courtyard_body_margin is not None:
        # Real stepped courtyard (SOIC-style): union of the true physical
        # body rect and the full pad bbox, independently margin-expanded.
        # courtyard_body_width/_margin are deliberately separate from
        # body_width/body_margin (used for the oversized F.SilkS body) —
        # see docs/superpowers/specs/2026-09-15-stepped-courtyard-design.md.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        ccx = (min_px + max_px) / 2
        body_rect = (
            ccx - courtyard_body_width / 2, min_py - courtyard_body_margin,
            ccx + courtyard_body_width / 2, max_py + courtyard_body_margin,
        )
        rects = [body_rect, (min_x, min_y, max_x, max_y)]
        expanded = [(r[0] - mx, r[1] - my, r[2] + mx, r[3] + my) for r in rects]
        for start, end in union_outline(expanded):
            geometry.lines.append(Line(start=start, end=end, layer="F.CrtYd", width=0.05))
    elif courtyard_body_size is not None:
        # Real stepped courtyard (QFP-style): union of the true physical
        # body square and one pad-group rect per side, independently
        # margin-expanded. courtyard_body_size is deliberately separate
        # from body_size (used for the oversized F.SilkS corner marks).
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        ccx, ccy = (min_px + max_px) / 2, (min_py + max_py) / 2
        half = courtyard_body_size / 2
        body_rect = (ccx - half, ccy - half, ccx + half, ccy + half)
        rects = [body_rect] + list(_quad_side_groups(geometry.pads).values())
        expanded = [(r[0] - mx, r[1] - my, r[2] + mx, r[3] + my) for r in rects]
        for start, end in union_outline(expanded):
            geometry.lines.append(Line(start=start, end=end, layer="F.CrtYd", width=0.05))
    else:
        cy0x, cy0y = min_x - mx, min_y - my
        cy1x, cy1y = max_x + mx, max_y + my
        geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))

    if no_silk:
        # Real KiCad draws no F.SilkS outline at all for the smallest chip
        # passives (e.g. 0201): the body is too small to fit a safely
        # visible line. Declared explicitly per variant, since every other
        # chip-passive size does get silk lines.
        pass
    elif body_width is not None and body_margin is not None:
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
        if notch_radius is not None:
            # Real KiCad cuts a semicircular notch into the DIP body's
            # top edge (the pin-1-side indicator molded into the
            # physical package) — a true semicircle centered at the
            # body's horizontal center, constant radius regardless of
            # pin count or width class. See docs/superpowers/specs/
            # 2026-09-14-dip-notch-arc-design.md. SOIC shares this
            # branch but never declares notch_radius, so it's
            # unaffected.
            notch_left, notch_right = center_x - notch_radius, center_x + notch_radius
            geometry.lines.append(Line(start=(sx0, sy0), end=(notch_left, sy0), layer="F.SilkS"))
            geometry.lines.append(Line(start=(notch_right, sy0), end=(sx1, sy0), layer="F.SilkS"))
            geometry.arcs.append(Arc(
                start=(notch_right, sy0), mid=(center_x, sy0 + notch_radius), end=(notch_left, sy0),
                layer="F.SilkS",
            ))
            geometry.lines.append(Line(start=(sx1, sy0), end=(sx1, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx1, sy1), end=(sx0, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx0, sy1), end=(sx0, sy0), layer="F.SilkS"))
        elif silk_two_lines:
            # Real SOIC silk is just the top/bottom body edges, not a
            # closed rectangle -- no vertical sides.
            geometry.lines.append(Line(start=(sx0, sy0), end=(sx1, sy0), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx0, sy1), end=(sx1, sy1), layer="F.SilkS"))
        else:
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
        # chip-passive-silk-lines-design.md.
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
        # A filled circle directly above pad 1: same X as the pad,
        # offset up past its own top edge (and the circle's own radius,
        # so its *near* edge — not its center — clears the pad by
        # PIN1_MARKER_CLEARANCE_MM) so it sits outside both the copper
        # pad and its solder mask opening. This is independent of the
        # outline mode entirely (unlike the old nearest-corner triangle)
        # — see docs/superpowers/specs/2026-09-14-pin1-circle-marker-
        # design.md. "Above" assumes pin 1 is at the top of the part,
        # true for every generator today.
        cx = pad1.at[0]
        radius = PIN1_MARKER_MM / 2
        cy = pad1.at[1] - pad1.size[1] / 2 - PIN1_MARKER_CLEARANCE_MM - radius
        geometry.circles.append(Circle(center=(cx, cy), radius=radius, layer="F.SilkS"))


def _snap_to_grid(value: float, grid: float = TEXT_GRID_MM) -> float:
    return round(round(value / grid) * grid, 6)


def _outline_bounding_box(geometry) -> tuple[float, float, float, float]:
    """Bounding box of the actual silk/courtyard outline geometry already
    added by _add_outline (rects, lines, arcs) -- deliberately excludes
    circles, since the only circle this project ever draws is the pin-1
    marker, an ornament with no equivalent in real KiCad that shouldn't
    drive text placement."""
    xs: list[float] = []
    ys: list[float] = []
    for rect in geometry.rects:
        xs += [rect.start[0], rect.end[0]]
        ys += [rect.start[1], rect.end[1]]
    for line in geometry.lines:
        xs += [line.start[0], line.end[0]]
        ys += [line.start[1], line.end[1]]
    for arc in geometry.arcs:
        for point in (arc.start, arc.mid, arc.end):
            xs.append(point[0])
            ys.append(point[1])
    return min(xs), min(ys), max(xs), max(ys)


def _add_reference_and_value_text(geometry, name: str) -> None:
    min_x, min_y, max_x, max_y = _outline_bounding_box(geometry)
    center_x = _snap_to_grid((min_x + max_x) / 2)
    geometry.texts.append(
        Text(kind="reference", text="REF**", at=(center_x, _snap_to_grid(min_y - TEXT_MARGIN_MM)), layer="F.SilkS")
    )
    geometry.texts.append(
        Text(kind="value", text=name, at=(center_x, _snap_to_grid(max_y + TEXT_MARGIN_MM)), layer="F.Fab")
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
    silk_two_lines = params.pop("silk_two_lines", False)
    no_silk = params.pop("no_silk", False)
    courtyard_margin_x = params.pop("courtyard_margin_x", None)
    courtyard_margin_y = params.pop("courtyard_margin_y", None)
    courtyard_body_width = params.pop("courtyard_body_width", None)
    courtyard_body_margin = params.pop("courtyard_body_margin", None)
    courtyard_body_size = params.pop("courtyard_body_size", None)
    notch_radius = params.pop("notch_radius", None)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**params)
    geometry.name = name
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, silk_y=silk_y, silk_half_length=silk_half_length,
                 silk_two_lines=silk_two_lines, no_silk=no_silk,
                 courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y,
                 courtyard_body_width=courtyard_body_width, courtyard_body_margin=courtyard_body_margin,
                 courtyard_body_size=courtyard_body_size,
                 notch_radius=notch_radius)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
