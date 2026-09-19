# Extend the pin-1 triangle marker to SOIC and LQFP

Date: 2026-09-17

## Problem

QFN's pin-1 marker was changed from a circle to a filled triangle
matching real KiCad's own convention (`pin1_marker_style: triangle`,
see `docs/superpowers/specs/2026-09-17-qfn-pin1-triangle-marker-design.md`).
That work's investigation found that SOIC, SOT-23, and LQFP's real
reference footprints *also* carry their own triangle markers, at
family-specific positions — tracked as a TODO follow-up. This spec
covers SOIC and LQFP; SOT-23 is deferred separately (its geometry
follows a different, not-yet-understood rule, and two of its variants
currently have `pin1_marker: false` for an unrelated reason that would
need its own decision — see Non-goals).

## Investigation

Extracted pad 1 and the real `F.SilkS` triangle poly from every SOIC
and LQFP reference case (`kicad_fpdb.reference_cases.CASES`) and
compared against QFN's already-known formula (apex at
`pad-edge - margin - 0.01mm` along the pad's own outward axis, base
spread symmetric around the pad's own center on the perpendicular
axis, fixed depth/half-width).

**The extension axis differs per family.** QFN's marker extends along
the same axis pad 1's lead points on (its "wide" axis — pad 1 is a
left-side pad, wide in X, and the marker extends further in X). SOIC
and LQFP's markers instead extend along the *perpendicular* axis (Y —
toward the top of the body), even though their pad 1 is also a wide-in-X
left-side pad. This isn't inferrable from pad shape; each family's own
real generator script apparently makes this choice independently, so
it needs to become an explicit parameter rather than the current
shape-based inference.

**The extension-axis formula is unchanged**, just applied to Y instead
of X: `apex_y = pad1.y ± (pad1's own half-height + courtyard_margin_y +
0.01mm)`, sign matching whichever direction is outward (away from body
center). This held essentially exactly across every SOIC and LQFP
sample — 4 of LQFP's 8 variants match the real file to the last digit,
the other 4 are off by exactly `0.01mm` in a way that doesn't resolve
to one consistent alternate constant (not a rounding artifact of *this*
formula specifically — tried `0.02mm` as the offset, which fixes those
4 but un-fixes the other 4). Accepted as the same category of small,
unavoidable discrepancy already documented elsewhere in this project
(e.g. SOIC's own body-width formula, LQFP's corner marks).

