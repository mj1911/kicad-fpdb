# kicad-fpdb

🚧 Under construction... 🚧

Independent side projects exploring alternatives to KiCad's per-file
footprint library — build footprints on demand instead of picking from
thousands of near-duplicate static files:

* [`kicad-fpdb/`](kicad-fpdb/) — reverse-engineered from real KiCad
  library files: a descriptor language + family-tree YAML + shape
  generators, validated to match KiCad's own footprints exactly.  Was
  initally going to use just this, but decided to try a more algorthmic
  approach, where no footprint data was stored locally.  Was able to
  reduce file size by over 60x with a limited subset of footprints.
* [`jedec-fpdb/`](jedec-fpdb/) — the opposite approach: footprints
  generated purely from published JEDEC/IPC standards, independent of
  any real KiCad file.  This seems more capable than the previous.  Of
  course the default options will produce footprints very close to
  established KiCAD references.

See each subdirectory's own README for details.

Expect everything to change here, often, as we try to nail this down.
