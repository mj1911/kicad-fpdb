from kicad_fpdb.geometry import Arc, Circle, FootprintGeometry, Line, Pad, Poly, Rect, Text

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
    for rect in geometry.rects:
        lines.append(_write_rect(rect))
    for line in geometry.lines:
        lines.append(_write_line(line))
    for poly in geometry.polys:
        lines.append(_write_poly(poly))
    for circle in geometry.circles:
        lines.append(_write_circle(circle))
    for arc in geometry.arcs:
        lines.append(_write_arc(arc))
    for pad in geometry.pads:
        lines.append(_write_pad(pad))
    lines.append(")")
    return "\n".join(lines) + "\n"


def _write_text(text: Text) -> str:
    if text.kind == "fab_reference":
        return _write_fab_reference_text(text)
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


def _write_fab_reference_text(text: Text) -> str:
    # Real KiCad footprints carry this as a distinct fp_text user element
    # (an assembly-drawing overlay), not a property like Reference/Value.
    at_x, at_y = text.at
    size = _fmt(text.font_size)
    return (
        f'  (fp_text user "{text.text}"\n'
        f"    (at {_fmt(at_x)} {_fmt(at_y)} {_fmt(text.rotation)})\n"
        f'    (layer "{text.layer}")\n'
        "    (effects\n"
        "      (font\n"
        f"        (size {size} {size})\n"
        f"        (thickness {_fmt(text.thickness)})\n"
        "      )\n"
        "    )\n"
        "  )"
    )


def _write_line(line: Line) -> str:
    sx, sy = line.start
    ex, ey = line.end
    return (
        "  (fp_line\n"
        f"    (start {_fmt(sx)} {_fmt(sy)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(line.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f'    (layer "{line.layer}")\n'
        "  )"
    )


def _write_rect(rect: Rect) -> str:
    sx, sy = rect.start
    ex, ey = rect.end
    return (
        "  (fp_rect\n"
        f"    (start {_fmt(sx)} {_fmt(sy)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(rect.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f"    (fill {rect.fill})\n"
        f'    (layer "{rect.layer}")\n'
        "  )"
    )


def _write_poly(poly: Poly) -> str:
    pts = "\n".join(f"      (xy {_fmt(x)} {_fmt(y)})" for x, y in poly.points)
    return (
        "  (fp_poly\n"
        "    (pts\n"
        f"{pts}\n"
        "    )\n"
        "    (stroke\n"
        f"      (width {_fmt(poly.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f"    (fill {poly.fill})\n"
        f'    (layer "{poly.layer}")\n'
        "  )"
    )


def _write_circle(circle: Circle) -> str:
    cx, cy = circle.center
    ex, ey = cx + circle.radius, cy
    return (
        "  (fp_circle\n"
        f"    (center {_fmt(cx)} {_fmt(cy)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(circle.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f"    (fill {circle.fill})\n"
        f'    (layer "{circle.layer}")\n'
        "  )"
    )


def _write_arc(arc: Arc) -> str:
    sx, sy = arc.start
    mx, my = arc.mid
    ex, ey = arc.end
    return (
        "  (fp_arc\n"
        f"    (start {_fmt(sx)} {_fmt(sy)})\n"
        f"    (mid {_fmt(mx)} {_fmt(my)})\n"
        f"    (end {_fmt(ex)} {_fmt(ey)})\n"
        "    (stroke\n"
        f"      (width {_fmt(arc.width)})\n"
        "      (type solid)\n"
        "    )\n"
        f'    (layer "{arc.layer}")\n'
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