**The perpendicular-axis position is anchored to the body, not to pad
1.** Initially appeared to depend on pad 1's own position with an
unexplained ~0.09mm variance per LQFP variant — this turned out to be
`pad_lead_extension`'s effect on pad 1's position exactly canceling
against an apparent pad-relative offset. Re-deriving from
`quad_perimeter`'s own `pad_offset = courtyard_body_size/2 +
pad_lead_extension` formula and substituting gives:

```
apex_x = -(courtyard_body_size / 2 + 0.75)
```

(sign flips for a right-side pad 1) — independent of `pad_lead_extension`
and pad 1's position entirely. Verified **exact, zero error**, across
all 8 real LQFP variants (32 through 208, spanning 7mm-28mm bodies).

SOIC's own perpendicular axis follows the identical shape,
`apex_x = -(courtyard_body_width / 2 + constant)`, with its own
per-width-class constant: `0.65` (narrow) / `0.90` (wide) — also
**exact, zero error**, across every narrow and wide sample checked,
including the SOIC-8-1EP exposed-pad variants whose pad 1 shifts
slightly to clear a larger EP (previously looked like it might break a
pad-relative formula; irrelevant now that the formula doesn't reference
pad 1's position on this axis at all).

**Marker size is not universal** — there are two real sizes, not one:
`depth=0.33mm / half-width=0.24mm` (QFN's existing constants, matches
SOIC's narrow class too) and a second, larger pair,
`depth=0.47mm / half-width=0.34mm` (SOIC's wide class and all 8 LQFP
variants, despite LQFP's bodies ranging from 7mm to 28mm — size-
independent within that family).

## Design

**New optional params on `_add_outline`** (all default to today's QFN
behavior when omitted, so QFN's yaml needs zero changes):

- `pin1_triangle_axis: "x" | "y" | None = None` — which axis the
  marker extends along. `None` infers from pad shape (today's QFN
  behavior: `"x"` if the pad is wider than tall, else `"y"`). SOIC and
  LQFP set this explicitly to `"y"`, overriding the shape-based
  inference (their pad 1 is also wide-in-X, but the real marker still
  extends in Y).
- `pin1_triangle_size: "small" | "large" = "small"` — selects the
  depth/half-width constant pair. LQFP and SOIC's wide class set
  `"large"`; SOIC's narrow class (and QFN, unchanged) stay `"small"`.
- `pin1_triangle_anchor_mm: float | None = None` — only consulted when
  `pin1_triangle_axis == "y"`. When set, the perpendicular-axis
  position is computed as `body_center ± (body_half + anchor_mm)`
  (sign toward whichever side pad 1 is on), where `body_half` comes
  from whichever of `courtyard_body_width` or `courtyard_body_size` is
  already declared for that family. When `None` (not used by SOIC/
  LQFP, kept as a documented default for any future `axis="y"` family
  that turns out to be pad-relative instead), falls back to pad 1's
  own center on that axis — today's QFN-only code path had no such
  fallback need, since QFN never uses `axis="y"`.

**`_add_outline`'s existing triangle branch is generalized**, not
duplicated: the current QFN-only logic (X-extension, pad-relative
perpendicular position) becomes the `axis == "x"` case of a single
unified block; `axis == "y"` is new. Depth/half-width become a
`(depth, half_span)` pair selected once via `pin1_triangle_size`,
reused by both axis branches (previously QFN's block had these two
constants hardcoded).

**New constants** (`kicad_fpdb/pipeline.py`, alongside the existing
`PIN1_TRIANGLE_DEPTH_MM`/`PIN1_TRIANGLE_HALF_HEIGHT_MM`):

```python
PIN1_TRIANGLE_DEPTH_LARGE_MM = 0.47
PIN1_TRIANGLE_HALF_HEIGHT_LARGE_MM = 0.34
```

**Data changes** (`data/kicad-fpdb.yaml`):

- `LQFP` root: add `pin1_marker_style: triangle`, `pin1_triangle_axis:
  y`, `pin1_triangle_size: large`, `pin1_triangle_anchor_mm: 0.75`.
- `SOIC` root: add `pin1_marker_style: triangle`, `pin1_triangle_axis:
  y`, `pin1_triangle_size: {narrow: small, wide: large}`,
  `pin1_triangle_anchor_mm: {narrow: 0.65, wide: 0.90}` — reusing the
  same per-width-class dict mechanism `body_width`/`pad_size`/etc.
  already use on this same node (`family_tree.resolve_descriptor`
  resolves any dict-valued param generically, no new mechanism needed).
- `QFN` root: **no change** — `pin1_triangle_axis`/`_size`/
  `_anchor_mm` all default to values reproducing today's exact QFN
  geometry.

## Non-goals

- SOT-23 (and TSOT-23) — deferred; its triangle geometry doesn't match
  either the QFN or SOIC/LQFP formula and needs its own investigation.
  Also raises a separate question this spec doesn't answer: real
  SOT-23/SOT-23-5 reference files have a triangle marker even though
  this project currently sets `pin1_marker: false` for both (reasoned
  as "asymmetric layout, only placeable one way" — a functional
  argument unrelated to whether real KiCad draws a marker there).
- The ~0.01mm residual on 4 of LQFP's 8 variants' extension-axis
  position is not chased further — accepted as generator-rounding
  noise, consistent with this project's existing tolerance for
  similarly-sized discrepancies elsewhere.
- No change to any family other than SOIC and LQFP.

## Verification

- Extend `tests/test_pipeline_regression.py`'s (via
  `kicad_fpdb.footprint_diff.diff_footprint`) triangle check —
  currently scoped to `descriptor.split()[0] == "QFN"` — to also cover
  SOIC and LQFP descriptors, using the same tolerance (points rounded
  to 0.01mm, compared as sets). LQFP's known ~0.01mm residual on some
  variants means this tolerance (not a tighter one) is required, not
  optional, for this family.
- Add unit tests in `tests/test_pipeline_outline.py` for the new
  `axis="y"` branch and the `pin1_triangle_anchor_mm` body-anchoring
  math, following the same direct-call-to-`_add_outline`/
  `_add_corner_marks`-style pattern already used for QFN's triangle
  tests and the corner-mark jog tests.
- Run `python -m kicad_fpdb.verify_library --family SOIC LQFP` for a
  full diff report (not just pass/fail) across every SOIC and LQFP
  case, since this is exactly the tool built for this kind of check.
- Visual review via `python -m kicad_fpdb.render_png --family SOIC
  LQFP` on a narrow SOIC, a wide SOIC, and a small/large LQFP.
