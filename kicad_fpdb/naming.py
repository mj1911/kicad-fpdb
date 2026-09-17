"""Derives a descriptive dimension suffix for a generated footprint's
identity/Value text, mirroring each family's own real KiCad naming
convention -- verified against real reference footprints -- so a user
assigning a footprint can sanity-check it at a glance (e.g. "LQFP-32
must be wrong, I know the pitch is 0.85mm"). Families with no natural
single dimension to show (SOT/TSOT: asymmetric per-pin offsets, no
shared pitch) get no suffix, matching real KiCad, which doesn't add
one for these either.
"""

# Standard imperial (inch-derived) chip passive size code -> its metric
# (mm-derived) equivalent, as used in real KiCad's own footprint names
# (e.g. "R_0603_1608Metric"). Not derivable from our own params -- it's
# a fixed industry pairing, not a formula.
IMPERIAL_TO_METRIC = {
    "0201": "0603",
    "0402": "1005",
    "0603": "1608",
    "0805": "2012",
    "1206": "3216",
    "1210": "3225",
    "1812": "4532",
    "2010": "5025",
    "2512": "6332",
}

# Modifier token -> real-KiCad-exact display name for the name suffix.
# Plain `.capitalize()` handles "socket" -> "Socket" fine, but breaks on
# internal capitals like "LongPads" (would give "Longpads").
MODIFIER_DISPLAY_NAMES = {
    "socket": "Socket",
    "longpads": "LongPads",
}


def _fmt(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text else "0"


def fab_outline_bounding_box(geometry) -> tuple[float, float, float, float] | None:
    """Bounding box of the true-body F.Fab outline (a rect or chamfered
    poly, whichever _add_outline drew) -- None if the geometry has no
    F.Fab rect/poly."""
    xs: list[float] = []
    ys: list[float] = []
    for rect in geometry.rects:
        if rect.layer == "F.Fab":
            xs += [rect.start[0], rect.end[0]]
            ys += [rect.start[1], rect.end[1]]
    for poly in geometry.polys:
        if poly.layer == "F.Fab":
            for point in poly.points:
                xs.append(point[0])
                ys.append(point[1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def descriptive_suffix(family: str, variant: str, params: dict, geometry,
                        applied_modifiers: list | None = None) -> str:
    # Non-width modifier tokens (e.g. "socket") are dropped from the base
    # name (kicad_fpdb.pipeline.generate_footprint) since real KiCad
    # names encode them as a trailing suffix *after* the dimension part
    # (e.g. "DIP-14_W7.62mm_Socket", not "DIP-14_socket_W7.62mm") -- width
    # tokens (r/w/x/u/...) carry no suffix of their own at all, since the
    # dimension part already encodes them.
    # SOIC's "ep..." modifiers (e.g. "ep2_41x3_3") only exist to select an
    # ep_size/ep_mask_size override -- the EP dimension suffix they
    # produce is built explicitly below, not through this generic
    # trailing-modifier mechanism, so they're excluded here or it would
    # double up (e.g. "..._EP2.41x3.3mm_Ep2_41x3_3").
    modifier_suffix = "".join(
        f"_{MODIFIER_DISPLAY_NAMES.get(m, m.capitalize())}" for m in (applied_modifiers or [])
        if not m.startswith("ep")
    )
    # Note: every early `return ""` below drops modifier_suffix rather than returning it -- harmless today since only DIP/CERDIP declare modifiers and both always have row_spacing, but would silently swallow a modifier suffix if that ever changes.

    # The descriptor grammar splits on the first hyphen only, so
    # "R-AXIAL0204" parses to family="R", variant="AXIAL0204" -- check
    # this before the plain chip-resistor/capacitor branch below, or
    # "AXIAL0204" would be (mis)treated as an unknown metric code.
    if family in ("R", "C") and variant.startswith("AXIAL"):
        pad_pitch = params.get("pad_pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pad_pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        return f"_L{_fmt(max_x - min_x)}_D{_fmt(max_y - min_y)}_P{_fmt(pad_pitch)}mm" + modifier_suffix

    if family in ("DIP", "CERDIP", "SMDIP"):
        row_spacing = params.get("row_spacing")
        if row_spacing is None:
            return ""
        # Real KiCad's own CERDIP names always carry "_SideBrazed" right
        # after the dimension part (e.g. "CERDIP-14_W7.62mm_SideBrazed",
        # "CERDIP-16_W7.62mm_SideBrazed_Socket") -- unlike "_Socket" this
        # isn't a selectable modifier, every CERDIP part is side-brazed.
        family_suffix = "_SideBrazed" if family == "CERDIP" else ""
        return f"_W{_fmt(row_spacing)}mm" + family_suffix + modifier_suffix

    if family in ("SOIC", "LQFP", "QFN", "TSSOP", "MSOP"):
        pitch = params.get("pitch")
        bbox = fab_outline_bounding_box(geometry)
        if pitch is None or bbox is None:
            return ""
        min_x, min_y, max_x, max_y = bbox
        dims = f"_{_fmt(max_x - min_x)}x{_fmt(max_y - min_y)}mm_P{_fmt(pitch)}mm"
        ep_size = params.get("ep_size") if family in ("SOIC", "QFN") else None
        if ep_size is not None:
            # Real KiCad names an exposed-pad SOIC "SOIC-8-1EP_..." --
            # the "-1EP" sits right after the base name, before the
            # dimension part, unlike every other modifier suffix (which
            # comes after). ep_mask_size (a separate solder-mask opening
            # override) gets its own trailing "_Mask..." when declared.
            ep_suffix = f"_EP{_fmt(ep_size[0])}x{_fmt(ep_size[1])}mm"
            ep_mask_size = params.get("ep_mask_size")
            if ep_mask_size is not None:
                ep_suffix += f"_Mask{_fmt(ep_mask_size[0])}x{_fmt(ep_mask_size[1])}mm"
            return "-1EP" + dims + ep_suffix + modifier_suffix
        return dims + modifier_suffix

    if family in ("R", "C"):
        metric = IMPERIAL_TO_METRIC.get(variant)
        if metric is None:
            return ""
        return f"_{metric}Metric" + modifier_suffix

    return modifier_suffix
