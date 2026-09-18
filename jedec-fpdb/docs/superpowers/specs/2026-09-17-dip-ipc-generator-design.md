# jedec-fpdb: spec-derived DIP footprint generator (design)

## Purpose

`kicad-fpdb` (the sibling project at the repo root) builds footprints by
reverse-engineering geometry from real KiCad `.kicad_mod` library files —
constants are hand-copied from what KiCad actually ships, verified to match
exactly. That answers "what does KiCad draw." It does not answer "what
would an IPC-7351B/IPC-7251-compliant land pattern look like for the same
part," since KiCad's own footprints are known to deviate from the standards
in places (already noted in `kicad-fpdb`'s own CLAUDE.md, e.g. SOIC's
~0.01-0.02mm body-margin approximation).

`jedec-fpdb` is a side-project, self-contained under this subfolder, that
generates DIP footprints purely from published standards — JEDEC MS-001
(package body/lead outline) and IPC-7251 (thru-hole land pattern sizing:
DIP is a thru-hole package, and IPC-7351B itself is scoped to surface-mount
land patterns only, so it does not govern DIP's pad/drill sizing) — with no
reference to any real `.kicad_mod` file as a data source. Real reference
files from `kicad-fpdb`'s existing test fixtures are used only afterward,
read-only, as a comparison/sanity-check baseline (see Validation below).

This is background research, not a production feature: the deliverable is
a working formula pipeline for DIP plus a documented comparison against
real KiCad output, not a footprint library meant to replace `kicad-fpdb`.

## Non-goals

* No integration with `kicad-fpdb`'s descriptor grammar, family tree, YAML
  data, geometry classes, or writer — this project shares no runtime code
  with `kicad-fpdb` (see Code Sharing below).
* No families other than DIP in this first pass.
* No cosmetic silkscreen conventions (pin-1 notch, corner marks, etc.) —
  those are KiCad/vendor drawing conventions, not something either JEDEC
  MS-001 or IPC-7251/7351B specifies. First pass draws pads, a plain body
  outline rectangle, and a courtyard only.
* No access to the actual paywalled JEDEC/IPC PDF documents. All formulas
  and table values are sourced from publicly available secondary
  references (manufacturer datasheets citing MS-001, published land
  pattern calculator documentation/tools, standards summaries) found via
  web search, cited inline in code comments where a constant is
  standards-derived rather than a plain geometric formula. Values should
  be treated as best-effort reconstructions of the standards, not
  guaranteed byte-for-byte matches to the official documents.
* No attempt to reconcile deviations from real KiCad files — deviations
  are expected and are the point of the comparison, not bugs to fix.

## Code sharing

Fully independent of `kicad-fpdb`. `jedec-fpdb` has its own geometry
primitives and its own `.kicad_mod` writer, built fresh. The only thing
"shared" with `kicad-fpdb` is read-only: `compare.py` loads existing real
reference `.kicad_mod` fixture files from `kicad-fpdb`'s test suite to diff
against, but does not import any `kicad-fpdb` Python code, and does not
copy those files into `jedec-fpdb`'s own tree.

## Architecture / folder layout

```
jedec-fpdb/
  jedec_fpdb/
    __init__.py
    geometry.py     # Pad/Rect/Poly/Footprint dataclasses (independent of kicad_fpdb's)
    writer.py        # .kicad_mod S-expression serializer (independent)
    ipc7251.py         # thru-hole pad/drill sizing formulas (annular ring, hole clearance, density levels)
    dip.py              # generate(width_class, pin_count, density="N") -> Footprint
    compare.py            # diff a generated Footprint against a real reference .kicad_mod
  data/
    ms001_dip.py            # JEDEC MS-001 DIP table: pitch, row spacing per width class, body length formula
  tests/
    test_ipc7251.py           # formulas against IPC-7251's published worked examples
    test_dip.py                 # generated DIP-N geometry sanity checks
    test_compare.py               # comparison tool against real kicad-fpdb reference fixtures
  docs/
    superpowers/specs/            # this project's own design specs (this file)
  README.md
```

Sits as a sibling top-level directory in the same git repo as
`kicad-fpdb` (not a separate repo, not a separately-installed package).

## Data flow

1. **`data/ms001_dip.py`** holds JEDEC MS-001's DIP table as plain Python
   data: lead pitch (2.54mm, fixed across all DIP variants), row spacing
   per width class, and body length as a function of pin count
   (`body_length = (pin_count / 2 - 1) * pitch + end_margin`, `end_margin`
   a MS-001 constant). Width class names (narrow/regular/wide/...) mirror
   the vocabulary `kicad-fpdb` already uses for the same physical concept,
   but the numeric row-spacing values here are independently sourced from
   MS-001, not copied from `kicad-fpdb`'s YAML — the two are expected to
   agree closely but are derived independently, and any mismatch is itself
   a data point for the comparison step.
2. **`ipc7251.py`** takes a lead diameter (from MS-001's lead dimension
   range) and a density level (Most / Nominal / Least material condition)
   and returns:
   * `drill_diameter = lead_diameter_max + hole_clearance(density)`
   * `pad_diameter = drill_diameter + 2 * min_annular_ring(density)`

   `hole_clearance` and `min_annular_ring` are small lookup tables keyed
   by density level, sourced from public IPC-7251 summaries during
   implementation and cited in a code comment next to the table.
3. **`dip.py`**'s `generate(width_class, pin_count, density="N")` combines
   both: computes pin positions from pitch + row spacing, pad/drill size
   from `ipc7251`, and package body outline from MS-001, assembling a
   `Footprint` (pads + a plain body rectangle on silkscreen + a courtyard
   rectangle — no notch, no pin-1 marker).
4. **`writer.py`** serializes the `Footprint` to a real `.kicad_mod` file,
   an independent implementation of the KiCad S-expression format (reusing
   only the *format knowledge* already established while building
   `kicad-fpdb`'s own writer, not its code).
5. **`compare.py`** loads one of `kicad-fpdb`'s existing real reference
   `DIP-*.kicad_mod` fixtures (by file path, read-only) and reports
   per-dimension deltas — pad diameter, drill diameter, row spacing, body
   length — between the spec-derived and real file. Deltas are expected;
   the tool flags a result only when a delta looks like an implementation
   bug (e.g. an order-of-magnitude mismatch) rather than a legitimate
   spec-vs-KiCad difference. What counts as "expected" vs. "flagged" is
   a fixed tolerance band documented in `test_compare.py` itself, refined
   as real numbers come in during implementation.

## Testing

* `test_ipc7251.py` — unit tests for the annular-ring/hole-clearance
  formulas against IPC-7251's published worked examples, independent of
  any KiCad comparison.
* `test_dip.py` — sanity checks on generated geometry: pad count matches
  pin count, row spacing/pitch match the MS-001 table, no overlapping
  pads, symmetric layout.
* `test_compare.py` — runs `compare.py` against real reference DIP files
  already in `kicad-fpdb`'s test fixtures (DIP-8, DIP-14, DIP-16, DIP-16w,
  DIP-24w) and asserts deltas stay within the documented tolerance band.
  This is the test that validates the project's core claim.

No error handling beyond input validation (an unsupported pin count or
width class raises a clear error) — this is a research tool with no other
code depending on it, not a library needing defensive fallback behavior.

## Initial scope

DIP only, at the width classes `kicad-fpdb` already validates (narrow,
regular, wide) across pin counts 8, 14, 16, and 24. Density level fixed to
Nominal for this first pass; Most/Least are a natural follow-up once the
Nominal pipeline is validated, not part of this deliverable.

## Open follow-ups (not in this deliverable)

* Most/Least density levels, and exposing density as a CLI/API option.
* Additional DIP width classes (extra_wide, ultra_wide) once the base
  three are validated.
* Additional families beyond DIP (SOIC is the natural next step, but
  needs IPC-7351B proper rather than IPC-7251, since SOIC is
  surface-mount).
* Cosmetic silkscreen conventions (pin-1 notch, etc.) if a later goal
  needs visual parity with `kicad-fpdb`'s output rather than just
  standards-derived geometry.
