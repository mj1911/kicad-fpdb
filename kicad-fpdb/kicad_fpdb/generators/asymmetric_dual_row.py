from kicad_fpdb.geometry import FootprintGeometry, Pad, clamped_roundrect_rratio


def asymmetric_dual_row(left_offsets: list[float], right_offsets: list[float],
                         row_spacing: float, pad_size: tuple[float, float],
                         pad_shape: str, pad_type: str,
                         drill: float | None = None) -> FootprintGeometry:
    rratio = clamped_roundrect_rratio(pad_size) if pad_shape == "roundrect" else None
    half = row_spacing / 2

    pads = []
    n = 1
    for y in left_offsets:
        pads.append(Pad(number=str(n), pad_type=pad_type, shape=pad_shape,
                         at=(-half, y), size=pad_size, drill=drill, roundrect_rratio=rratio))
        n += 1
    for y in right_offsets:
        pads.append(Pad(number=str(n), pad_type=pad_type, shape=pad_shape,
                         at=(half, y), size=pad_size, drill=drill, roundrect_rratio=rratio))
        n += 1

    return FootprintGeometry(name="", pads=pads)
