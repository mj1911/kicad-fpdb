# Footprint Descriptor + Generator Engine — Design Spec

Date: 2026-09-13

## Background

KiCad ships thousands of footprint files, many nearly identical variants of
the same underlying package family (e.g. DIP-16 vs DIP-18 differ by two
pins in a well-defined way). This project ("kicad-fpdb") aims to replace
one-file-per-footprint with a condensed, hierarchical descriptor database
that generates footprint geometry on demand.

This spec covers the **first, foundational sub-project only**: the
descriptor language and the geometry-generation engine. It deliberately
excludes the KiCad plugin/UI, full-library conversion, and the future
community contribution/moderation server — each is a separate future spec
once this foundation is proven.

## Goals

- Design a descriptor syntax that can express a footprint variant as a
  short string (e.g. `DIP-16 r 2.54`).
- Design a hierarchical family-tree data model with parameter inheritance,
  so related package families (DIP, SOIC, QFP, chip passives, ...) share
  definitions instead of duplicating geometry logic.
- Implement a generator engine that resolves a descriptor against the
  family tree and produces real `.kicad_mod` files.
- Validate correctness against KiCad's own official footprint library,
  across a broad slice of families, with a permanent automated regression
  suite.

## Non-goals (deferred to future specs)

- KiCad plugin / footprint-picker UI integration.
- Converting KiCad's entire existing library into the descriptor format.
- Community upload / moderator review server.
- 3D model references, footprint metadata (tags/description text), and
  fine-grained courtyard nuances beyond basic clearance.

## Architecture

Four independently testable stages:

```text
descriptor string ("DIP-16 r 2.54")
        │
        ▼
 [1] Descriptor Parser  ──►  parsed query {family, variant, modifiers}
        │
        ▼
 [2] Family Tree Resolver  ──►  resolved parameter set (walks kicad-fpdb.yaml,
        │                        applies inheritance, merges query overrides)
        ▼
 [3] Shape Generator Library  ──►  FootprintGeometry (in-memory pads/lines/
        │                          arcs/courtyard model)
        ▼
 [4] KiCad Writer  ──►  .kicad_mod file (S-expression text)
```

