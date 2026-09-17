# Corner Marks Extend to Courtyard Jog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed `CORNER_MARK_MM = 0.3` leg length on LQFP/QFN's F.SilkS corner-mark brackets with a length computed exactly to reach the courtyard's own "jog" (the point where the stepped F.CrtYd outline transitions from the plain body corner to the adjacent side's pad-arm edge) on that same side.

**Architecture:** `_add_corner_marks` (`kicad_fpdb/pipeline.py`) gains two new optional parameters — `side_groups` (the same per-side arm rects `_quad_side_groups` already computes for the courtyard) and `mx`/`my` (the same courtyard margins already in scope at the call site) — and computes each leg's endpoint directly from the adjacent side's margin-expanded edge instead of a fixed offset, falling back to the old fixed-length behavior when a given side's data isn't available. `_add_outline`'s single call site (only ever reached by LQFP/QFN) is updated to pass this data through. No new yaml params, no per-family opt-in — the fix applies everywhere `_add_corner_marks` is used.

**Tech Stack:** Python, pytest. No new dependencies.

## Global Constraints

- Leg **direction** does not change — legs still point inward, from the silk body corner toward the center. Only the **length** changes.
- No change to any family other than LQFP/QFN — no other family reaches `_add_corner_marks`.
- No change to F.CrtYd or F.Fab geometry — only the F.SilkS corner-mark legs.
- Full test suite (`pytest`) must pass after every task, including the regression suite where the local machine has the real KiCad footprint library installed (it self-skips otherwise, per `CLAUDE.md`'s cross-machine notes).

---

### Task 1: Add jog-based leg computation (with fallback) to `_add_corner_marks`

**Files:**
- Modify: `kicad_fpdb/pipeline.py:96-103` (`_add_corner_marks`)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `kicad_fpdb.geometry.Line` (already imported and used elsewhere in this file).
- Produces: `_add_corner_marks(geometry, sx0, sy0, sx1, sy1, side_groups: dict[str, tuple[float, float, float, float]] | None = None, mx: float = COURTYARD_MARGIN_MM, my: float = COURTYARD_MARGIN_MM) -> None`. `side_groups` uses the exact same shape `_quad_side_groups` already returns: `{"left"|"right"|"top"|"bottom": (x0, y0, x1, y1)}`, raw pad-group bbox (not yet margin-expanded — `_add_corner_marks` applies `mx`/`my` itself). Missing keys or `side_groups=None` fall back to the pre-existing fixed `CORNER_MARK_MM` behavior for the affected leg(s) only.

- [ ] **Step 1: Write the failing unit tests**

Add to `tests/test_pipeline_outline.py`, right after the existing `test_add_outline_with_body_size_keeps_pin1_marker` (both already import `_add_outline` from `kicad_fpdb.pipeline`; add `_add_corner_marks` to that same import line):

```python
def test_add_corner_marks_extends_legs_to_side_group_jog():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    side_groups = {
        "top": (-1.0, -3.0, 1.0, -2.2),
        "bottom": (-1.0, 2.2, 1.0, 3.0),
        "left": (-3.0, -1.0, -2.2, 1.0),
        "right": (2.2, -1.0, 3.0, 1.0),
    }
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0, side_groups=side_groups, mx=0.25, my=0.25)

    assert len(geometry.lines) == 8
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # Each leg now reaches the adjacent side's own margin-expanded edge
    # (e.g. top-left corner's horizontal leg is bounded by "top"'s own
    # left edge minus mx: -1.0 - 0.25 = -1.25) instead of a fixed 0.3mm
    # offset -- see docs/superpowers/specs/2026-09-17-corner-mark-
    # extends-to-courtyard-jog-design.md.
    assert (-2.0, -2.0) in endpoints
    assert (-1.25, -2.0) in endpoints
    assert (-2.0, -1.25) in endpoints
    assert (2.0, -2.0) in endpoints
    assert (1.25, -2.0) in endpoints
    assert (2.0, -1.25) in endpoints
    assert (2.0, 2.0) in endpoints
    assert (1.25, 2.0) in endpoints
    assert (2.0, 1.25) in endpoints
    assert (-2.0, 2.0) in endpoints
    assert (-1.25, 2.0) in endpoints
    assert (-2.0, 1.25) in endpoints
    for line in geometry.lines:
        assert line.layer == "F.SilkS"


def test_add_corner_marks_falls_back_to_fixed_length_without_side_groups():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0)

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # No side_groups at all -- every leg keeps the old fixed 0.3mm length.
    assert (-1.7, -2.0) in endpoints
    assert (-2.0, -1.7) in endpoints
    assert (1.7, -2.0) in endpoints
    assert (2.0, -1.7) in endpoints
    assert (1.7, 2.0) in endpoints
    assert (2.0, 1.7) in endpoints
    assert (-1.7, 2.0) in endpoints
    assert (-2.0, 1.7) in endpoints


def test_add_corner_marks_falls_back_per_leg_when_one_side_is_missing():
    from kicad_fpdb.geometry import FootprintGeometry
    geometry = FootprintGeometry(name="TEST")
    # No "top" entry -- both top corners' horizontal legs must fall back
    # to the fixed length, while every other leg (bounded by a side that
    # IS present) still computes from side_groups.
    side_groups = {
        "bottom": (-1.0, 2.2, 1.0, 3.0),
        "left": (-3.0, -1.0, -2.2, 1.0),
        "right": (2.2, -1.0, 3.0, 1.0),
    }
    _add_corner_marks(geometry, -2.0, -2.0, 2.0, 2.0, side_groups=side_groups, mx=0.25, my=0.25)

    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in geometry.lines for pt in (line.start, line.end)}
    # Top corners' horizontal legs: fixed-length fallback (no "top").
    assert (-1.7, -2.0) in endpoints
    assert (1.7, -2.0) in endpoints
    # Top corners' vertical legs: computed from "left"/"right" (present).
    assert (-2.0, -1.25) in endpoints
    assert (2.0, -1.25) in endpoints
    # Bottom corners: fully computed (both "bottom" and "left"/"right" present).
    assert (1.25, 2.0) in endpoints
    assert (2.0, 1.25) in endpoints
    assert (-1.25, 2.0) in endpoints
    assert (-2.0, 1.25) in endpoints
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k add_corner_marks -v`
Expected: all 3 FAIL — the first two with assertion errors (old fixed-length-only behavior doesn't match the new expected endpoints / doesn't accept `side_groups`/`mx`/`my` yet — `TypeError: unexpected keyword argument`), the third likewise.

- [ ] **Step 3: Implement the new leg computation**

Replace `_add_corner_marks` in `kicad_fpdb/pipeline.py` (lines 96-103) with:

```python
def _add_corner_marks(geometry, sx0: float, sy0: float, sx1: float, sy1: float,
                       side_groups: dict[str, tuple[float, float, float, float]] | None = None,
                       mx: float = COURTYARD_MARGIN_MM, my: float = COURTYARD_MARGIN_MM) -> None:
    # Each leg extends inward from the silk body corner until it reaches
    # the courtyard's own "jog" on that same side -- the point where the
    # stepped F.CrtYd outline transitions from the plain body corner to
    # the adjacent side's own pad-arm edge -- instead of a fixed offset.
    # side_groups uses the same per-side arm rects _quad_side_groups
    # already computes for the courtyard (raw pad-group bbox, not yet
    # margin-expanded -- mx/my are applied here). A missing side (or no
    # side_groups at all) falls back to the old fixed CORNER_MARK_MM
    # length for just that leg -- not reachable today (LQFP/QFN's
    # quad_perimeter always populates all four sides) but keeps this
    # function safe to call with partial data. See docs/superpowers/
    # specs/2026-09-17-corner-mark-extends-to-courtyard-jog-design.md.
    side_groups = side_groups or {}
    corners = [(sx0, sy0), (sx1, sy0), (sx1, sy1), (sx0, sy1)]
    for cx, cy in corners:
        x_dir = 1.0 if cx == sx0 else -1.0
        y_dir = 1.0 if cy == sy0 else -1.0

        horiz_side = side_groups.get("top" if cy == sy0 else "bottom")
        if horiz_side is not None:
            leg_x_end = horiz_side[0] - mx if x_dir > 0 else horiz_side[2] + mx
        else:
            leg_x_end = cx + x_dir * CORNER_MARK_MM

        vert_side = side_groups.get("left" if cx == sx0 else "right")
        if vert_side is not None:
            leg_y_end = vert_side[1] - my if y_dir > 0 else vert_side[3] + my
        else:
            leg_y_end = cy + y_dir * CORNER_MARK_MM

        geometry.lines.append(Line(start=(cx, cy), end=(leg_x_end, cy), layer="F.SilkS"))
        geometry.lines.append(Line(start=(cx, cy), end=(cx, leg_y_end), layer="F.SilkS"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k add_corner_marks -v`
Expected: all 3 PASS.

- [ ] **Step 5: Run the full unit test suite to confirm no regression**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS except `test_add_outline_with_body_size_draws_corner_marks` and the 3 `test_generate_footprint_qfp*_silk_matches_real_corner*` tests, which are expected to FAIL here — they still assert the old fixed-length endpoints and are updated in Task 2 (this function isn't wired into `_add_outline`'s caller yet, so those specific tests are unaffected by this step and were already passing before it — re-run to confirm nothing *else* broke).

- [ ] **Step 6: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "Add jog-based leg computation to _add_corner_marks, with fixed-length fallback

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 2: Wire the new computation into `_add_outline` and update existing corner-mark tests

**Files:**
- Modify: `kicad_fpdb/pipeline.py:316-327` (`_add_outline`'s `elif body_size is not None:` branch)
- Test: `tests/test_pipeline_outline.py`

**Interfaces:**
- Consumes: `_add_corner_marks(geometry, sx0, sy0, sx1, sy1, side_groups=..., mx=..., my=...)` from Task 1; `_quad_side_groups(pads)` (already defined and used elsewhere in `_add_outline`, at `kicad_fpdb/pipeline.py:77-93`); `mx`/`my` (already computed at the top of `_add_outline`, lines 125-126).
- Produces: every LQFP/QFN footprint's corner marks now reach the courtyard jog instead of a fixed 0.3mm.

- [ ] **Step 1: Write the failing test updates**

In `tests/test_pipeline_outline.py`, update `test_add_outline_with_body_size_draws_corner_marks` (currently around line 247-269) to the new expected endpoints, computed by hand from the `_qfp32_geometry()` fixture's real pad positions (`_quad_side_groups` on those pads gives `top=(-3.05, -4.925, 3.05, -3.425)`, `left=(-4.925, -3.05, -3.425, 3.05)`, etc. — symmetric — and this test calls `_add_outline(geometry, body_size=7.22)` with no `courtyard_margin_x`/`_y`, so `mx=my=COURTYARD_MARGIN_MM=0.5`):

```python
def test_add_outline_with_body_size_draws_corner_marks():
    geometry = _qfp32_geometry()
    _add_outline(geometry, body_size=7.22)

    silk_lines = [line for line in geometry.lines if line.layer == "F.SilkS"]
    # 4 corners x 2 legs each = 8 short lines, no full-perimeter rectangle.
    assert len(silk_lines) == 8

    # Real LQFP-32_7x7mm_P0.8mm.kicad_mod body corners are at (±3.61, ±3.61).
    # Legs now extend inward exactly to the adjacent side's own courtyard
    # jog (this test's fixture pads give a "top"/"left" arm edge at
    # ±3.05, minus the 0.5mm default courtyard margin -- since this test
    # doesn't pass courtyard_margin_x/_y -- landing at ±3.55) instead of
    # the old fixed ±0.3mm offset (±3.31).
    endpoints = {(round(pt[0], 5), round(pt[1], 5)) for line in silk_lines for pt in (line.start, line.end)}
    assert (-3.61, -3.61) in endpoints
    assert (-3.55, -3.61) in endpoints
    assert (-3.61, -3.55) in endpoints
    assert (3.61, -3.61) in endpoints
    assert (3.55, -3.61) in endpoints
    assert (3.61, -3.55) in endpoints
    assert (3.61, 3.61) in endpoints
    assert (3.55, 3.61) in endpoints
    assert (3.61, 3.55) in endpoints
    assert (-3.61, 3.61) in endpoints
    assert (-3.55, 3.61) in endpoints
    assert (-3.61, 3.55) in endpoints
```

Update the 3 `test_generate_footprint_qfp*_silk_matches_real_corner*` tests (around lines 425-448) — these go through the real `LQFP` yaml params (`courtyard_margin_x = courtyard_margin_y = 0.25`), so the new endpoints differ from the trimmed-fixture test above:

```python
def test_generate_footprint_qfp32_silk_matches_real_corner_marks():
    text = generate_footprint("LQFP-32", FAMILY_TREE_PATH, name="LQFP32_TEST")
    assert "(start -3.61 -3.61)" in text
    # Leg now reaches the courtyard jog (-3.3) instead of the old fixed
    # -3.31 -- a 0.01mm difference for this specific variant, since its
    # jog happens to sit almost exactly where the old fixed length did.
    assert "(end -3.3 -3.61)" in text
    assert "(end -3.61 -3.3)" in text


def test_generate_footprint_qfp48_silk_matches_real_corner_position():
    text = generate_footprint("LQFP-48", FAMILY_TREE_PATH, name="LQFP48_TEST")
    # Same 7x7mm body as LQFP-32, but LQFP-48's own pad layout gives a
    # different jog position -- -3.15, close to real KiCad's own 0.45mm
    # leg for this package (real: -3.16), unlike the old fixed -3.31
    # this project previously used for every LQFP variant alike.
    assert "(start -3.61 -3.61)" in text
    assert "(end -3.15 -3.61)" in text


def test_generate_footprint_qfp100_silk_matches_real_corner_position():
    # Real LQFP-100_14x14mm_P0.5mm.kicad_mod corner marks are at
    # (+-7.11, +-7.11) -- proves body_size derivation
    # (courtyard_body_size + 0.22) generalizes beyond the 7x7mm bodies
    # LQFP-32/LQFP-48 share, to a 14x14mm body.
    text = generate_footprint("LQFP-100", FAMILY_TREE_PATH, name="LQFP100_TEST")
    assert "(start -7.11 -7.11)" in text
    assert "(end -6.4 -7.11)" in text
```

- [ ] **Step 2: Run these 4 tests to verify they fail**

Run: `pytest tests/test_pipeline_outline.py -k "corner_marks or qfp32_silk or qfp48_silk or qfp100_silk" -v`
Expected: all 4 FAIL — `_add_outline`'s caller doesn't pass `side_groups`/`mx`/`my` yet, so `_add_corner_marks` still falls back to the fixed `CORNER_MARK_MM` length, producing the old endpoints instead of these new ones.

- [ ] **Step 3: Wire `_quad_side_groups` and the margins into the caller**

In `kicad_fpdb/pipeline.py`, in `_add_outline`'s `elif body_size is not None:` branch (around lines 316-327), change:

```python
        sx0, sx1 = center_x - half, center_x + half
        sy0, sy1 = center_y - half, center_y + half
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1)
```

to:

```python
        sx0, sx1 = center_x - half, center_x + half
        sy0, sy1 = center_y - half, center_y + half
        side_groups = _quad_side_groups(geometry.pads)
        _add_corner_marks(geometry, sx0, sy0, sx1, sy1, side_groups=side_groups, mx=mx, my=my)
```

(`mx`/`my` are already computed at the top of `_add_outline`, lines 125-126 — no new computation needed here.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pipeline_outline.py -k "corner_marks or qfp32_silk or qfp48_silk or qfp100_silk" -v`
Expected: all 4 PASS.

- [ ] **Step 5: Run the full unit test suite**

Run: `pytest tests/test_pipeline_outline.py -v`
Expected: all PASS.

- [ ] **Step 6: Run the full suite, including the regression suite**

Run: `pytest tests/ -v`
Expected: all PASS (or the pre-existing 1 known skip, `R-0201`'s unnumbered-pad gap, on a machine with the real KiCad footprint library — the regression suite itself skips entirely on a machine without it, per `CLAUDE.md`'s cross-machine notes). This change only touches F.SilkS corner marks, which the regression suite doesn't assert on directly, but every LQFP/QFN case still goes through `generate_footprint` — confirms nothing else in those families regressed.

- [ ] **Step 7: Visual review**

Run: `python -m kicad_fpdb.render_png --family LQFP QFN --output-dir renders_png`

Open a small case (`renders_png/QFN-12.png`) and a large one (`renders_png/LQFP-208.png` if present, else the largest LQFP rendered) and confirm the generated (left) panel's corner marks now visibly reach the courtyard's own jog, compared to the reference (right) panel's real-KiCad marks (which stay shorter, per the accepted approximation this project already documents).

- [ ] **Step 8: Commit**

```bash
git add kicad_fpdb/pipeline.py tests/test_pipeline_outline.py
git commit -m "Wire jog-based corner-mark lengths into _add_outline for LQFP/QFN

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

### Task 3: Document in CLAUDE.md and CHANGELOG.md

**Files:**
- Modify: `CLAUDE.md` (narrative log section)
- Modify: `CHANGELOG.md` (top of file)

**Interfaces:** None — documentation only.

- [ ] **Step 1: Add a CLAUDE.md entry**

Append a new bullet to `CLAUDE.md`'s narrative log (the `## Claude-isms below` section), after the most recent entry and before `## TODO`:

```markdown
* LQFP/QFN's F.SilkS corner-mark legs no longer use a fixed 0.3mm
  length for every variant of both families — each leg now extends
  inward exactly until it reaches the courtyard's own "jog" (the point
  where the stepped F.CrtYd outline transitions from the plain body
  corner to the adjacent side's own pad-arm edge), computed from the
  same `_quad_side_groups` per-side rects the courtyard itself already
  uses. No new yaml params or per-family opt-in — `_add_corner_marks`
  is only ever reached by LQFP/QFN, so the fix applies everywhere it's
  used. Direction is unchanged (still inward); only the length is now
  exact instead of approximated. Coincidentally lands close to real
  KiCad's own per-package lengths on the cases checked (LQFP-48: 0.46mm
  computed vs. real KiCad's 0.45mm for that package, previously this
  project's flat 0.3mm for every LQFP variant alike) without attempting
  to match them exactly — still a deliberate, symbolic convention, not
  real-KiCad matching (see the original corner-mark design spec's own
  "not meant to pixel-match" framing). `_add_corner_marks` gained a
  fixed-length fallback for a missing/absent side, not reachable today
  since `quad_perimeter` always populates all four sides, but keeps the
  function safe to call with partial data. See docs/superpowers/specs/
  2026-09-17-corner-mark-extends-to-courtyard-jog-design.md.
```

- [ ] **Step 2: Add a CHANGELOG.md entry**

Check the most recent entry's date/version at the top of `CHANGELOG.md` and add a new entry above it, incrementing the version and using today's date. If the most recent entry is already dated today (same-day work), fold this into that existing entry instead of adding a new heading, per this project's own changelog convention (concatenate same-day version bumps under one heading).

```markdown
* Replaced LQFP/QFN's fixed 0.3mm corner-mark leg length with one
  computed exactly to reach the courtyard's own jog on each side,
  instead of approximating every variant with the same constant. See
  docs/superpowers/specs/2026-09-17-corner-mark-extends-to-courtyard-
  jog-design.md.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md CHANGELOG.md
git commit -m "Document the corner-mark courtyard-jog change in CLAUDE.md and CHANGELOG.md

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```
