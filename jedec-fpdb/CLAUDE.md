# jedec-fpdb

A spec-derived DIP footprint generator: builds `.kicad_mod` files purely
from JEDEC MS-001/MS-010/MS-011 (package body/lead outline) and
IPC-7251 Table 3-5 (Dual In-Line Packages thru-hole land pattern
sizing), with no reference to any real `.kicad_mod` file as a data
source. This is the deliberate opposite of the sibling `kicad-fpdb/`
project's approach (reverse-engineering geometry from KiCad's own real
library files) — the point of this project is to answer "what would a
standards-compliant land pattern look like," then compare that against
what KiCad actually ships, as a read-only sanity check afterward. See
`docs/superpowers/specs/2026-09-17-dip-ipc-generator-design.md` for the
full design rationale, and `notes.txt` for an early Q&A on how far a
purely-formulaic approach could realistically extend to other families.

## Claude-isms

* Dev environment: this package is deliberately never `pip install`ed
  (not even editable) — the plan's Global Constraints ruled that out up
  front to sidestep this machine's externally-managed-Python pip
  restriction entirely. Everything runs via Python's own `sys.path`
  insertion instead: `pytest` (via `pythonpath = ["."]` in
  `pyproject.toml`, needed so `from data import ms001_dip` resolves)
  and `python -m jedec_fpdb ...` / `python -m jedec_fpdb.visual_compare`
  both require cwd = this `jedec-fpdb/` directory. `tests/test_compare.py`
  and `tests/test_visual_compare.py`'s tool-dependent cases skip
  gracefully (`pytest.mark.skipif`) when `/usr/share/kicad/footprints/
  Package_DIP.pretty`, `kicad-cli`, or `rsvg-convert` aren't present —
  core generator/geometry/formula tests need none of them.
* Real JEDEC/IPC source documents live in `JEDEC/` (gitignored — not
  ours to redistribute, same convention `kicad-fpdb` uses for the real
  KiCad library itself). Reading the *actual* MS-001 (Issue D) document
  before writing any code surfaced two scope-narrowing facts, resolved
  with the user before the implementation plan: it covers only the
  0.300in (narrow) row-spacing family, and its full-lead body-length
  table has no N=8 entry (8 only appears under a different,
  less-common "1/2 lead" staggered variation). Per the user's decision,
  N=8 is computed by linear least-squares regression over the table's
  own N=14–28 values rather than guessed — the same extrapolation
  approach later reused for regular/wide's own out-of-table pin counts.
