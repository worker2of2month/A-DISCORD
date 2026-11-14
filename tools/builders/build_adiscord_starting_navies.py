"""Rebuild the shared naval sections without replacing country land armies."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.lib.adiscord_starting_navies import (
    STARTING_NAVIES,
    with_naval_history,
    with_starting_navy,
)
from tools.lib.paths import repository_root


ROOT = repository_root()


def outputs() -> dict[Path, bytes]:
    result = {}
    for tag in STARTING_NAVIES:
        histories = list((ROOT / "history/countries").glob(f"{tag} -*.txt"))
        if len(histories) != 1:
            raise ValueError(f"{tag}: expected one country history")
        path = histories[0]
        result[path] = with_naval_history(path.read_text(encoding="utf-8"), tag).encode("utf-8")
        path = ROOT / f"history/units/{tag}.txt"
        result[path] = with_starting_navy(path.read_text(encoding="utf-8"), tag).encode("utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    plan = outputs()
    changed = [path for path, data in plan.items() if path.read_bytes() != data]
    for path in changed:
        print(f"{'WRITE' if args.apply else 'STALE'} {path.relative_to(ROOT)}")
        if args.apply:
            path.write_bytes(plan[path])
    if args.apply and any(path.read_bytes() != data for path, data in outputs().items()):
        raise RuntimeError("Starting navies are not idempotent")
    print(f"Starting navy sections: {len(STARTING_NAVIES)} countries, {len(changed)} changed files.")
    return int(bool(changed) and not args.apply)


if __name__ == "__main__":
    raise SystemExit(main())
