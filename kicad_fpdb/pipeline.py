import math

from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.asymmetric_dual_row import asymmetric_dual_row
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.geometry import Arc, Circle, Line, Pad, Poly, Rect, Text, clamped_roundrect_rratio, pad_bounding_box
from kicad_fpdb.naming import descriptive_suffix
from kicad_fpdb.rect_union import union_outline
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
    "asymmetric_dual_row": asymmetric_dual_row,
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
# Fixed geometry of the QFN-style filled-triangle pin-1 marker
# (pin1_marker_style="triangle"), verified against 11 real QFN
# reference files spanning 12-80 pins and 0.4/0.5/0.65mm pitch -- see
# docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-design.md.
# Depth (apex to base) along pad 1's own outward axis.
PIN1_TRIANGLE_DEPTH_MM = 0.33
# Half-height of the base, perpendicular to the outward axis, centered
# on pad 1's own center.
PIN1_TRIANGLE_HALF_HEIGHT_MM = 0.24
# Extra clearance, beyond the courtyard margin, between pad 1's own
# edge and the triangle's apex -- the apex lands just past where the
# courtyard line on that side already sits.
PIN1_TRIANGLE_SILK_OFFSET_MM = 0.01
# A second, larger real marker size -- SOIC's wide width class and
# every LQFP variant use this pair instead of the "small" one above,
# verified exact (zero error) against every real sample checked. See
# docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-triangle-marker-
# design.md.
PIN1_TRIANGLE_DEPTH_LARGE_MM = 0.47
PIN1_TRIANGLE_HALF_HEIGHT_LARGE_MM = 0.34
# Length, in mm, of each leg of a QFP-style corner-mark bracket. Real
# KiCad varies this per package (0.3mm for LQFP-32, 0.45mm for LQFP-48);
# this project uses one fixed value for all QFP variants, consistent
# with the "symbolic, not exact" approach documented in
# docs/superpowers/specs/2026-09-14-qfp-corner-mark-silk-design.md.
CORNER_MARK_MM = 0.3
# Clearance, in mm, between a pad's own edge and where a THT axial
# resistor's F.SilkS lead line starts (the far end lands on the body
# rectangle's own edge, already computed elsewhere). Verified as a
# constant 0.24mm across every DIN body size checked (0204/0207/0309/
# 0414), independent of pad or body size.
LEAD_CLEARANCE_MM = 0.24


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


def _add_corner_marks(geometry, sx0: float, sy0: float, sx1: float, sy1: float,
                       side_groups: dict[str, tuple[float, float, float, float]] | None = None,
                       mx: float = COURTYARD_MARGIN_MM, my: float = COURTYARD_MARGIN_MM) -> None:
    # Each leg extends inward from the silk body corner until it reaches
    # the courtyard's own "jog" on that same side -- the point where the
    # stepped F.CrtYd outline transitions from the plain body corner to
    # the adjacent side's own pad-arm edge -- instead of a fixed offset.
    # side_groups uses the same per-side arm rects _quad_side_groups
    # already computes for the courtyard (raw pad-group bbox, not yet
    # margin-expanded -- mx/my are applied here). A missing side (or no
    # side_groups at all) falls back to the old fixed CORNER_MARK_MM
    # length for just that leg -- not reachable today (LQFP/QFN's
    # quad_perimeter always populates all four sides) but keeps this
    # function safe to call with partial data. See docs/superpowers/
    # specs/2026-09-17-corner-mark-extends-to-courtyard-jog-design.md.
    side_groups = side_groups or {}
    corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
    for cx, cy in corners:
        x_dir = 1.0 if cx == sx0 else -1.0
        y_dir = 1.0 if cy == sy0 else -1.0

        horiz_side = side_groups.get("top" if cy == sy0 else "bottom")
        if horiz_side is not None:
            leg_x_end = horiz_side[0] - mx if x_dir > 0 else horiz_side[2] + mx
        else:
            leg_x_end = cx + x_dir * CORNER_MARK_MM

        vert_side = side_groups.get("left" if cx == sx0 else "right")
        if vert_side is not None:
            leg_y_end = vert_side[1] - my if y_dir > 0 else vert_side[3] + my
        else:
            leg_y_end = cy + y_dir * CORNER_MARK_MM

        geometry.lines.append(Line(start=(cx, cy), end=(leg_x_end, cy), layer="F.SilkS"))
        geometry.lines.append(Line(start=(cx, cy), end=(cx, leg_y_end), layer="F.SilkS"))


