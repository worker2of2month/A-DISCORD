"""Build the four infantry badge families through the land battalion atlas."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.builders import build_adiscord_battalion_icons as battalions

UNITS = ("territorial", "assault_infantry", "marine_infantry", "hazard_infantry")


def outputs(units=None):
    selected = UNITS if units is None else units
    return battalions.outputs({f"ADISCORD_{unit}" for unit in selected})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units', nargs='+', choices=tuple(UNITS))
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    generated = outputs(args.units)
    changed = [
        path for path, data in generated.items()
        if not path.exists() or path.read_bytes() != data
    ]
    if args.apply:
        for path in changed:
            path.write_bytes(generated[path])
    print(f"Infantry icon files {'updated' if args.apply else 'different'}: {len(changed)}")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
