from kicad_fpdb.geometry import FootprintGeometry, Pad


def quad_perimeter(pin_count: int, pitch: float, pad_offset: float,
                    pad_size: tuple[float, float]) -> FootprintGeometry:
    if pin_count % 4 != 0:
        raise ValueError("quad_perimeter requires pin_count divisible by 4")
    pins_per_side = pin_count // 4
    half_span = (pins_per_side - 1) * pitch / 2
    long, short = pad_size

    pads = []
    n = 1
    for i in range(pins_per_side):  # left side
        y = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(-pad_offset, y), size=(long, short), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # bottom side
        x = -half_span + i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, pad_offset), size=(short, long), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # right side
        y = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(pad_offset, y), size=(long, short), roundrect_rratio=0.25))
        n += 1
    for i in range(pins_per_side):  # top side
        x = half_span - i * pitch
        pads.append(Pad(number=str(n), pad_type="smd", shape="roundrect",
                         at=(x, -pad_offset), size=(short, long), roundrect_rratio=0.25))
        n += 1

    return FootprintGeometry(name="", pads=pads)