def _add_outline(geometry, body_width: float | None = None, body_margin: float | None = None,
                  body_size: float | None = None, pin1_marker: bool = True,
                  pin1_marker_style: str = "circle",
                  pin1_triangle_axis: str | None = None, pin1_triangle_size: str = "small",
                  pin1_triangle_anchor_mm: float | None = None,
                  silk_y: float | None = None, silk_half_length: float | None = None,
                  silk_two_lines: bool = False,
                  silk_segments: list[tuple[tuple[float, float], tuple[float, float]]] | None = None,
                  no_silk: bool = False,
                  courtyard_margin_x: float | None = None, courtyard_margin_y: float | None = None,
                  courtyard_body_width: float | None = None, courtyard_body_margin: float | None = None,
                  courtyard_body_size: float | tuple[float, float] | None = None,
                  notch_radius: float | None = None,
                  fab_body_width: float | None = None, fab_body_margin: float | None = None,
                  fab_body_size: float | tuple[float, float] | None = None,
                  fab_outline: bool = False, fab_chamfer: float | None = None,
                  silk_leads: bool = False, fab_leads: bool = False,
                  courtyard_includes_body: bool = False,
                  socket_margin_x: float | None = None, socket_margin_y: float | None = None,
                  courtyard_from_pad_center: bool = False) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
    my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM

    if body_size is None and isinstance(courtyard_body_size, (int, float)):
        # QFP-style: the oversized F.SilkS corner-mark span is a fixed
        # 0.22mm larger than the true body on every real LQFP reference
        # footprint checked (7mm-28mm bodies) -- see docs/superpowers/
        # specs/2026-09-15-qfp-formula-driven-design.md. Guarded to a
        # plain number so SOT's tuple courtyard_body_size (a different,
        # non-square shape with no body_size/corner-mark concept) is
        # left alone.
        body_size = courtyard_body_size + 0.22

    # Computed early (not just where it's drawn on F.Fab below) so the
    # courtyard's own courtyard_includes_body mode can fold it in too.
    fab_body_rect = None
    if fab_body_width is not None and fab_body_margin is not None:
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        fcx = (min_px + max_px) / 2
        fab_body_rect = (
            fcx - fab_body_width / 2, min_py - fab_body_margin,
            fcx + fab_body_width / 2, max_py + fab_body_margin,
        )
    elif fab_body_size is not None:
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        fcx, fcy = (min_px + max_px) / 2, (min_py + max_py) / 2
        fw, fh = fab_body_size if isinstance(fab_body_size, (tuple, list)) else (fab_body_size, fab_body_size)
        fab_body_rect = (fcx - fw / 2, fcy - fh / 2, fcx + fw / 2, fcy + fh / 2)
    elif fab_outline and courtyard_body_width is not None and courtyard_body_margin is not None:
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        fcx = (min_px + max_px) / 2
        fab_body_rect = (
            fcx - courtyard_body_width / 2, min_py - courtyard_body_margin,
            fcx + courtyard_body_width / 2, max_py + courtyard_body_margin,
        )
    elif fab_outline and courtyard_body_size is not None:
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        fcx, fcy = (min_px + max_px) / 2, (min_py + max_py) / 2
        fw, fh = courtyard_body_size if isinstance(courtyard_body_size, (tuple, list)) else (courtyard_body_size, courtyard_body_size)
        fab_body_rect = (fcx - fw / 2, fcy - fh / 2, fcx + fw / 2, fcy + fh / 2)

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
    elif isinstance(courtyard_body_size, (tuple, list)):
        # Real stepped courtyard (SOT-style): union of the true physical
        # (non-square) body rect and each individual pad's own bbox --
        # not grouped per side, so a gap between two same-side pads
        # (e.g. SOT-23-5's right column) stays open rather than being
        # incorrectly bridged. Adjacent pads still merge into one
        # continuous arm wherever their own margin-expanded boxes
        # overlap. See docs/superpowers/specs/2026-09-15-sot23-family-
        # design.md.
        min_px, max_px = _pad_center_extent(geometry.pads, 0)
        min_py, max_py = _pad_center_extent(geometry.pads, 1)
        ccx, ccy = (min_px + max_px) / 2, (min_py + max_py) / 2
        half_w, half_h = courtyard_body_size[0] / 2, courtyard_body_size[1] / 2
        body_rect = (ccx - half_w, ccy - half_h, ccx + half_w, ccy + half_h)
        rects = [body_rect] + [pad_bounding_box([pad]) for pad in geometry.pads]
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
        # Real THT axial resistor courtyard: not a stepped union like
        # SOIC/QFP/SOT -- just the *combined* bounding box of pads and
        # the true F.Fab body (reusing whichever fab_body_* param is
        # already declared, via fab_body_rect above), then a single flat
        # margin around that. Verified this is a plain rectangle (not
        # stepped) because the pad bbox dominates in X while the body
        # dominates in Y, so their combined bbox has no notches to trace.
        if courtyard_from_pad_center:
            # Real KiCad's Socket-flavored courtyard is measured from
            # each pin's own *center*, not the pad bbox edge -- it
            # doesn't move at all when LongPads widens the pad
            # (confirmed byte-identical between DIP-14_Socket and
            # DIP-14_Socket_LongPads), unlike the plain DIP courtyard
            # below, which genuinely does scale with pad size.
            cy0x, cy1x = _pad_center_extent(geometry.pads, 0)
            cy0y, cy1y = _pad_center_extent(geometry.pads, 1)
        else:
            cy0x, cy0y, cy1x, cy1y = min_x, min_y, max_x, max_y
        if courtyard_includes_body and fab_body_rect is not None:
            bx0, by0, bx1, by1 = fab_body_rect
            cy0x, cy0y = min(cy0x, bx0), min(cy0y, by0)
            cy1x, cy1y = max(cy1x, bx1), max(cy1y, by1)
        geometry.rects.append(Rect(
            start=(cy0x - mx, cy0y - my), end=(cy1x + mx, cy1y + my), layer="F.CrtYd",
        ))

    if silk_segments is not None:
        # Verbatim escape hatch for a real notched-body silk shape no
        # formula covers (SOT-23's silk is a body rectangle with bites
        # cut out wherever a pad crosses an edge -- subtractive, unlike
        # the additive union model courtyards use, so not worth a
        # general algorithm for the families that need it so far). Each
        # pair is copied verbatim from the real reference footprint. See
        # docs/superpowers/specs/2026-09-15-sot23-family-design.md.
        for start, end in silk_segments:
            geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))
    elif no_silk:
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
        if silk_leads:
            # Real THT axial resistor lead lines: from each pad's own
            # edge (plus a fixed clearance) to the body rectangle's own
            # edge, in addition to the rectangle itself.
            left_pad = min(geometry.pads, key=lambda p: p.at[0])
            right_pad = max(geometry.pads, key=lambda p: p.at[0])
            geometry.lines.append(Line(
                start=(left_pad.at[0] + left_pad.size[0] / 2 + LEAD_CLEARANCE_MM, left_pad.at[1]),
                end=(sx0, left_pad.at[1]), layer="F.SilkS",
            ))
            geometry.lines.append(Line(
                start=(right_pad.at[0] - right_pad.size[0] / 2 - LEAD_CLEARANCE_MM, right_pad.at[1]),
                end=(sx1, right_pad.at[1]), layer="F.SilkS",
            ))
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
        side_groups = _quad_side_groups(geometry.pads)
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1, side_groups=side_groups, mx=mx, my=my)
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

    if socket_margin_x is not None and socket_margin_y is not None:
        # Real KiCad's "_Socket" DIP/CERDIP variants add one extra plain
        # F.SilkS rectangle around the pads, drawn in addition to
        # whichever body outline was drawn above (e.g. the notched DIP
        # body) -- a separate socket silhouette, not a replacement.
        # Margin is measured from each pin's own *center* (like
        # body_margin, via _pad_center_extent), not the pad bbox edge --
        # the physical socket's footprint doesn't depend on which pad
        # style (plain vs. LongPads' wider oval) was chosen. This only
        # coincided with a pad-edge-based margin (0.53/0.59) as long as
        # every pad was the same 1.6mm size; LongPads' 2.4mm-wide pad
        # exposed the real center-based margin as its own distinct value
        # (1.44mm, vs. 1.33mm for plain pads) -- confirmed exactly
        # against DIP-14_W7.62mm_Socket_LongPads.
        min_cx, max_cx = _pad_center_extent(geometry.pads, 0)
        min_cy, max_cy = _pad_center_extent(geometry.pads, 1)
        geometry.rects.append(Rect(
            start=(min_cx - socket_margin_x, min_cy - socket_margin_y),
            end=(max_cx + socket_margin_x, max_cy + socket_margin_y),
            layer="F.SilkS", width=0.12, fill="no",
        ))

    # Real KiCad also draws the true (non-oversized) physical body on
    # F.Fab, chamfered at pin 1's corner for polarized families -- an
    # assembly-drawing outline, independent of the F.SilkS/F.CrtYd
    # bodies above. Reuses whichever "true body" source is already
    # declared: a family's own fab_body_width/_margin or fab_body_size
    # if given, else (fab_outline=True) the same courtyard_body_width/
    # _margin or courtyard_body_size already used for the courtyard --
    # verified exactly against real SOIC/QFP/SOT-23 reference
    # footprints. See docs/superpowers/specs/2026-09-15-fab-body-
    # outline-design.md.
    if fab_body_rect is not None:
        fsx0, fsy0, fsx1, fsy1 = fab_body_rect
        if fab_chamfer is not None:
            points = [
                (fsx0 + fab_chamfer, fsy0), (fsx1, fsy0), (fsx1, fsy1), (fsx0, fsy1), (fsx0, fsy0 + fab_chamfer),
            ]
            geometry.polys.append(Poly(points=points, layer="F.Fab", width=0.1, fill="no"))
        else:
            geometry.rects.append(Rect(start=(fsx0, fsy0), end=(fsx1, fsy1), layer="F.Fab", width=0.1, fill="no"))
        if fab_leads:
            # Real THT axial resistor F.Fab leads start exactly at each
            # pad's own center (no clearance, unlike the silk leads
            # above) and run to the true body's own edge.
            left_pad = min(geometry.pads, key=lambda p: p.at[0])
            right_pad = max(geometry.pads, key=lambda p: p.at[0])
            geometry.lines.append(Line(start=left_pad.at, end=(fsx0, left_pad.at[1]), layer="F.Fab", width=0.1))
            geometry.lines.append(Line(start=right_pad.at, end=(fsx1, right_pad.at[1]), layer="F.Fab", width=0.1))

    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None and pin1_marker_style == "triangle":
        # A filled triangle pointing outward from pad 1. Real KiCad's own
        # per-family generator scripts each choose which axis the marker
        # extends along independently -- not inferrable from pad shape
        # alone (SOIC/LQFP's pad 1 is wide-in-X, same as QFN's, but their
        # real marker extends in Y, not X) -- so pin1_triangle_axis makes
        # that choice explicit, defaulting to the old shape-based
        # inference (pw > ph -> "x") so QFN's yaml needs no change. See
        # docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-
        # design.md (axis="x", the original QFN case) and
        # docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-triangle-
        # marker-design.md (axis="y", added for SOIC/LQFP).
        pw, ph = pad1.size
        px, py = pad1.at
        mx = courtyard_margin_x if courtyard_margin_x is not None else COURTYARD_MARGIN_MM
        my = courtyard_margin_y if courtyard_margin_y is not None else COURTYARD_MARGIN_MM
        offset = PIN1_TRIANGLE_SILK_OFFSET_MM
        depth, half_span = (
            (PIN1_TRIANGLE_DEPTH_LARGE_MM, PIN1_TRIANGLE_HALF_HEIGHT_LARGE_MM)
            if pin1_triangle_size == "large"
            else (PIN1_TRIANGLE_DEPTH_MM, PIN1_TRIANGLE_HALF_HEIGHT_MM)
        )
        axis = pin1_triangle_axis if pin1_triangle_axis is not None else ("x" if pw > ph else "y")
        if axis == "x":
            direction = -1.0 if px < 0 else 1.0
            apex_x = px + direction * (pw / 2 + mx + offset)
            base_x = apex_x + direction * depth
            points = [(apex_x, py), (base_x, py - half_span), (base_x, py + half_span)]
        else:
            direction = -1.0 if py < 0 else 1.0
            apex_y = py + direction * (ph / 2 + my + offset)
            base_y = apex_y + direction * depth
            if pin1_triangle_anchor_mm is not None:
                # Body-anchored, not pad-relative: real KiCad's own LQFP/
                # SOIC marker sits a fixed distance from the true body
                # edge regardless of where pad 1's own lead happens to
                # extend to -- verified exact (zero error) against every
                # real LQFP/SOIC sample once pad_lead_extension's effect
                # on pad 1's own position was correctly excluded. See
                # docs/superpowers/specs/2026-09-17-soic-lqfp-pin1-
                # triangle-marker-design.md.
                if courtyard_body_width is not None:
                    body_half = courtyard_body_width / 2
                elif isinstance(courtyard_body_size, (tuple, list)):
                    body_half = courtyard_body_size[0] / 2
                else:
                    body_half = courtyard_body_size / 2
                min_px, max_px = _pad_center_extent(geometry.pads, 0)
                center_x = (min_px + max_px) / 2
                perp_dir = -1.0 if px < center_x else 1.0
                apex_x = center_x + perp_dir * (body_half + pin1_triangle_anchor_mm)
            else:
                apex_x = px
            points = [(apex_x, apex_y), (apex_x - half_span, base_y), (apex_x + half_span, base_y)]
        geometry.polys.append(Poly(points=points, layer="F.SilkS"))
    elif pin1_marker and pad1 is not None:
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


