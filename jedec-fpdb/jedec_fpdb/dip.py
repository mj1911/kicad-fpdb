"""DIP footprint generation, purely from JEDEC MS-001 + IPC-7251 -- see
docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md. No
kicad-fpdb code or data is imported or copied.

Pin layout matches how real DIP ICs are physically numbered: pin 1 at
the bottom of the left column, numbering up the left column, across,
then down the right column to the bottom-right pin. Pitch runs along Y
(the body's long axis); row spacing runs along X (the two columns'
separation) -- confirmed against a real DIP-8 reference file, whose
pad 5 (first right-column pin) sits at (row_spacing, pitch * (pins_per_row - 1))
relative to pad 1 at its own origin.
"""

from data import ms001_dip
from jedec_fpdb import ipc7251
from jedec_fpdb.geometry import Footprint, Pad, RectOutline

SUPPORTED_WIDTH_CLASSES = ms001_dip.SUPPORTED_WIDTH_CLASSES


def generate(width_class: str, pin_count: int, density: str = "N") -> Footprint:
    if width_class not in SUPPORTED_WIDTH_CLASSES:
        raise ValueError(
            f"unsupported width_class {width_class!r}, expected one of {SUPPORTED_WIDTH_CLASSES}"
        )
    if pin_count % 2 != 0 or pin_count < 4:
        raise ValueError(f"pin_count must be even and >= 4, got {pin_count}")

    pitch = ms001_dip.PITCH_MM
    row_spacing = ms001_dip.row_spacing_mm(width_class)
    pins_per_row = pin_count // 2

    drill = ipc7251.drill_diameter_mm(ms001_dip.LEAD_WIDTH_MAX_MM, density)
    pad_dia = ipc7251.pad_diameter_mm(ms001_dip.LEAD_WIDTH_MAX_MM, density)

    x_left, x_right = -row_spacing / 2, row_spacing / 2
    y0 = -pitch * (pins_per_row - 1) / 2
    top_y = -y0

    pads = [
        Pad(number=i + 1, x_mm=x_left, y_mm=y0 + i * pitch,
            drill_mm=drill, diameter_mm=pad_dia,
            shape="rect" if i == 0 else "circle")
        for i in range(pins_per_row)
    ]
    pads += [
        Pad(number=pins_per_row + i + 1, x_mm=x_right, y_mm=top_y - i * pitch,
            drill_mm=drill, diameter_mm=pad_dia, shape="circle")
        for i in range(pins_per_row)
    ]

    body_half_x = ms001_dip.body_width_mm(width_class) / 2
    body_half_y = ms001_dip.body_length_mm(width_class, pin_count) / 2
    silk_body = RectOutline("F.SilkS", -body_half_x, -body_half_y, body_half_x, body_half_y)

    # Table 3-5's courtyard rule: excess is added to whichever of the
    # component body or the pad bounding box is larger on that axis,
    # then the resulting full width/height is rounded up to 0.10mm.
    courtyard_excess = ipc7251.courtyard_excess_mm(density)
    pad_bbox_half_x = row_spacing / 2 + pad_dia / 2
    pad_bbox_half_y = top_y + pad_dia / 2
    crtyd_width = ipc7251.round_up_to_0_1mm(2 * (max(body_half_x, pad_bbox_half_x) + courtyard_excess))
    crtyd_height = ipc7251.round_up_to_0_1mm(2 * (max(body_half_y, pad_bbox_half_y) + courtyard_excess))
    courtyard = RectOutline("F.CrtYd", -crtyd_width / 2, -crtyd_height / 2, crtyd_width / 2, crtyd_height / 2)

    name = f"DIP-{pin_count}_{width_class}_{density}"
    return Footprint(name=name, pads=pads, silk_body=silk_body, courtyard=courtyard)
