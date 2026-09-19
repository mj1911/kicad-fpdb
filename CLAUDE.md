# kicad-fpdb (monorepo)

This repository hosts independent side projects exploring a condensed,
hierarchical-descriptor alternative to KiCad's per-file footprint
library. Each subdirectory is self-contained (its own `pyproject.toml`,
tests, and docs) — commands and relative paths always assume a working
directory of the subproject itself, not this root.

* `kicad-fpdb/` — the original project: a descriptor language + family-tree
  YAML + shape-generator engine, validated against KiCad's own real
  footprint library. See `kicad-fpdb/CLAUDE.md`.
* `jedec-fpdb/` — an independent from-scratch DIP generator derived purely
  from freely-obtained JEDEC/IPC reference documents, sharing no code or
  data with `kicad-fpdb/`. See `jedec-fpdb/notes.txt`.

## User-defined project goals

* KiCAD dev website (reference): https://dev-docs.kicad.org/en/
* KiCAD add-on specifics: https://dev-docs.kicad.org/en/addons/

Currently, KiCAD ships over 15k footprint files in their library, each
differing by various amounts, many closely related.  This is highly
inefficient storage-wise.  It is also limiting, since if a footprint
doesn't already exist in the library, it must be created manually.
Footprints are inherently classed; a DIP-16 footprint is very similar to
a DIP-18 footprint and differs by only two pins in a highly-defined way,
yet the current implementation means two static, completely separate
geometry-data-files to represent nearly identical data.

*I'd like to develop a plug-in or add-on to KiCAD which introduces a completely new footprint paradigm; a much smaller and more efficient footprint solution than tens of thousands of static files - build footprints on-demand, from highly-optimized footprint formulae.*

* This can't break existing KiCAD workflows; this must be a *new* workflow.
* Instead of *assigning* a footprint file to a component, the user *builds* a footprint *for* the component, from industry-standard dimensions.
* The user may select options for these dimensions at build-time, such as pad size (minimal, normal, maximum), solder mask relief, etc.
* This eliminates the dreaded "I need this package with 22 pins, but only the 20 and 24-pin footprint is available" issue which always seems to happen.  No library can be infinitely-large; but a well-tuned generator could come close!

1. Back-end: instead of having each footprint as a separate file which the
user picks, instead lets optimize those down to formulae with threaded
parameters.  Then the user can select a footprint type (such as DIP or
SOIC), set the number of pins, pad size, relief, etc, and generate a .kicad-mod
file custom-made to their specifications.  This is going to
require *a lot of investigation and optimization.*
2. The entire existing footprint library is converted into this new
(condensed, formulaic) format.  We will find specification documents for
many of the standards, but some may have to be interpolated from spec
documents and the KiCAD library itself.
3. From there, we can extrapolate possible tweaks to each footprint, such
as "omit pin 13" or "."
4. In a perfect world, the new (formulaic) footprint generator would be
included in the KiCAD source itself, so could be upgraded on any KiCAD
upgrade.  If the old footprint library were eventually removed, the
release would shrink by 15,450 files and 156/181MB.
