from dataclasses import dataclass, field

import yaml


@dataclass
class FamilyNode:
    name: str
    generator: str | None = None
    params: dict = field(default_factory=dict)
    variants: dict = field(default_factory=dict)
    default_width: str | None = None
    variant_param: str = "pin_count"
    children: dict = field(default_factory=dict)


def _build_node(name: str, data: dict) -> FamilyNode:
    node = FamilyNode(
        name=name,
        generator=data.get("generator"),
        params=data.get("params", {}),
        variants=data.get("variants", {}),
        default_width=data.get("default_width"),
        variant_param=data.get("variant_param", "pin_count"),
    )
    for child_name, child_data in data.get("children", {}).items():
        node.children[child_name] = _build_node(child_name, child_data)
    return node


def load_family_tree(path: str) -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return {name: _build_node(name, data) for name, data in raw.items()}