* IPC-7251's real Table 3-5 ("Dual In-Line Packages") replaced an
  initial best-effort placeholder formula once a real copy of the
  standard was located: annular ring excess is added directly to the
  drill diameter (Table 3-5's own "added to hole dia." wording), *not*
  doubled as a per-side radius value like the placeholder had assumed;
  courtyard excess is density-dependent (Most/Nominal/Least, i.e. Level
  A/B/C), not a flat guess; and courtyard width/height are each rounded
  up to the nearest 0.10mm as a final step (never down), per the
  table's own "Courtyard Round-off factor."
* Built in six small TDD-plan tasks (scaffolding + MS-001 data →
  IPC-7251 formulas → geometry + `dip.py` generator → `.kicad_mod`
  writer → `compare.py` against real files → CLI + README), each
  committed independently. `compare.py`/its tests are the *only*
  contact with `kicad-fpdb`'s world: reading real reference
  `.kicad_mod` files directly off the filesystem
  (`/usr/share/kicad/footprints/Package_DIP.pretty/`) as a plain path
  string, never importing `kicad_fpdb` code or copying its data — see
  the design spec's "Code sharing" section.
* Running `compare.diff()` across every covered pin count and density
  level against real KiCad files surfaced a real, consistent pattern
  (not per-file noise), written up in the design spec's Findings
  section: pitch and row spacing match real KiCad exactly (both are
  JEDEC Basic/theoretical-exact dimensions); real KiCad's drill
  diameter (a flat 0.8mm regardless of pin count) tracks IPC-7251's own
  "Most" (Level A) density level almost exactly (+0.009mm), while its
  pad diameter (a flat 1.6mm) exceeds *every* density level including
  Most (-0.291mm even there) — real KiCad is closely standards-aligned
  on hole sizing but consistently more generous than IPC-7251 permits
  on annular ring, a genuine standard-vs-practice gap rather than a bug
  on either side; and courtyard height is the only metric that varies
  non-monotonically with pin count, mirroring MS-001's own non-linear
  body-length table rather than indicating an error.
* Added `regular` (MS-010, 0.400in/10.16mm row spacing) and `wide`
  (MS-011, 0.600in/15.24mm) width classes once real copies of those
  documents arrived in `JEDEC/` — both are addenda documenting only a
  subset of variations (MS-010 Issue C: N=22/24/28/32 only; MS-011
  Issue B: N=24/28/40/48 only), not full base standards, unlike
  MS-001's fuller N=14–28 table. `data/ms001_dip.py` was restructured
  from flat module constants into a `_WidthClass` dataclass keyed by
  width class, grounding each new class's supported pin-count range in
  which real KiCad files actually exist (`_W10.16mm`/`_W15.24mm`) rather
  than just the documented table entries. Regular's extrapolation turned
  out unusually low-risk — its 4 documented points fall on a perfectly
  linear D-vs-N line (slope exactly half the lead pitch, 1.27mm/pin) —
  while wide's table is noisier and its extrapolation reaches further
  past the table's own range (N=64 vs. a max of 48), same
  accepted-uncertainty category as narrow's own N=8. 17 new comparison
  cases against real KiCad files confirmed the drill/pad-diameter
  pattern above holds independent of width class; courtyard *width*
  delta stayed consistently negative for both new classes, but
  courtyard *height* flipped sign for wide (real KiCad giving wide-body
  DIPs more vertical courtyard headroom than the flat
  excess-plus-round-up formula produces) — a new observation this data
  hadn't surfaced before.
* Fixed a real (if tiny) transcription bug found while adding the width
  classes above: `LEAD_WIDTH_MAX_MM` had been hand-computed from
  MS-001's `0.022in` and typed as a 3-decimal-rounded `0.559`, not the
  exact `0.5588`. Root cause was doing the inch→mm conversion by hand
  instead of in code (25.4mm/inch is an exact ratio, so there's no
  inherent precision loss — only from rounding a hand-computed literal
  before typing it). Fixed with an `_in()` helper (`inches * 25.4`);
  every constant in `ms001_dip.py` is now a computed conversion from
  its documented inch value, except wide's D/E1 values, which MS-011
  publishes as an already-converted mm table and are used verbatim
  rather than re-derived. A second, silently-uncorrected copy of the
  same stale `0.559` had also been hardcoded directly in
  `test_ipc7251.py` (`LEAD = 0.559`) — fixed to import
  `ms001_dip.LEAD_WIDTH_MAX_MM` instead, so it can't drift from the
  real source again.
* Checked `JEDEC/` for plastic-DIP outline docs at 0.900in/1.000in row
  spacing before attempting `extra_wide`/`ultra_wide` — neither exists
  yet. The one 0.900in document present, MS-015a, is for side-brazed
  **ceramic** DIPs (CERDIP), a different package family/body
  construction, deliberately not adapted as a plastic stand-in per user
  decision. Recorded so a future session doesn't re-search without a
  new source document actually arriving.
* Added an interactive Tkinter viewer (`jedec_fpdb/visual_compare.py`,
  `python -m jedec_fpdb.visual_compare`) cycling through every case in
  a new `jedec_fpdb/reference_cases.py` (`CASES`, extracted from
  `test_compare.py`'s own list so both share one source of truth — 23
  cases total: 6 narrow + 9 regular + 8 wide), rasterizing the
  generated and real footprint side by side via `kicad-cli` +
  `rsvg-convert` at matched physical scale with a checkerboard/0.1in
  dot-grid ruler background, mirroring `kicad-fpdb`'s own review-viewer
  conventions closely (same `FRAME_PX`, `PX_PER_MM`, `CHECKER_MM`,
  pad-1-locating-by-`#C83434`-fill technique) but as a native desktop
  Tkinter window instead of an HTML page, and built fresh with no
  shared code. A run of viewer-alignment bugs followed, each caught by
  eye and then fixed with a regression test:
  * The pad-1 grid anchor was first computed by subtracting the
    exported SVG's viewBox origin from the pad's raw `.kicad_mod` `at`
    mm coordinate — wrong, since `kicad-cli`'s SVG export doesn't
    preserve a footprint's own local coordinate frame (confirmed on
    DIP-4 narrow: its real courtyard extends to local `(-1.06, -1.52)`,
    yet the exported SVG's viewBox starts at exactly `(0.0, 0.0)`
    regardless). Fixed by locating pad 1 directly in the *rendered*
    SVG by its `#C83434` copper-fill color instead — the same
    technique `kicad-fpdb`'s own viewer already uses, for the same
    reason.
  * Both panels' grid now shares one anchor — the real reference
    file's own pad-1 position — instead of each panel self-aligning to
    its own pad 1. This is what actually makes a real placement
    mismatch visible: jedec-fpdb's simpler silk body (no REF**/Value
    text, no notch) gives it a different bounding box than the real
    file, which independent per-panel centering had been quietly
    hiding.
  * Rendering was parallelized via a `ThreadPoolExecutor` — each case
    is 4 independent, purely I/O-bound subprocess calls (`kicad-cli`
    ×2, `rsvg-convert` ×2) with no shared state — cutting startup from
    ~11.6s to ~0.9s for all 23 cases (verified byte-identical output
    against the old sequential path first).
  * `python -m jedec_fpdb.visual_compare` now SIGTERMs any other
    running instance of itself on launch (matched via
    `/proc/<pid>/comm` containing `"python"` plus `"jedec_fpdb.
    visual_compare"` in its cmdline, Linux-only) so re-launching by
    hand or via the VS Code task doesn't pile up duplicate windows.
  * Fixed the checkerboard/dot-grid pitch not shrinking along with a
    downscaled panel (e.g. DIP-24, taller than the 500px frame): only
    the one shared anchor pixel happened to line up by construction,
    every other pad drifted off-grid the further it sat from the
    anchor. `_scale_reference_background` now takes the same scale
    factor the image itself was downscaled by.
  * Fixed each panel computing its *own* independent downscale factor
    from its own image size instead of one shared factor for the whole
    case — generated and reference images are rarely the same pixel
    size (jedec-fpdb's simpler silk has a smaller bounding box), so
    whenever either overflowed the frame the two panels silently got
    different grid pitches *and* the viewer's whole "matched true
    physical scale" premise broke (a genuine size difference would get
    independently scaled away instead of staying visible). Replaced
    with one `_shared_scale` (from whichever image's largest dimension
    needs the most shrinking) plus a `_panel_offset` that just centers
    at that shared scale.
