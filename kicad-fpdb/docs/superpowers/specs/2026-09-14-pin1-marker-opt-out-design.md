# Pin-1 Marker Opt-Out for Non-Polarized Passives — Design Spec

Date: 2026-09-14

## Background

`_add_outline()` in `kicad_fpdb/pipeline.py` currently draws a filled
silkscreen pin-1 marker triangle whenever a footprint has a pad numbered
`"1"` — true for every generator, including `two_pad_chip` (R and C).
Resistors are never polarized, and capacitors are only occasionally
polarized (electrolytic, tantalum) — for the common non-polarized case,
a pin-1 marker is misleading (it implies an orientation that doesn't
matter) and doesn't match real KiCad's own R/C footprints, which have no
such marker.

There's currently no "polarized" concept anywhere in `data/kicad-fpdb.yaml`
or the generator engine, and only one capacitor variant exists (`C-0603`,
non-polarized). So today this change is equivalent to "remove the pin-1
marker from every R and C part" — but the design must leave room for a
future polarized capacitor variant to opt back in without new code.

## Goals

- Stop drawing the pin-1 marker for `R-0402`, `R-0603`, `R-0805`, and
  `C-0603`.
- Leave DIP, SOIC, and QFP unaffected — they always need pin-1
  identification (multi-pin ICs are always orientation-sensitive).
- Make it easy for a future polarized capacitor variant to opt back in,
  without touching pipeline code — just a data change.

## Non-goals

- Introducing an actual `polarized` descriptor concept, or new
  capacitor variants (electrolytic, tantalum, etc.). This spec only adds
  the on/off mechanism; using it for a real polarized part is future work.
- Changing the marker's geometry, size, or the DIP/SOIC/QFP behavior in
  any way.

## Design

### Data model (`data/kicad-fpdb.yaml`)

Add a generic `pin1_marker` boolean param, defaulting to `true` when
absent (so DIP/SOIC/QFP need zero changes). Set it to `false` at the `R`
and `C` family root level — `family_tree`'s existing chain-merge already
inherits root-level params down to every child (`_merge_params` walks
parent-to-child in order, so a root's `params` apply to every descendant
unless a child overrides them), so this one change covers `R-0402`,
`R-0603`, `R-0805`, and `C-0603` without editing each child:

```yaml
R:
  params:
    pin1_marker: false
  children:
    R-0402: ...
    R-0603: ...
    R-0805: ...

C:
  params:
    pin1_marker: false
  children:
    C-0603: ...
```

A future polarized capacitor child (e.g. `C-ELEC-...`) would simply
declare `pin1_marker: true` in its own `params`, which overrides the
inherited `false` per the existing child-overrides-parent merge rule —
no pipeline code change needed for that case.

### Pipeline (`kicad_fpdb/pipeline.py`)

`pin1_marker` is an outline input, not a generator input — pop it from
resolved params in `generate_footprint`, same pattern as
`body_width`/`body_margin`/`body_size`, defaulting to `True` when absent:

```python
pin1_marker = params.pop("pin1_marker", True)
...
_add_outline(geometry, body_width=body_width, body_margin=body_margin,
             body_size=body_size, pin1_marker=pin1_marker)
```

`_add_outline` gains a `pin1_marker: bool = True` parameter. The existing
marker-drawing block (currently gated only on `pad1 is not None`) is
additionally gated on this flag:

```python
if pin1_marker and pad1 is not None:
    ...  # existing triangle-construction logic, unchanged
```

Everything else in `_add_outline` (courtyard, the F.SilkS outline itself
in whichever mode) is unaffected — this only ever suppresses the
triangle `Poly`.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (pad geometry untouched).
- Unit test on `_add_outline` confirming `pin1_marker=False` produces no
  `Poly` even when pad `"1"` exists.
- Tests via `generate_footprint` confirming R-0402/R-0603/R-0805/C-0603
  no longer emit `fp_poly`, while DIP-16/SOIC-8/QFP-32 (unaffected
  families) still do.
- Regenerate `renders/review.html` and visually confirm the R/C cases no
  longer show a pin-1 triangle.
