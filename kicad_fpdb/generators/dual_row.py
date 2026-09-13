from kicad_fpdb.geometry import FootprintGeometry, Pad


def dual_row_grid(pin_count: int, pitch: float, row_spacing: float,
                   pad_size: tuple[float, float], pad_shape: str,
                   pad_type: str, drill: float | None = None,
                   centered: bool = False) -> FootprintGeometry:
    if pin_count % 2 != 0:
        raise ValueError("dual_row_grid requires an even pin_count")
    pins_per_row = pin_count // 2

    if centered:
        y0 = -pitch * (pins_per_row - 1) / 2
        x_left, x_right = -row_spacing / 2, row_spacing / 2
    else:
        y0 = 0.0
        x_left, x_right = 0.0, row_spacing

    pads = []
    for i in range(pins_per_row):
        pin1 = i == 0
        shape = "roundrect" if (pad_shape == "dip_pin1_marker" and pin1) else (
            "circle" if pad_shape == "dip_pin1_marker" else "roundrect"
        )
        pads.append(Pad(
            number=str(i + 1), pad_type=pad_type, shape=shape,
            at=(x_left, y0 + i * pitch), size=pad_size, drill=drill,
            roundrect_rratio=_round_ratio(pad_shape, shape, pad_size),
        ))

    top_y = y0 + (pins_per_row - 1) * pitch
    for i in range(pins_per_row):
        shape = "circle" if pad_shape == "dip_pin1_marker" else "roundrect"
        pads.append(Pad(
            number=str(pins_per_row + i + 1), pad_type=pad_type, shape=shape,
            at=(x_right, top_y - i * pitch), size=pad_size, drill=drill,
            roundrect_rratio=_round_ratio(pad_shape, shape, pad_size),
        ))

    return FootprintGeometry(name="", pads=pads)


def _round_ratio(pad_shape: str, shape: str, pad_size: tuple[float, float]) -> float | None:
    if shape != "roundrect":
        return None
    if pad_shape == "dip_pin1_marker":
        return round(0.25 / min(pad_size), 5)
    return 0.25
