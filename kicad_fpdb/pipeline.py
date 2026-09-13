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
# convention of a small solid silkscreen triangle at the pin-1 corner
# (much more visible than a thin outline notch).
PIN1_MARKER_MM = 0.6


def _nearest_corner(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> tuple[float, float]:
    cx = x0 if abs(px - x0) <= abs(px - x1) else x1
    cy = y0 if abs(py - y0) <= abs(py - y1) else y1
    return cx, cy


def _add_outline(geometry) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)

    cy0x, cy0y = min_x - COURTYARD_MARGIN_MM, min_y - COURTYARD_MARGIN_MM
    cy1x, cy1y = max_x + COURTYARD_MARGIN_MM, max_y + COURTYARD_MARGIN_MM
    geometry.rects.append(Rect(start=(cy0x, cy0y), end=(cy1x, cy1y), layer="F.CrtYd"))

    sx0, sy0 = min_x - SILK_MARGIN_MM, min_y - SILK_MARGIN_MM
    sx1, sy1 = max_x + SILK_MARGIN_MM, max_y + SILK_MARGIN_MM
    corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
    for i in range(4):
        start, end = corners[i], corners[(i + 1) % 4]
        geometry.lines.append(Line(start=start, end=end, layer="F.SilkS"))

    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pad1 is not None:
        cx, cy = _nearest_corner(pad1.at[0], pad1.at[1], sx0, sy0, sx1, sy1)
        # A small filled triangle, apex at the body corner, extending
        # outward away from the body along both edges.
        ox = -1.0 if cx == sx0 else 1.0
        oy = -1.0 if cy == sy0 else 1.0
        geometry.polys.append(Poly(
            points=[(cx, cy), (cx + ox * PIN1_MARKER_MM, cy), (cx, cy + oy * PIN1_MARKER_MM)],
            layer="F.SilkS",
        ))


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

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**resolved.params)
    geometry.name = name
    _add_outline(geometry)
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
