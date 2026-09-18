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

## Findings

Running `compare.diff()` across all covered pin counts (4, 6, 8, 14, 16,
24) and all three density levels against the real KiCad files surfaced a
consistent pattern, not just per-file noise:

* **Pitch and row spacing match real KiCad exactly** at every pin count
  and density level (delta 0.000mm) — expected, since both are JEDEC
  Basic (theoretical-exact) dimensions with no tolerance to deviate.
* **Real KiCad's drill diameter (0.8mm, flat across every pin count)
  tracks IPC-7251's own "Most" (Level A, Maximum) density level almost
  exactly** — delta only +0.009mm at Most, vs. -0.041mm at Nominal and
  -0.091mm at Least. If real KiCad is targeting a density level for hole
  sizing at all, this suggests Level A, not Level B (Nominal), despite
  Nominal being the more commonly assumed default.
* **Real KiCad's pad diameter (1.6mm, flat across every pin count)
  exceeds every IPC-7251 density level**, including Most (-0.291mm delta
  even there, growing to -0.491mm at Nominal and -0.591mm at Least). So
  real KiCad tracks the standard's hole sizing closely but is
  consistently more generous on annular ring/pad diameter than IPC-7251
  permits at any density level — a genuine standard-vs-practice gap, not
  an implementation bug on either side.
* **Courtyard height is the only metric that varies non-monotonically
  with pin count** (e.g. Nominal deltas of +1.30mm at N=14, -0.22mm at
  N=16, +1.32mm at N=24) — this mirrors MS-001's own body-length table
  not being perfectly linear in pin count either (see the regression
  note above), rather than indicating an error in either file.

## Open follow-ups (not in this deliverable)

* Exposing density level as a first-class CLI/API convenience beyond the
  existing `--density` flag (e.g. generating all three at once for
  comparison).
* Additional DIP width classes (extra_wide/0.900in, ultra_wide/1.000in)
  once real *plastic*-DIP JEDEC outline documents for them are located —
  checked the full `jedec-fpdb/JEDEC/` collection on 2026-09-18 and
  neither exists there yet. The one 0.900in-row-spacing document present,
  `MS-015a`, is for side-brazed **ceramic** DIPs (CERDIP), a different
  package family/body construction than plastic DIP, so it was
  deliberately not adapted as a stand-in data source (would mix a
  ceramic body spec into a plastic-DIP generator with no real
  justification). Nothing at all covers 1.000in row spacing, ceramic or
  plastic, in the current collection.
* Additional families beyond DIP (SOIC is the natural next step, but
  needs IPC-7351B proper rather than IPC-7251, since SOIC is
  surface-mount).
* Cosmetic silkscreen conventions (pin-1 notch, etc.) if a later goal
  needs visual parity with `kicad-fpdb`'s output rather than just
  standards-derived geometry.

## Regular and wide width classes (2026-09-18)

Added `regular` (0.400in/10.16mm row spacing) and `wide` (0.600in/15.24mm
row spacing), closing the "Open follow-ups" item above, once real copies
of `MS-010` (regular) and `MS-011` (wide) became available in
`jedec-fpdb/JEDEC/` (gitignored, same convention as MS-001/IPC-7251).
Both are addenda documenting only a subset of variations — MS-010 Issue C
covers just N=22/24/28/32, MS-011 Issue B just N=24/28/40/48 — not full
base standards with every pin count, unlike MS-001's own fuller N=14–28
table. `data/ms001_dip.py` was restructured from flat module constants
into a `_WidthClass` dataclass keyed by width class (`row_spacing_mm`,
`body_width_mm`, and its own `body_length_table_mm`), with
`row_spacing_mm()`/`body_width_mm()`/`body_length_mm()` functions
replacing the old `ROW_SPACING_MM`/`BODY_WIDTH_MM` constants and
single-table `body_length_mm(pin_count)`. `PITCH_MM`/`LEAD_WIDTH_MAX_MM`
stay shared top-level constants — both new documents confirm identical
values to MS-001's own (0.100in pitch, 0.022in max lead width).

Pin-count coverage for each new class was grounded in what real KiCad
files actually exist (`Package_DIP.pretty`'s `_W10.16mm`/`_W15.24mm`
base files), not just the documented table entries, reusing the same
linear-regression extrapolation already established for narrow's N=8:
regular covers N=4–16 (even) plus 22/24 (9 real files; N=28/32 are also
directly supported since MS-010 documents them, just with no real file
to compare against), wide covers N=24/26/28/32/40/42/48/64 (8 real
files). Regular's extrapolation turned out unusually low-risk: its 4
documented points (N=22/24/28/32) fall on a perfectly linear D-vs-N line
(slope exactly half the lead pitch, 1.27mm/pin), so extrapolating down to
N=4 follows the same line rather than guessing at curvature. Wide's table
is noisier, like narrow's, and its extrapolation reaches further past the
table's own range (N=64 vs. a max of 48) — same accepted-uncertainty
category as narrow's N=8, not a new kind of risk.

While transcribing this data, found and fixed a real (if tiny) bug in the
*existing* narrow data: `LEAD_WIDTH_MAX_MM` had been hand-computed from
MS-001's `.022in` and typed as a 3-decimal rounded `0.559`, not the exact
`0.5588`. Root cause was doing the inch→mm conversion by hand instead of
in code — 25.4mm/inch is an exact ratio, so there's no inherent precision
loss from working in mm, only from rounding a hand-computed literal
before typing it in. Fixed by adding an `_in()` helper (`inches * 25.4`)
and expressing every constant in `ms001_dip.py` as a computed conversion
from its documented inch value, rather than a hand-rounded mm literal
(wide's D/E1 values are the one exception, converted verbatim from
MS-011's own already-published mm table instead, since those mm numbers
are the document's own, not derived by us).

Comparison against real KiCad files (`tests/test_compare.py`, 17 new
cases) confirms the same pattern narrow already established, now shown
to hold independent of width class:

* Pitch and row spacing still match exactly (0.000mm) across both new
  classes — expected, both are Basic dimensions.
* Drill delta (-0.0412mm at Nominal) and pad diameter delta (-0.4912mm
  at Nominal) are the same magnitude as narrow's own findings above,
  confirming IPC-7251's hole/pad sizing is genuinely width-class-
  independent — it only depends on lead width, which MS-001/010/011 all
  document identically.
* Courtyard width delta is consistently negative for both classes (-0.46
  regular, -0.44 wide) — generated courtyards run narrower than real
  KiCad's. Courtyard *height*, however, flips sign for wide (+0.52mm at
  N=24 up to +1.17mm at N=26) where narrow/regular's height delta was
  negative or mixed-sign — a new observation this data didn't surface
  before: real KiCad appears to give wide-body DIPs more vertical
  courtyard headroom than IPC-7251's flat excess-plus-round-up formula
  produces, more so than for narrow/regular.
