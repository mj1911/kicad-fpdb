from kicad_fpdb.geometry import FootprintGeometry, Pad, clamped_roundrect_rratio

# Real LQFP reference footprints (7mm-28mm bodies) show
# pad_offset == courtyard_body_size/2 + pad_lead_extension, where
# pad_lead_extension is 0.675mm on 5 of 8 samples checked (the rest
# override it) -- see docs/superpowers/specs/
# 2026-09-15-qfp-formula-driven-design.md.
DEFAULT_PAD_LEAD_EXTENSION_MM = 0.675


def quad_perimeter(pin_count: int, pitch: float, pad_size: tuple[float, float],
                    pad_offset: float | None = None,
                    courtyard_body_size: float | None = None,
                    pad_lead_extension: float = DEFAULT_PAD_LEAD_EXTENSION_MM) -> FootprintGeometry:
    if pin_count % 4 != 0:
        raise ValueError("quad_perimeter requires pin_count divisible by 4")
    if pad_offset is None:
        if courtyard_body_size is None:
            raise ValueError("quad_perimeter requires pad_offset or courtyard_body_size")
        pad_offset = courtyard_body_size / 2 + pad_lead_extension
    pins_per_side = pin_count // 4
    half_span = (pins_per_side - 1) * pitch / 2
    long, short = pad_size
    rratio = clamped_roundrect_rratio(pad_size)

    pads = []
    n = 1
    for i in range(pins_per_side):  # left side
        y = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(-pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # bottom side
        x = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # right side
        y = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(pad_offset, y), size=(long, short), roundrect_rratio=rratio))
        n += 1
    for i in range(pins_per_side):  # top side
        x = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, -pad_offset), size=(short, long), roundrect_rratio=rratio))
        n += 1

    return FootprintGeometry(name="", pads=pads)
