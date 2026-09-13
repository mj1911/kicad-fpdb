from dataclasses import dataclass, field


@dataclass
class ParsedDescriptor:
    family: str
    variant: str
    modifier_tokens: list[str] = field(default_factory=list)


def parse_descriptor(text: str) -> ParsedDescriptor:
    tokens = text.split()
    if not tokens:
        raise ValueError("descriptor must not be empty")

    head, *modifier_tokens = tokens
    if "-" not in head:
        raise ValueError(f"descriptor must start with FAMILY-VARIANT, got {head!r}")

    family, variant = head.split("-", 1)
    if not family or not variant:
        raise ValueError(f"descriptor must start with FAMILY-VARIANT, got {head!r}")

    return ParsedDescriptor(family=family, variant=variant, modifier_tokens=modifier_tokens)
