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


def _known_generators() -> set:
    # Deferred import: pipeline.py imports this module at load time, so a
    # top-level import here would be circular. By call time (after the
    # package has finished importing) this resolves fine either way, and
    # it keeps the generator name list defined in exactly one place
    # (pipeline.GENERATORS) instead of duplicating it here.
    from kicad_fpdb.pipeline import GENERATORS

    return set(GENERATORS)


def _validate_generators(roots: dict) -> None:
    known = _known_generators()

    def walk(node: FamilyNode):
        if node.generator is not None and node.generator not in known:
            raise ValueError(
                f"family {node.name!r} references unknown generator "
                f"{node.generator!r}; known generators: {sorted(known)}"
            )
        for child in node.children.values():
            walk(child)

    for root in roots.values():
        walk(root)


def load_family_tree(path: str) -> dict:
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    roots = {name: _build_node(name, data) for name, data in raw.items()}
    _validate_generators(roots)
    return roots


@dataclass
class ResolvedFootprint:
    generator: str
    params: dict


def _find_chain(roots: dict, target_name: str):
    def search(node: FamilyNode, chain: list):
        chain = chain + [node]
        if node.name == target_name:
            return chain
        for child in node.children.values():
            found = search(child, chain)
            if found:
                return found
        return None

    for root in roots.values():
        found = search(root, [])
        if found:
            return found
    return None


def _merge_params(chain: list) -> dict:
    merged: dict = {}
    for node in chain:
        for key, value in node.params.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
    return merged


def _resolve_meta(chain: list, attr: str, default):
    value = default
    for node in chain:
        candidate = getattr(node, attr)
        if candidate:
            value = candidate
    return value


def resolve_descriptor(roots: dict, parsed) -> ResolvedFootprint:
    full_name = f"{parsed.family}-{parsed.variant}"
    chain = _find_chain(roots, full_name)
    inject_variant = chain is None
    if chain is None:
        chain = _find_chain(roots, parsed.family)
    if chain is None:
        raise KeyError(f"unknown family {parsed.family!r}")

    params = _merge_params(chain)
    variants = _resolve_meta(chain, "variants", {})
    default_width = _resolve_meta(chain, "default_width", None)
    variant_param = _resolve_meta(chain, "variant_param", "pin_count")
    generator = _resolve_meta(chain, "generator", None)
    if generator is None:
        raise ValueError(f"no generator defined for family {parsed.family!r}")

    width_name = default_width
    for token in parsed.modifier_tokens:
        if token in variants:
            width_name = variants[token]
        else:
            try:
                params["pitch"] = float(token)
            except ValueError:
                raise ValueError(f"unknown modifier {token!r} for family {parsed.family!r}")

    resolved_params = {}
    for key, value in params.items():
        if isinstance(value, dict):
            if width_name is None:
                raise ValueError(f"family {parsed.family!r} requires a width modifier for {key!r}")
            resolved_params[key] = value[width_name]
        else:
            resolved_params[key] = value

    if inject_variant and variant_param:
        variant_token = parsed.variant
        resolved_params[variant_param] = int(variant_token) if variant_token.isdigit() else variant_token

    return ResolvedFootprint(generator=generator, params=resolved_params)