def _snap_outward(value: float, sign: float, grid: float = TEXT_GRID_MM) -> float:
    """Snaps to the grid, but only in the direction away from zero along
    `sign` (negative or positive) -- never inward. Rounding to the
    *nearest* grid point (as _snap_to_grid does) can land closer to the
    part than the intended TEXT_MARGIN_MM clearance, visually
    overlapping the outline once a family's margin sits close enough to
    a grid line (confirmed on R-1206's courtyard)."""
    if sign < 0:
        return round(math.floor(value / grid) * grid, 6)
    return round(math.ceil(value / grid) * grid, 6)


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


def _add_reference_and_value_text(geometry, name: str, fab_reference_font_size: float | None = None,
                                   fab_reference_thickness: float | None = None,
                                   fab_reference_rotation: float | None = None) -> None:
    min_x, min_y, max_x, max_y = _outline_bounding_box(geometry)
    center_x = _snap_to_grid((min_x + max_x) / 2)
    geometry.texts.append(
        Text(kind="reference", text="REF**", at=(center_x, _snap_outward(min_y - TEXT_MARGIN_MM, -1)), layer="F.SilkS")
    )
    geometry.texts.append(
        Text(kind="value", text=name, at=(center_x, _snap_outward(max_y + TEXT_MARGIN_MM, 1)), layer="F.Fab")
    )
    # Real KiCad also carries a separate fp_text user "${REFERENCE}" on
    # F.Fab, centered on the footprint's true midpoint (not grid-snapped
    # like Reference/Value above -- real KiCad doesn't snap this either)
    # -- an assembly-drawing overlay that resolves to whatever reference
    # designator gets assigned (e.g. "U1"). Font size defaults to the
    # same 1mm/0.15 used everywhere else; chip passives override it
    # (real KiCad scales it down per package size -- the default badly
    # overflows their tiny courtyard).
    true_center = ((min_x + max_x) / 2, (min_y + max_y) / 2)
    fab_reference_kwargs = {}
    if fab_reference_font_size is not None:
        fab_reference_kwargs["font_size"] = fab_reference_font_size
    if fab_reference_thickness is not None:
        fab_reference_kwargs["thickness"] = fab_reference_thickness
    if fab_reference_rotation is not None:
        fab_reference_kwargs["rotation"] = fab_reference_rotation
    geometry.texts.append(
        Text(kind="fab_reference", text="${REFERENCE}", at=true_center, layer="F.Fab", **fab_reference_kwargs)
    )


