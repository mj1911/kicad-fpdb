"""Serializes a Footprint to a real .kicad_mod file. An independent
implementation of the KiCad S-expression format -- reuses only format
knowledge, not code, from kicad-fpdb's own writer (see the design
spec's Code sharing section)."""

import uuid
from pathlib import Path

from jedec_fpdb.geometry import Footprint, RectOutline


def _rect_expr(rect: RectOutline, stroke_width_mm: float) -> str:
    return (
        f'\t(fp_rect\n'
        f'\t\t(start {rect.x1_mm:.4f} {rect.y1_mm:.4f}) (end {rect.x2_mm:.4f} {rect.y2_mm:.4f})\n'
        f'\t\t(stroke (width {stroke_width_mm}) (type default))\n'
        f'\t\t(fill none)\n'
        f'\t\t(layer "{rect.layer}")\n'
        f'\t\t(uuid "{uuid.uuid4()}")\n'
        f'\t)'
    )


def _pad_expr(pad) -> str:
    return (
        f'\t(pad "{pad.number}" thru_hole {pad.shape}\n'
        f'\t\t(at {pad.x_mm:.4f} {pad.y_mm:.4f})\n'
        f'\t\t(size {pad.diameter_mm:.4f} {pad.diameter_mm:.4f})\n'
        f'\t\t(drill {pad.drill_mm:.4f})\n'
        f'\t\t(layers "*.Cu" "*.Mask")\n'
        f'\t\t(remove_unused_layers no)\n'
        f'\t\t(uuid "{uuid.uuid4()}")\n'
        f'\t)'
    )


def write_footprint(footprint: Footprint, path: Path) -> None:
    lines = [
        f'(footprint "{footprint.name}"',
        '\t(version 20221018)',
        '\t(generator "jedec_fpdb")',
        '\t(layer "F.Cu")',
        '\t(attr through_hole)',
    ]
    if footprint.silk_body is not None:
        lines.append(_rect_expr(footprint.silk_body, 0.12))
    if footprint.courtyard is not None:
        lines.append(_rect_expr(footprint.courtyard, 0.05))
    for pad in footprint.pads:
        lines.append(_pad_expr(pad))
    lines.append(')')
    path.write_text('\n'.join(lines) + '\n')