* A `.vscode/tasks.json` task ("jedec-fpdb: Visual Review", cwd
  `${workspaceFolder}/jedec-fpdb`) launches the viewer without needing
  to remember the cwd requirement above.
* 2026-09-19: pytest-xdist wired up (`dev` extra + `addopts = "-n 6"`
  in `pyproject.toml`), matching `kicad-fpdb`'s own existing setup, at
  the user's request to keep both projects' test suites consistently
  multi-process. Verified: 101 tests passed in ~3.5s, `bringing up
  nodes...` confirms xdist is active.

## TODO

* Expose density level as a first-class CLI/API convenience beyond the
  existing `--density` flag (e.g. generating all three levels at once
  for comparison) — noted in the design spec, not yet done.
* Additional DIP width classes (`extra_wide`/0.900in, `ultra_wide`/
  1.000in) once real *plastic*-DIP JEDEC outline documents for them are
  located — checked `JEDEC/` on 2026-09-18 and neither exists yet (see
  the Claude-isms note above on why MS-015a doesn't count).
* Additional families beyond DIP — SOIC is the natural next step, but
  needs IPC-7351B proper rather than IPC-7251, since SOIC is
  surface-mount and IPC-7251 is thru-hole-only.
* Cosmetic silkscreen conventions (pin-1 notch, corner marks, etc.) if
  a later goal needs visual parity with `kicad-fpdb`'s own output
  rather than just standards-derived geometry — deliberately out of
  scope so far, since neither JEDEC MS-001 nor IPC-7251/7351B specifies
  them.