- The **family tree** (`kicad-fpdb.yaml`) is the single data file that is
  field-updatable/crowd-sourced later (per the project's long-term vision).
- The **shape generator library** is a small, fixed, hand-written Python
  module — the tested "engine" — and changes rarely.
- Each stage has a clean input/output type and is tested independently.

## 1. Descriptor Syntax

```text
descriptor := FAMILY "-" VARIANT_TOKEN [MODIFIER ...]
FAMILY        := identifier (e.g. DIP, SOIC, QFP, R, C)
VARIANT_TOKEN := family-defined token (often a pin count, but not always —
                 e.g. a chip-passive size code like "0603")
MODIFIER      := family-defined single-letter code (e.g. width class) or
                 a decimal value (e.g. pitch in mm), all optional —
                 omitted modifiers fall back to family-tree defaults
```

Examples:

- `DIP-16 r 2.54` → family=DIP, variant=16, width=regular, pitch=2.54mm
  (2.54mm is the standard DIP pitch and also the family-tree default;
  the modifier is spelled out here only to illustrate the grammar —
  pitch is in mm throughout, never inches, so a bare "0.1" would mean
  0.1mm, not 0.1in)
- `SOIC-8` → family=SOIC, variant=8, pitch defaults from family tree
- `R-0603` → family=R, variant="0603" (a size code, not a pin count)

**Key design point:** the parser is family-agnostic. It produces a generic
`{family, variant, modifiers: {...}}` structure; the *family's own schema*
(declared in the family tree) defines what its variant token and modifiers
mean and how they're validated. Adding a new package shape only requires
updating the family tree, never the parser.

**Search fallback:** unrecognized or ambiguous input triggers a fuzzy
search against the family tree rather than a hard error, matching the
intended user workflow (search "dip", get candidate matches, pick one).

**Expected evolution:** this grammar is a starting point, not final. The
full KiCad library contains far more variation than DIP/SOIC/QFP/chip
passives can anticipate, and the grammar is expected to grow substantially
as more of the library is surveyed. The family-agnostic parser design is
specifically intended to absorb that growth without parser rewrites — new
variation should mean new family-tree schema, not new grammar rules,
wherever possible. Where it isn't possible, grammar changes should be
made deliberately and documented, not organically.

## 2. Family Tree Data Model

A single YAML file, `kicad-fpdb.yaml`, tree-structured. Each node may
define or override:

```yaml
DIP:
  generator: dual_row_grid
  params:
    pitch: 2.54
    row_spacing: { narrow: 7.62, regular: 10.16, wide: 15.24 }
    pad_size: [1.6, 1.6]
    pad_shape: rect_first_round_rest
  variants: { n: narrow, r: regular, w: wide }

  children:
    DIP-SKINNY:
      params:
        pitch: 1.778
```

**Inheritance rule:** a child's effective params = parent's effective
params, with the child's own `params` merged on top. Merging is a shallow
key overwrite, except dict-valued params (like `row_spacing`) which merge
key-by-key rather than being replaced wholesale. A query's own explicit
modifiers are merged on top of that again.

Priority, low to high:

```text
family defaults  →  inherited overrides down the tree  →  descriptor overrides
```

Each family node names a `generator` (a function in the shape generator
library). Children inherit their parent's generator unless they override
it, allowing a family to keep shared electrical/geometric params while
substituting a different geometry generator if needed.

**Validation:** loading `kicad-fpdb.yaml` fails fast, with a clear error, if
a node references an unknown generator, or if the merged parameter set
doesn't satisfy that generator's declared required-parameter schema.

## 3. Shape Generator Library

A small, hand-written, well-tested Python module (not data) — this is
where geometric correctness lives. Each generator is a pure function:

```python
def dual_row_grid(pin_count: int, pitch: float, row_spacing: float,
                   pad_size: tuple[float, float], pad_shape: str) -> FootprintGeometry:
    ...
```

Returns a generator-agnostic `FootprintGeometry`: a plain dataclass with
pad list (position, size, shape, number), silkscreen/fab/courtyard outline
primitives (lines/arcs/rects), and reference/value text placement. This is
the intermediate representation decoupling geometry math from KiCad's file
format.

Initial generators for the broad-slice proof-of-concept:

- `dual_row_grid` — DIP, SOIC, SSOP (THT and SMD dual-row ICs)
- `quad_perimeter` — QFP/QFN-style quad packages
- `two_pad_chip` — chip resistors/capacitors (0402/0603/0805, ...)

Each generator is unit-tested standalone against hand-computed expected
coordinates, independent of the family tree/parser — geometric correctness
is verified at this layer directly, before descriptor resolution is even
involved.

Outline geometry (silkscreen/courtyard/fab layer conventions — clearance,
setback, etc.) follows the conventions observed in the real KiCad library
files used for validation, rather than being guessed.

## 4. KiCad Writer

Converts `FootprintGeometry` into a valid `.kicad_mod` file (S-expression
format). Targets whatever format version the locally installed `kicad-cli`
reports as current.

- Pure serializer: `FootprintGeometry → str`. No knowledge of families,
  descriptors, or generators.
- Structural pieces: module header/attributes, pad entries (`(pad ...)`),
  graphic layer entries (`(fp_line ...)`, `(fp_arc ...)`, `(fp_rect ...)`),
  reference/value text.
- 3D model references (`(model ...)`) are omitted for this phase.
- Correctness check: round-trip validity — generate a file, then confirm
  it parses as structurally valid via KiCad's own tooling, before
  comparing geometry values.

Out of scope for this phase: 3D model references, footprint metadata
(tags/description), and courtyard nuances beyond basic clearance.

## 5. Validation & Testing

**Automated (primary regression suite):**

- Pull real reference footprints from the locally installed KiCad library
  (`/usr/share/kicad/footprints/*.pretty`).
- Given the variability across footprint families (different pitches,
  widths, pad shapes, row spacings), the reference set should cover
  **multiple variants per family**, not just one example each — e.g.
  several DIP pitch/width combinations, several SOIC pitches, several
  chip-passive sizes, a couple of QFP pitches. This is deliberately not a
  fixed small number; it should grow as more variation is discovered
  during implementation.
- For each reference footprint, hand-write the equivalent descriptor (and
  any needed family-tree entries), run it through the full pipeline, and
  diff generated pad positions/sizes/shapes against the real file's pads
  (parsed via the same S-expression reader), tolerance ~1µm for float
  rounding.
- This becomes a permanent pytest regression suite — every
  family/generator combination gets at least one "reproduces a real
  footprint" test, and ideally several to exercise inheritance and
  parameter-merging across variants.

**Manual (spot-check):**

- Open a handful of generated footprints in KiCad's footprint editor to
  visually confirm silkscreen/courtyard/text placement looks sane —
  automated pad-diffing won't catch overlapping silkscreen or text
  placement issues.

## Success Criteria

The descriptor + generator engine reproduces a broad set of real
reference footprints (multiple variants across DIP, SOIC, QFP, and chip
passive families) within the automated regression suite, with manual
visual confirmation in KiCad's footprint editor for a subset of them.

## Open Questions / Future Work

- Exact `.kicad_mod` format version to target (pin to whatever the local
  `kicad-cli` reports; confirm during implementation).
- 3D model references and footprint metadata — deferred.
- Full-library conversion pipeline — separate future spec.
- KiCad plugin/UI integration — separate future spec.
- Community contribution/moderation server — separate future spec.
- Descriptor grammar is expected to evolve significantly as more of the
  library's variation is surveyed; changes should be deliberate and
  documented.