# Paste-stencil segmentation formula for an exposed-pad's paste block,
# reverse-engineered from 8 real SOIC-8-1EP reference footprints (all
# split into a 2x2 grid over the EP size range they cover -- larger
# EPs needing more divisions aren't supported yet). Per axis, using
# H = effective_size/2 (half the EP, or its separate solder-mask
# opening override when one exists -- real KiCad computes the paste
# split from *that*, not the copper EP, whenever a Mask override is
# present): each paste sub-pad's size is `_PASTE_SPLIT_SLOPE * H +
# _PASTE_SPLIT_INTERCEPT`, centered at `effective_size / 4`. Fit by
# least squares across all 8 samples; max residual 0.006mm, well
# inside this project's usual real-file rounding tolerance.
_PASTE_SPLIT_SLOPE = 0.8094
_PASTE_SPLIT_INTERCEPT = -0.0057


def _add_exposed_pad(geometry, pin_count: int, ep_size: tuple[float, float],
                      ep_mask_size: tuple[float, float] | None = None,
                      ep_paste_pads: list[tuple[float, float, float, float]] | None = None) -> None:
    ew, eh = ep_size
    # Real KiCad drops F.Mask from the copper heatsink pad itself once a
    # separate mask-opening pad is declared (verified on both
    # EP2.95x4.9mm_Mask* samples) -- the mask pad below covers it instead.
    heatsink_layers = ("F.Cu",) if ep_mask_size is not None else ("F.Cu", "F.Mask")
    heatsink_pad = Pad(
        number=str(pin_count + 1), pad_type="smd", shape="rect",
        at=(0.0, 0.0), size=(ew, eh),
        layers=heatsink_layers, pad_prop="pad_prop_heatsink", zone_connect=2,
    )
    unnumbered_pads = []
    if ep_mask_size is not None:
        mw, mh = ep_mask_size
        unnumbered_pads.append(Pad(
            number="", pad_type="smd", shape="rect",
            at=(0.0, 0.0), size=(mw, mh), layers=("F.Mask",),
        ))
    if ep_paste_pads is not None:
        # Real KiCad splits the paste aperture into more than a 2x2 grid
        # once the EP is large enough (1x2, 3x3, or 4x4 seen so far) --
        # no formula covers all of those, so the caller supplies the
        # exact real sub-pad list instead of it being derived here.
        for x, y, w, h in ep_paste_pads:
            unnumbered_pads.append(Pad(
                number="", pad_type="smd", shape="roundrect",
                at=(x, y), size=(w, h),
                layers=("F.Paste",),
                roundrect_rratio=clamped_roundrect_rratio((w, h)),
            ))
    else:
        eff_w, eff_h = ep_mask_size if ep_mask_size is not None else ep_size
        pos_x, pos_y = eff_w / 4, eff_h / 4
        paste_w = _PASTE_SPLIT_SLOPE * (eff_w / 2) + _PASTE_SPLIT_INTERCEPT
        paste_h = _PASTE_SPLIT_SLOPE * (eff_h / 2) + _PASTE_SPLIT_INTERCEPT
        for sign_x in (-1, 1):
            for sign_y in (-1, 1):
                unnumbered_pads.append(Pad(
                    number="", pad_type="smd", shape="roundrect",
                    at=(sign_x * pos_x, sign_y * pos_y), size=(paste_w, paste_h),
                    layers=("F.Paste",),
                    roundrect_rratio=clamped_roundrect_rratio((paste_w, paste_h)),
                ))
    # Real KiCad orders these as: unnumbered paste/mask pads, then the
    # numbered pads, then the heatsink pad last -- matched here (rather
    # than just appending everything at the end) because the regression
    # suite's pad parser scans from each numbered pad's own "(pad "N""
    # to the *next* one it finds, so an unnumbered pad sitting between
    # pad 9 and EOF would get folded into pad 9's own parsed block.
    geometry.pads[:0] = unnumbered_pads
    geometry.pads.append(heatsink_pad)


