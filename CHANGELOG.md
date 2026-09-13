# Changes

2026-09-13 v0.0.5:

* Updated CLAUDE.md's TODO list: removed the now-done outline-geometry
  item.
* Added generic courtyard (`F.CrtYd`) and silkscreen body outline
  (`F.SilkS`, with a pin-1 corner marker) geometry to generated
  footprints, built purely from the pad bounding box so it works the
  same way across all three generators. Not a per-family match to real
  KiCad's own outline styles — verified visually via the review tool,
  per the spec's stated approach.
