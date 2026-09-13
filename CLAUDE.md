# User-defined project goals

KiCAD dev website (reference): https://dev-docs.kicad.org/en/

Currently, KiCAD ships thousands of footprint files in their library, each
differing by various amounts, many nearly identical.  This is highly
inefficient and limiting, since if a footprint doesn't exist in the library,
one must be created manually.  Footprints are inherently classed; a DIP-16
footprint is very similar to a DIP-18 footprint and differs by only two pins
in a highly-defined way, yet the current implementation means two completely
separate geometry-files to represent nearly identical data.

I'd like to develop a plug-in or add-on to KiCAD which completely changes
the existing footprint paradigm, and offers a much smaller and more efficient
solution - build footprints on-demand, from a database/tree of condensed
footprint info.  If a user wants a desired footprint but it does not exist
yet, pick a similar one and define the changes from a series of questions.
This can't break existing KiCAD workflows; this must be a new workflow.

1. Back-end: instead of having each footprint as a separate file which the
user picks, instead lets build a database or tree of footprints, as text
specifiers, which inherit parent attributes.  This is going to require a
lot of investigation and optimization.  I'm not 100% sure how a specifier
would look yet, but perhaps something like 'DIP-16 r 0.1', where DIP
completely defines a dual-inline-package, 16 is the (variable) number of
pins, 'r' means regular-width (as opposed to narrow or wide), and 0.1 is
the pin spacing (perhaps superfluous for DIP, but a necessity for some of
the other footprint styles.)
2. The entire existing footprint library is converted into this new
(condensed, hierarchical-descriptor) format.  Now when the user wants to
assign a footprint, they use this tool to search for 'dip', find an exact
'dip-16' match, pick it, and the footprint geometry file is created
on-demand and assigned to the component.
3. The new (condensed, hierarchical-descriptor) footprint library
(concept title is 'kicad-fpdb' = footprint database) is a single file
which can be updated regularly.
4. Later milestone: this 'fpdb' must be field-updateable.  As users
generate new footprints, they are asked if they want to contribute their
new ones (once per year, or via an upload button.)  If the user agrees,
their new footprints are uploaded to a server, awaiting moderator review.
If a moderator approves them, they are added to the global database/tree,
and become available for everyone to automatically update to.

## Claude-isms below