def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    params = dict(resolved.params)
    body_width = params.pop("body_width", None)
    body_margin = params.pop("body_margin", None)
    body_size = params.pop("body_size", None)
    pin1_marker = params.pop("pin1_marker", True)
    pin1_marker_style = params.pop("pin1_marker_style", "circle")
    pin1_triangle_axis = params.pop("pin1_triangle_axis", None)
    pin1_triangle_size = params.pop("pin1_triangle_size", "small")
    pin1_triangle_anchor_mm = params.pop("pin1_triangle_anchor_mm", None)
    silk_y = params.pop("silk_y", None)
    silk_half_length = params.pop("silk_half_length", None)
    silk_two_lines = params.pop("silk_two_lines", False)
    silk_segments = params.pop("silk_segments", None)
    no_silk = params.pop("no_silk", False)
    courtyard_margin_x = params.pop("courtyard_margin_x", None)
    courtyard_margin_y = params.pop("courtyard_margin_y", None)
    courtyard_body_width = params.pop("courtyard_body_width", None)
    courtyard_body_margin = params.pop("courtyard_body_margin", None)
    courtyard_body_size = params.pop("courtyard_body_size", None)
    notch_radius = params.pop("notch_radius", None)
    fab_body_width = params.pop("fab_body_width", None)
    fab_body_margin = params.pop("fab_body_margin", None)
    fab_body_size = params.pop("fab_body_size", None)
    fab_outline = params.pop("fab_outline", False)
    fab_chamfer = params.pop("fab_chamfer", None)
    silk_leads = params.pop("silk_leads", False)
    fab_leads = params.pop("fab_leads", False)
    courtyard_includes_body = params.pop("courtyard_includes_body", False)
    fab_reference_font_size = params.pop("fab_reference_font_size", None)
    fab_reference_thickness = params.pop("fab_reference_thickness", None)
    fab_reference_rotation = params.pop("fab_reference_rotation", None)
    solder_mask_margin = params.pop("solder_mask_margin", None)
    solder_paste_margin = params.pop("solder_paste_margin", None)
    socket_margin_x = params.pop("socket_margin_x", None)
    socket_margin_y = params.pop("socket_margin_y", None)
    courtyard_from_pad_center = params.pop("courtyard_from_pad_center", False)
    ep_size = params.pop("ep_size", None)
    ep_mask_size = params.pop("ep_mask_size", None)
    ep_paste_pads = params.pop("ep_paste_pads", None)

    generator_fn = GENERATORS[resolved.generator]
    generator_kwargs = dict(params)
    if resolved.generator == "quad_perimeter":
        # courtyard_body_size is popped above for _add_outline's use on
        # every family (including SOT, whose generator doesn't accept
        # it) -- quad_perimeter is the one generator that also needs it,
        # to derive pad_offset when the yaml doesn't declare one.
        generator_kwargs["courtyard_body_size"] = courtyard_body_size
    geometry = generator_fn(**generator_kwargs)
    geometry.name = name
    if solder_mask_margin is not None or solder_paste_margin is not None:
        for pad in geometry.pads:
            if solder_mask_margin is not None:
                pad.solder_mask_margin = solder_mask_margin
            if solder_paste_margin is not None:
                pad.solder_paste_margin = solder_paste_margin
    _add_outline(geometry, body_width=body_width, body_margin=body_margin, body_size=body_size,
                 pin1_marker=pin1_marker, pin1_marker_style=pin1_marker_style,
                 pin1_triangle_axis=pin1_triangle_axis, pin1_triangle_size=pin1_triangle_size,
                 pin1_triangle_anchor_mm=pin1_triangle_anchor_mm,
                 silk_y=silk_y, silk_half_length=silk_half_length,
                 silk_two_lines=silk_two_lines, silk_segments=silk_segments, no_silk=no_silk,
                 courtyard_margin_x=courtyard_margin_x, courtyard_margin_y=courtyard_margin_y,
                 courtyard_body_width=courtyard_body_width, courtyard_body_margin=courtyard_body_margin,
                 courtyard_body_size=courtyard_body_size,
                 notch_radius=notch_radius,
                 fab_body_width=fab_body_width, fab_body_margin=fab_body_margin, fab_body_size=fab_body_size,
                 fab_outline=fab_outline, fab_chamfer=fab_chamfer,
                 silk_leads=silk_leads, fab_leads=fab_leads, courtyard_includes_body=courtyard_includes_body,
                 socket_margin_x=socket_margin_x, socket_margin_y=socket_margin_y,
                 courtyard_from_pad_center=courtyard_from_pad_center)
    if ep_size is not None:
        # Added after _add_outline, not before: the heatsink/paste pads
        # are all well inside the existing pad-row bounding box, but
        # keeping them out of every silk/courtyard/fab computation
        # entirely avoids any risk of them shifting one, rather than
        # relying on that always staying true.
        _add_exposed_pad(geometry, params["pin_count"], tuple(ep_size),
                          tuple(ep_mask_size) if ep_mask_size is not None else None,
                          [tuple(p) for p in ep_paste_pads] if ep_paste_pads is not None else None)
        # Naming needs these too (built below) -- put back after popping
        # them for the generator call above.
        params["ep_size"] = ep_size
        if ep_mask_size is not None:
            params["ep_mask_size"] = ep_mask_size
        if ep_paste_pads is not None:
            params["ep_paste_pads"] = ep_paste_pads
    # Real KiCad's own footprint identity *is* its descriptive name (e.g.
    # "DIP-16_W7.62mm") -- matching that convention here (rather than a
    # separate display-only label) lets a user sanity-check a generated
    # footprint's real dimensions at a glance, directly from its Value
    # text. See kicad_fpdb.naming for the per-family formats.
    name = name + descriptive_suffix(parsed.family, parsed.variant, params, geometry,
                                      applied_modifiers=resolved.applied_modifiers)
    geometry.name = name
    _add_reference_and_value_text(geometry, name, fab_reference_font_size=fab_reference_font_size,
                                   fab_reference_thickness=fab_reference_thickness,
                                   fab_reference_rotation=fab_reference_rotation)

    return write_kicad_mod(name, geometry)
