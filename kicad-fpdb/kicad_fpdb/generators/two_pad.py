from kicad_fpdb.geometry import FootprintGeometry, Pad, clamped_roundrect_rratio


def two_pad_chip(pad_pitch: float, pad_size: tuple[float, float],
                  pad_shape: str = "roundrect", roundrect_rratio: float | None = None,
                  pad_type: str = "smd", drill: float | None = None,
                  centered: bool = True) -> FootprintGeometry:
    if roundrect_rratio is None:
        roundrect_rratio = clamped_roundrect_rratio(pad_size)
    rratio = roundrect_rratio if pad_shape == "roundrect" else None
    if centered:
        x1, x2 = -pad_pitch / 2, pad_pitch / 2
    else:
        # Real THT axial resistors place pad 1 at the origin and pad 2
        # at (pitch, 0), not symmetric about x=0 like SMD chip passives.
        x1, x2 = 0.0, pad_pitch
    pads = [
        Pad(number="1", pad_type=pad_type, shape=pad_shape, at=(x1, 0.0),
            size=pad_size, drill=drill, roundrect_rratio=rratio),
        Pad(number="2", pad_type=pad_type, shape=pad_shape, at=(x2, 0.0),
            size=pad_size, drill=drill, roundrect_rratio=rratio),
    ]
    return FootprintGeometry(name="", pads=pads)
