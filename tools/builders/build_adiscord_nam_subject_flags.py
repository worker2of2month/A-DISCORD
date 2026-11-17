"""Keep NAM subject regime flags identical to their authored district heraldry."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAGS = ("EFL", "AZH", "RHM", "SDR", "KDR")
STYLES = (
    "governorate",
    "military_district",
    "service_district",
    "concession",
    "treaty_republic",
    "directorate",
    "imperial_governorate",
)
FOLDERS = ("", "medium", "small")


def expected_outputs() -> dict[Path, bytes]:
    outputs = {}
    for tag in TAGS:
        for folder in FOLDERS:
            flags = ROOT / "gfx/flags" / folder
            data = (flags / f"{tag}_NAM_federal_district.tga").read_bytes()
            for style in STYLES:
                outputs[flags / f"{tag}_NAM_subject_{style}.tga"] = data
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    outputs = expected_outputs()
    changed = [path for path, data in outputs.items()
               if not path.is_file() or path.read_bytes() != data]
    if args.apply:
        for path in changed:
            path.write_bytes(outputs[path])
    print(f"NAM subject flags: {len(outputs)} textures, {len(changed)} "
          f"{'updated' if args.apply else 'pending'}.")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
