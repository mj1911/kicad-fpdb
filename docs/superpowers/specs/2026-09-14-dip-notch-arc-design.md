# DIP Top-Notch Arc — Design Spec

Date: 2026-09-14

## Background

Real KiCad's DIP footprints cut a semicircular notch into the top edge
of the F.SilkS outline — the pin-1-side indicator molded into the
physical package. This project's DIP rectangle mode (`body_width`/
`body_margin` in `_add_outline`) currently draws a single straight top
edge instead. SOIC shares that same rectangle-drawing branch but real
SOIC footprints have no such notch (confirmed: 0 `fp_arc` entries in
either SOIC reference footprint), so this is a DIP-specific addition,
not a change to the shared branch's default behavior.

Checked directly against five real DIP reference footprints (three pin
counts, three row-spacing widths):

| Footprint | arc start | arc mid | arc end |
|---|---|---|---|
| DIP-16 W7.62 | (4.81, -1.33) | (3.81, -0.33) | (2.81, -1.33) |
| DIP-14 W7.62 | (4.81, -1.33) | (3.81, -0.33) | (2.81, -1.33) |
| DIP-18 W7.62 | (4.81, -1.33) | (3.81, -0.33) | (2.81, -1.33) |
| DIP-16 W10.16 | (6.08, -1.33) | (5.08, -0.33) | (4.08, -1.33) |
| DIP-24 W15.24 | (8.62, -1.33) | (7.62, -0.33) | (6.62, -1.33) |

In every case: a true semicircle (chord 2.0mm, sagitta 1.0mm — a real
semicircle has sagitta = radius = half-chord, confirmed exactly here),
centered at the body's horizontal center (matching this project's
existing `center_x`), sitting on the top silk edge (`sy0`), bulging
downward into the body by exactly its 1.0mm radius. Radius is constant
across every pin count and width class — the same "one constant covers
every variant" pattern as `body_margin`.

## Goals

- Add an `Arc` geometry primitive and `fp_arc` writer support.
- Give DIP's rectangle silk mode a semicircular notch (radius 1.0mm)
  cut into the top edge, centered at body center-x: the top edge
  becomes two short line segments (from each top corner to the notch)
  plus the arc filling the gap between them.
- This is additive to the existing pin-1 circle marker, not a
  replacement — both appear on generated DIP footprints.

## Non-goals

- SOIC — its rectangle mode keeps a plain, unbroken top edge (new
  parameter defaults to `None`/absent, so SOIC's output is byte-identical
  to before this change).
- QFP's corner marks or R/C's two-line mode — untouched, this only
  touches the `body_width`/`body_margin` rectangle branch.
- Generalizing which edge gets the notch — hardcoded to the top edge
  (`sy0`), matching every current DIP variant's pin-1 position. Like the
  pin-1 marker's "above" assumption, this would need revisiting for a
  hypothetical DIP-like family with pin 1 elsewhere.

## Design

### New geometry primitive (`kicad_fpdb/geometry.py`)

```python
@dataclass
class Arc:
    start: tuple[float, float]
    mid: tuple[float, float]
    end: tuple[float, float]
    layer: str
    width: float = 0.12
```

No `fill` field — arcs are open curves in KiCad, unlike `Rect`/`Poly`/
`Circle`. Add `arcs: list[Arc] = field(default_factory=list)` to
`FootprintGeometry`.

### Writer support (`kicad_fpdb/writer.py`)

```python
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
```

`write_kicad_mod` gains a loop over `geometry.arcs`, alongside the
existing lines/rects/polys/circles loops.

### Pipeline (`kicad_fpdb/pipeline.py`)

New `notch_radius: float | None = None` parameter on `_add_outline`,
popped from resolved params in `generate_footprint` the same way as the
other outline-only params. Used only inside the `body_width`/
`body_margin` branch:

```python
    if body_width is not None and body_margin is not None:
        ...  # sx0/sx1/sy0/sy1/center_x computed as today
        if notch_radius is not None:
            notch_left, notch_right = center_x - notch_radius, center_x + notch_radius
            geometry.lines.append(Line(start=(sx0, sy0), end=(notch_left, sy0), layer="F.SilkS"))
            geometry.lines.append(Line(start=(notch_right, sy0), end=(sx1, sy0), layer="F.SilkS"))
            geometry.arcs.append(Arc(
                start=(notch_right, sy0), mid=(center_x, sy0 + notch_radius), end=(notch_left, sy0),
                layer="F.SilkS",
            ))
            geometry.lines.append(Line(start=(sx1, sy0), end=(sx1, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx1, sy1), end=(sx0, sy1), layer="F.SilkS"))
            geometry.lines.append(Line(start=(sx0, sy1), end=(sx0, sy0), layer="F.SilkS"))
        else:
            ...  # existing 4-line rectangle loop, unchanged — this is SOIC's path
```

`data/kicad-fpdb.yaml`: add `notch_radius: 1.0` to DIP's root `params`
(inherited by every child). SOIC's params are untouched.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry untouched).
- Unit test on `_add_outline` confirming the notch's exact line/arc
  endpoints for DIP-16 (matching the real values in the table above).
- Test confirming SOIC's rectangle mode is unaffected (still a plain
  4-line rectangle, no `Arc`).
- Regenerate `renders/review.html` and visually confirm DIP-16/14/18/16r
  show the notch matching the reference panel closely; SOIC unchanged.
