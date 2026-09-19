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
    # Modifier tokens (e.g. "socket") that aren't a width class -- each
    # maps to a flat dict of param overrides merged in when the token
    # appears in the descriptor, e.g. "DIP-14 socket". Distinct from
    # `variants` (which pick a width class rather than override params)
    # so a family can offer both kinds of token without collision.
    modifiers: dict = field(default_factory=dict)
    children: dict = field(default_factory=dict)


def _build_node(name: str, data: dict) -> FamilyNode:
    node = FamilyNode(
        name=name,
        generator=data.get("generator"),
        params=data.get("params", {}),
        variants=data.get("variants", {}),
        default_width=data.get("default_width"),
        variant_param=data.get("variant_param", "pin_count"),
        modifiers=data.get("modifiers", {}),
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
    # Non-width modifier tokens actually applied (e.g. ["socket"]) --
    # exposed so naming.descriptive_suffix can append a matching
    # real-KiCad-style suffix (e.g. "_Socket") after the dimension part,
    # distinct from width tokens (r/w/x/u/...), which are dropped
    # entirely since the dimension suffix already encodes them.
    applied_modifiers: list = field(default_factory=list)


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


def _deep_merge_into(merged: dict, overrides: dict) -> None:
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value


def _merge_params(chain: list) -> dict:
    merged: dict = {}
    for node in chain:
        _deep_merge_into(merged, node.params)
    return merged


def _merge_modifiers(chain: list) -> dict:
    merged: dict = {}
    for node in chain:
        merged.update(node.modifiers)
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
    modifiers = _merge_modifiers(chain)
    default_width = _resolve_meta(chain, "default_width", None)
    variant_param = _resolve_meta(chain, "variant_param", "pin_count")
    generator = _resolve_meta(chain, "generator", None)
    if generator is None:
        raise ValueError(f"no generator defined for family {parsed.family!r}")

    width_name = default_width
    applied_modifiers = []
    active_tokens = set(parsed.modifier_tokens)
    for token in parsed.modifier_tokens:
        if token in variants:
            width_name = variants[token]
        elif token in modifiers:
            # Deep-merge (not a flat overwrite): a modifier like
            # "longpads" only overrides some width-class keys of a
            # dict-valued param (e.g. body_width), so the width classes
            # it doesn't mention must survive untouched -- same
            # semantics as _merge_params' own chain merging.
            modifier_def = dict(modifiers[token])
            # A reserved "_with" key holds combo-specific overrides,
            # keyed by another modifier token: applied in addition
            # (order-independent -- checked against the full active-
            # token set, not sequential application) when that other
            # token is also present. E.g. real KiCad's Socket+LongPads
            # combo needs a distinct socket_margin_x (1.44mm) from
            # Socket alone (1.33mm), since a real socket's silk margin
            # is measured from the pin center but happens to differ
            # slightly once LongPads' wider pad is chosen.
            combo_overrides = modifier_def.pop("_with", {})
            _deep_merge_into(params, modifier_def)
            for other_token, extra in combo_overrides.items():
                if other_token in active_tokens:
                    _deep_merge_into(params, extra)
            applied_modifiers.append(token)
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

    return ResolvedFootprint(generator=generator, params=resolved_params, applied_modifiers=applied_modifiers)
