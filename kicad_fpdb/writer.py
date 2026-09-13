from kicad_fpdb.geometry import FootprintGeometry, Pad


def write_kicad_mod(name: str, geometry: FootprintGeometry) -> str:
    lines = [
        f'(footprint "{name}"',
        "  (version 20240101)",
        '  (generator "kicad-fpdb")',
        '  (layer "F.Cu")',
    ]
    for pad in geometry.pads:
        lines.append(_write_pad(pad))
    lines.append(")")
    return "\n".join(lines) + "\n"


def _write_pad(pad: Pad) -> str:
    at_x, at_y = pad.at
    size_x, size_y = pad.size
    lines = [f'  (pad "{pad.number}" {pad.pad_type} {pad.shape}']
    lines.append(f"    (at {_fmt(at_x)} {_fmt(at_y)})")
    lines.append(f"    (size {_fmt(size_x)} {_fmt(size_y)})")
    if pad.drill is not None:
        lines.append(f"    (drill {_fmt(pad.drill)})")
    if pad.pad_type == "thru_hole":
        lines.append('    (layers "*.Cu" "*.Mask")')
    else:
        lines.append('    (layers "F.Cu" "F.Mask" "F.Paste")')
    if pad.roundrect_rratio is not None:
        lines.append(f"    (roundrect_rratio {_fmt(pad.roundrect_rratio)})")
    lines.append("  )")
    return "\n".join(lines)


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"
