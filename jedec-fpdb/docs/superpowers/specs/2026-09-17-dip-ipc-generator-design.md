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

A real copy of JEDEC MS-001 (Issue D, "R-PDIP-T ... .300 INCH ROW
SPACING") is available at `docs/Ms-001d.pdf` (repo root `docs/`, not this
project's own `jedec-fpdb/docs/`) and is the actual data source for the
narrow-width-class numbers below — not a secondary-source reconstruction.
Reading it surfaced two scope-narrowing facts, resolved with the user
before writing the implementation plan:

* This specific document covers **only** the 0.300in (narrow, 7.62mm)
  row-spacing DIP family. The regular (0.400in) and wide (0.600in)
  families are separate JEDEC outline registrations not yet located —
  see Initial scope below.
* Its full-lead body-length ("D") table only lists N = 14, 16, 18, 20,
  22, 24, 28 — there is no full-lead entry for N=8 (8 only appears under
  a "1/2 lead" staggered variation, a different, less common
  lead-population style than the ordinary fully-populated 8-pin DIP).
  Per the user's decision, N=8's body length is computed by linear
  regression over the table's own N=14..28 nominal values, extrapolated
  to N=8, rather than sourced directly from the table (see Data flow).

A real copy of IPC-7251 ("Generic Requirements for Through-Hole Design
and Land Pattern Standard", June 2008 Final Draft) is also available at
`docs/IPC-7251-req-for-Through-Hole-Designs.pdf` (same location
convention as MS-001, also gitignored). Its **Table 3-5, "Dual In-Line
Packages"** gives DIP-specific values directly — Hole Diameter Factor,
Annular Ring Excess, and Courtyard Excess, each for Maximum/Nominal/Least
(Level A/B/C) — so `ipc7251.py`'s formulas are transcribed from the real
standard's own DIP table, not a secondary-source reconstruction (see
Data flow).

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
* No modeling of Table 3-5's "Anti Pad Excess" row (internal-plane
  ground/power-pour clearance around a plated hole) — this project
  models only the external copper pad, a single-layer-adjacent concept;
  anti-pad is a multi-layer-stackup feature out of scope for this first
  pass.
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

1. **`data/ms001_dip.py`** holds JEDEC MS-001's narrow-width DIP data as
   plain Python data, transcribed directly from `docs/Ms-001d.pdf`: lead
   pitch `e` = 2.54mm (0.100in, Basic), row spacing `eA` = 7.62mm (0.300in,
   Basic), body width `E1` = 6.35mm nominal, lead width `b` max = 0.559mm
   (0.022in), and the full-lead body-length ("D") table keyed by pin count
   (N=14..28, nominal values transcribed from the document). A
   `body_length_mm(pin_count)` function returns the table value directly
   for N in the table; for N=8 (not in the table — see Purpose) it instead
   fits a linear least-squares regression over the table's own N=14..28
   nominal values and evaluates it at N=8, entirely in plain Python (no
   numpy dependency). Width classes beyond narrow are not represented yet
   (see Initial scope) — there is no `regular`/`wide` entry to accidentally
   fall back to.
2. **`ipc7251.py`** takes a lead diameter (from MS-001's lead dimension
   range) and a density level (`"M"` Most / `"N"` Nominal / `"L"` Least
   material condition, i.e. IPC-7251's own Level A/B/C) and, using Table
   3-5's three rows verbatim, returns:
   * `drill_diameter = lead_diameter_max + hole_diameter_factor(density)`
     — Table 3-5's "Hole Diameter Factor" (0.25/0.20/0.15mm).
   * `pad_diameter = drill_diameter + annular_ring_excess(density)` —
     Table 3-5's "Int. & Ext. Annular ring Excess (added to hole dia.)"
     (0.50/0.35/0.30mm). Note this is added to the *diameter* directly,
     not doubled as a per-side radius value — Table 3-5's own wording
     ("added to hole dia.") already accounts for both sides.
   * `courtyard_excess(density)` — Table 3-5's "Courtyard Excess from
     Component body and/or lands" (0.5/0.25/0.1mm), consumed by `dip.py`
     below.
3. **`dip.py`**'s `generate(width_class, pin_count, density="N")` combines
   both: computes pin positions from pitch + row spacing, pad/drill size
   from `ipc7251`, and package body outline from MS-001, assembling a
   `Footprint` (pads + a plain body rectangle on silkscreen + a courtyard
   rectangle — no notch, no pin-1 marker). The courtyard is the union
   bounding box of the body outline and the pad bounding box (Table
   3-5's "whichever is greater"), expanded by `courtyard_excess(density)`,
   then its full width/height rounded up to the nearest 0.10mm (Table
   3-5's "Courtyard Round-off factor").
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

* `test_ipc7251.py` — unit tests for the hole-diameter/annular-ring/
  courtyard-excess formulas against Table 3-5's own transcribed values,
  independent of any KiCad comparison.
* `test_dip.py` — sanity checks on generated geometry: pad count matches
  pin count, row spacing/pitch match the MS-001 table, no overlapping
  pads, symmetric layout.
* `test_compare.py` — runs `compare.py` against the real narrow-width
  (`_W7.62mm`) reference files for DIP-8, DIP-14, DIP-16, and DIP-24,
  read directly from the system KiCad library at
  `/usr/share/kicad/footprints/Package_DIP.pretty/` (the same real
  library `kicad-fpdb`'s own regression suite validates against — the
  path is a plain constant in this project's own test, not an import of
  `kicad-fpdb` code, keeping the two projects code-independent per Code
  sharing above), skipped when that path isn't present on the machine.
  Asserts deltas stay within the documented tolerance band. This is the
  test that validates the project's core claim.

No error handling beyond input validation (an unsupported pin count or
width class raises a clear error) — this is a research tool with no other
code depending on it, not a library needing defensive fallback behavior.

## Initial scope

DIP only, **narrow (0.300in/7.62mm) width class only** — the only family
MS-001 Issue D actually documents (see Purpose) — across pin counts 4,
6, 8, 14, 16, 18, 20, 22, 24, and 28. N=14 through N=28 come directly
from the document's own table; N=4/6/8 (below the table's own range) are
each a linear regression extrapolation over that table (see Data flow),
cross-checked against real KiCad DIP-4/6/8 files in `tests/test_compare.py`
— all three land comfortably inside the existing comparison tolerances,
though the extrapolation grows less certain the further below N=14 it's
evaluated. All three density levels (Most/Nominal/Least) are supported,
not just Nominal — the formula work identically regardless of density,
so restricting to Nominal only would have added complexity, not removed
it.

## Open follow-ups (not in this deliverable)

* Regular (0.400in) and wide (0.600in) width classes, once their own
  JEDEC outline document is located — MS-001 Issue D does not cover them.
* Exposing density level as a first-class CLI/API convenience beyond the
  existing `--density` flag (e.g. generating all three at once for
  comparison).
* Additional DIP width classes (extra_wide, ultra_wide) once regular/wide
  are validated.
* Additional families beyond DIP (SOIC is the natural next step, but
  needs IPC-7351B proper rather than IPC-7251, since SOIC is
  surface-mount).
* Cosmetic silkscreen conventions (pin-1 notch, etc.) if a later goal
  needs visual parity with `kicad-fpdb`'s output rather than just
  standards-derived geometry.
