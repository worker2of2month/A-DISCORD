"""Export native-sized office tiers without redrawing the shared base icon."""

import argparse
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--check", action="store_true")
    actions.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    script = Path(__file__).with_suffix(".ps1")
    return subprocess.run([
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script),
        "-Apply" if args.apply else "-Check",
    ], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
