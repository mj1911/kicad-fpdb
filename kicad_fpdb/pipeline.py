from kicad_fpdb.descriptor import parse_descriptor
from kicad_fpdb.family_tree import load_family_tree, resolve_descriptor
from kicad_fpdb.generators.dual_row import dual_row_grid
from kicad_fpdb.generators.quad_perimeter import quad_perimeter
from kicad_fpdb.generators.two_pad import two_pad_chip
from kicad_fpdb.writer import write_kicad_mod

GENERATORS = {
    "dual_row_grid": dual_row_grid,
    "two_pad_chip": two_pad_chip,
    "quad_perimeter": quad_perimeter,
}


def generate_footprint(descriptor_text: str, family_tree_path: str, name: str) -> str:
    tree = load_family_tree(family_tree_path)
    parsed = parse_descriptor(descriptor_text)
    resolved = resolve_descriptor(tree, parsed)

    generator_fn = GENERATORS[resolved.generator]
    geometry = generator_fn(**resolved.params)
    geometry.name = name

    return write_kicad_mod(name, geometry)
