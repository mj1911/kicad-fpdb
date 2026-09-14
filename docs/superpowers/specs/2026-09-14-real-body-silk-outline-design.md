# Real Body-Derived Silkscreen Outline — Design Spec

Date: 2026-09-14

## Background

The generator engine currently draws the F.SilkS body outline generically:
a rectangle inflated by a flat 0.2mm margin from the pad bounding box (see
`_add_outline` in `kicad_fpdb/pipeline.py`). This was a deliberate initial
simplification, called out as a known gap in `CLAUDE.md`'s TODO list and
the original descriptor-engine spec's non-goals ("fine-grained courtyard
nuances beyond basic clearance").

Real KiCad footprints don't derive their silk outline from the pads at
all — they use the package's actual physical body dimensions, which are
independent of (and usually smaller than, or offset from) the pad span.
For example, DIP-16_W7.62mm's pads span x=0→7.62mm, but its real silk
rectangle only spans x=1.16→6.46mm — inset between the pin rows, not
around them.

This spec covers making the F.SilkS rectangle for DIP and SOIC (the two
`dual_row_grid` families) reflect real body geometry, as a **symbolic**
per-family approximation — not an exact per-footprint dimension database.

## Goals

- Add a `body_width` and `body_margin` concept to the descriptor data for
  DIP and SOIC, derived from real KiCad reference footprints, applied
  uniformly to every pin-count variant within a family (and, for DIP,
  within each row-spacing/width class).
- Rebuild the F.SilkS rectangle from these values instead of the pad
  bounding box, when a family declares them.
- Preserve current behavior (pad-bbox + flat margin) for any family that
  doesn't declare these params (QFP, chip passives) — no regression there.

## Non-goals

- Exact per-footprint dimensional accuracy. Real KiCad's own values have
  minor irregularities (e.g. DIP-24 at the "regular" 10.16mm row spacing
  uses a different body width than DIP-8/14/16 at the same row spacing —
  a real-world outlier). This spec accepts small deviations; the outline
  is a symbolic representation of the part, not a certified dimension.
- Courtyard (F.CrtYd) geometry — stays pad-bbox-derived.
- The pin-1 marker triangle — unaffected.
- QFP and chip-passive (two_pad_chip / quad_perimeter) families — out of
  scope for this pass; they keep the generic outline.

## Data derived from real footprints

Checked directly against KiCad 10.0.6's official library
(`/usr/share/kicad/footprints/`):

**DIP** (`Package_DIP.pretty`), across DIP-8/14/16/18/24 at each width:

| width variant | row_spacing | body_width | margin |
|---|---|---|---|
| narrow | 7.62mm | 5.30mm | 1.33mm |
| regular | 10.16mm | 6.47mm | 1.33mm |
| wide | 15.24mm | 12.92mm | 1.33mm |

`margin` (offset from the first/last pad **center**, along the pin-row
direction) is constant at 1.33mm across every pin count and width class
tested. `body_width` is constant per width class for the pin counts this
project's reference suite covers (8/14/16/18); DIP-24 at "regular" is a
known outlier in real KiCad and is not specially-cased here.

**SOIC** (`Package_SO.pretty`), across the two reference cases (SOIC-8,
SOIC-14, both P1.27mm/4.95mm row spacing):

| body_width | margin |
|---|---|
| 4.12mm | ~0.64mm (averaged; real values are 0.655mm and 0.625mm) |

## Design

### Data model (`data/kicad-fpdb.yaml`)

Add `body_width` (variant-keyed dict for DIP, matching the existing
`row_spacing` pattern; scalar for SOIC) and `body_margin` (scalar) to each
family's `params`. These flow through `resolve_descriptor` unchanged — it
already resolves any variant-keyed dict param generically, not just
`row_spacing`.

```yaml
DIP:
  params:
    ...
    body_width: {narrow: 5.3, regular: 6.47, wide: 12.92}
    body_margin: 1.33

SOIC:
  params:
    ...
    body_width: 4.12
    body_margin: 0.64
```

### Pipeline (`kicad_fpdb/pipeline.py`)

`body_width`/`body_margin` are outline inputs, not generator inputs —
`dual_row_grid` doesn't accept them. `generate_footprint` pops them from
`resolved.params` before calling the generator, then passes them into
`_add_outline`:

```python
params = dict(resolved.params)
body_width = params.pop("body_width", None)
body_margin = params.pop("body_margin", None)
geometry = generator_fn(**params)
geometry.name = name
_add_outline(geometry, body_width=body_width, body_margin=body_margin)
```

`_add_outline` gains two optional parameters. When both are given, it
computes the silk rectangle from pad **centers** (a new min/max over
`pad.at`, not the existing size-inclusive `pad_bounding_box`):

- Width axis: centered on the pad-row centerline (midpoint of min/max pad
  center on that axis), spanning `body_width`.
- Length axis: from the first/last pad center, extended by `body_margin`.

When either is `None` (families that don't declare them), the existing
pad-bounding-box + `SILK_MARGIN_MM` behavior is unchanged. Courtyard and
the pin-1 marker keep using `pad_bounding_box` as before, regardless.

### Verification

- Existing pipeline regression suite and kicad-cli round-trip tests must
  keep passing (they check structural validity, not exact silk geometry,
  per the original spec's stated approach of visual review for outline
  geometry).
- Add a couple of focused unit tests on `_add_outline` (or a small
  pure-function extraction of the rectangle math) asserting the computed
  rectangle for known body_width/body_margin inputs.
- Regenerate `renders/review.html` and visually confirm DIP and SOIC
  cases now show a silk rectangle that visually matches the reference
  panel's proportions and position (not pixel-exact, since the reference
  SVG's real outline includes a pin-1 notch arc this project intentionally
  replaces with the triangle marker convention).
