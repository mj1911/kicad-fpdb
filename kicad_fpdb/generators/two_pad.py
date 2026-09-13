from kicad_fpdb.geometry import FootprintGeometry, Pad


def two_pad_chip(pad_pitch: float, pad_size: tuple[float, float],
                  pad_shape: str = "roundrect", roundrect_rratio: float = 0.25) -> FootprintGeometry:
    half = pad_pitch / 2
    rratio = roundrect_rratio if pad_shape == "roundrect" else None
    pads = [
        Pad(number="1", pad_type="smd", shape=pad_shape, at=(-half, 0.0),
            size=pad_size, roundrect_rratio=rratio),
        Pad(number="2", pad_type="smd", shape=pad_shape, at=(half, 0.0),
            size=pad_size, roundrect_rratio=rratio),
    ]
    return FootprintGeometry(name="", pads=pads)
