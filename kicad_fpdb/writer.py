from kicad_fpdb.geometry import FootprintGeometry, Pad, Text

_PROPERTY_NAMES = {"reference": "Reference", "value": "Value"}


def write_kicad_mod(name: str, geometry: FootprintGeometry) -> str:
    lines = [
        f'(footprint "{name}"',
        "  (version 20240101)",
        '  (generator "kicad-fpdb")',
        '  (layer "F.Cu")',
    ]
    for text in geometry.texts:
        lines.append(_write_text(text))
    for pad in geometry.pads:
        lines.append(_write_pad(pad))
    lines.append(")")
    return "\n".join(lines) + "\n"


def _write_text(text: Text) -> str:
    property_name = _PROPERTY_NAMES[text.kind]
    at_x, at_y = text.at
    return (
        f'  (property "{property_name}" "{text.text}"\n'
        f"    (at {_fmt(at_x)} {_fmt(at_y)} 0)\n"
        f'    (layer "{text.layer}")\n'
        "    (effects\n"
        "      (font\n"
        "        (size 1 1)\n"
        "        (thickness 0.15)\n"
        "      )\n"
        "    )\n"
        "  )"
    )


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
