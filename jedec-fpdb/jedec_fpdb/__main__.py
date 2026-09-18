"""CLI entry point: `python -m jedec_fpdb <width_class> <pin_count> [--density M|N|L] [--out PATH]`."""

import argparse
import sys
from pathlib import Path

from jedec_fpdb import dip, writer


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jedec_fpdb")
    parser.add_argument("width_class", choices=dip.SUPPORTED_WIDTH_CLASSES)
    parser.add_argument("pin_count", type=int)
    parser.add_argument("--density", choices=("M", "N", "L"), default="N")
    parser.add_argument("--out", type=Path, default=None,
                         help="output .kicad_mod path (default: <name>.kicad_mod in cwd)")
    args = parser.parse_args(argv)

    footprint = dip.generate(args.width_class, args.pin_count, args.density)
    out_path = args.out or Path(f"{footprint.name}.kicad_mod")
    writer.write_footprint(footprint, out_path)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
