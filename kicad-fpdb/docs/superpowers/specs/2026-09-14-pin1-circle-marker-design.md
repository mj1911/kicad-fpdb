# Pin-1 Circle Marker — Design Spec

Date: 2026-09-14

## Background

The pin-1 marker is currently a filled silkscreen triangle whose tip
sits at whichever body corner (from the active F.SilkS outline mode) is
nearest to pad 1, pointing at pad 1's actual position. This couples the
marker to `_add_outline`'s corner variables (`sx0/sy0/sx1/sy1`), which
only three of its four outline modes compute — the chip-passive
two-line mode (`silk_y`/`silk_half_length`) deliberately doesn't, so
that mode currently carries a documented (but unenforced) rule that it
must never be combined with `pin1_marker=True`.

This spec replaces the triangle with a filled circle, always positioned
directly above pad 1's own position — independent of the body outline
entirely. This is a deliberate departure from real KiCad's own DIP
convention (whose notch sits at the top-center of the body, not above
pin 1 specifically), not an attempt to match it.

## Goals

- Replace the triangle `Poly` marker with a filled circle.
- Position it directly above pad 1: same X as the pad, offset up past
  the pad's own top edge by a fixed clearance — computed purely from
  pad 1's own `at`/`size`, with no dependency on the outline mode or its
  corner variables.
- As a consequence, remove the now-dead `_nearest_corner` function and
  the "must not combine with pin1_marker=True" caveat on the two-line
  silk mode (it's no longer relevant — the marker doesn't touch
  `sx0/sy0/sx1/sy1` at all anymore).

## Non-goals

- Handling a hypothetical future family where pin 1 isn't at the "top"
  (most negative Y) of the part — every current generator (DIP, SOIC,
  QFP) places pin 1 there, so "above" unambiguously means "more negative
  Y" for now. If a future family breaks this assumption, it'll need its
  own follow-up.
- Matching real KiCad's own pin-1 indication conventions (arc notches,
  chamfers, corner cuts) — this is an intentionally different, simpler
  convention chosen for this project.

## Design

### New geometry primitive (`kicad_fpdb/geometry.py`)

Add a `Circle` dataclass, alongside the existing `Line`/`Rect`/`Poly`:

```python
@dataclass
class Circle:
    center: tuple[float, float]
    radius: float
    layer: str
    width: float = 0.12
    fill: str = "yes"
```

Add `circles: list[Circle] = field(default_factory=list)` to
`FootprintGeometry`.

### Writer support (`kicad_fpdb/writer.py`)

Real KiCad's `fp_circle` takes a `center` and an `end` point (a point on
the circle's circumference, defining the radius by distance from
center) rather than a radius value directly:

```python
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
```

`write_kicad_mod` gains a loop over `geometry.circles` emitting these,
alongside its existing loops for lines/rects/polys/pads.

### Pipeline (`kicad_fpdb/pipeline.py`)

New constant alongside `PIN1_MARKER_MM` (repurposed as the circle's
diameter rather than the triangle's base/height — same 0.6mm scale, so
the marker's visual size doesn't change):

```python
# Gap, in mm, between pad 1's own edge and the pin-1 marker circle
# drawn above it.
PIN1_MARKER_CLEARANCE_MM = 0.2
```

Replace the entire marker block at the end of `_add_outline` (which
currently computes `cx, cy = _nearest_corner(...)` and builds a
triangle `Poly`) with:

```python
    pad1 = next((p for p in geometry.pads if p.number == "1"), None)
    if pin1_marker and pad1 is not None:
        cx = pad1.at[0]
        cy = pad1.at[1] - pad1.size[1] / 2 - PIN1_MARKER_CLEARANCE_MM
        geometry.circles.append(Circle(center=(cx, cy), radius=PIN1_MARKER_MM / 2, layer="F.SilkS"))
```

Delete the now-unused `_nearest_corner` function entirely (confirmed via
grep it has no other callers).

Remove the "must not be combined with pin1_marker=True" comment/caveat
from the `silk_y`/`silk_half_length` branch in `_add_outline` — it no
longer applies, since the marker never touches that branch's variables.
This mode still doesn't compute `sx0/sy0/sx1/sy1`, but that's no longer
relevant to anything downstream.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry untouched).
- Unit test on `_add_outline` confirming the circle's center/radius for
  a known pad 1 (e.g. DIP-16: pad 1 at `(0, 0)`, size `(1.6, 1.6)` →
  circle center `(0, -1.0)`, radius `0.3`).
- Test confirming R/C (where `pin1_marker=False`) still produce no
  marker at all (no `fp_circle`, no `fp_poly`).
- Test confirming `generate_footprint` output contains `(fp_circle` and
  no longer contains `(fp_poly` for a family that uses the marker
  (DIP-16), since the triangle `Poly` is gone entirely.
- Regenerate `renders/review.html` and visually confirm DIP/SOIC/QFP
  show a small filled circle directly above pad 1, and R/C show nothing
  (unchanged).
