from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.geometry import Text, pad_bounding_box
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
}

# Margin, in mm, between the pad bounding box and the Reference/Value text
# placed above/below it. Generic default until real silkscreen/courtyard
# geometry exists to anchor text to instead.
TEXT_MARGIN_MM = 1.0


def _add_reference_and_value_text(geometry, name: str) -> None:
    min_x, min_y, max_x, max_y = pad_bounding_box(geometry.pads)
    center_x = (min_x + max_x) / 2
    geometry.texts.append(
        Text(kind="reference", text="REF**", at=(center_x, min_y - TEXT_MARGIN_MM), layer="F.SilkS")
    )
    geometry.texts.append(
        Text(kind="value", text=name, at=(center_x, max_y + TEXT_MARGIN_MM), layer="F.Fab")
    )


def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**resolved.params)
    geometry.name = name
    _add_reference_and_value_text(geometry, name)

    return write_kicad_mod(name, geometry)
