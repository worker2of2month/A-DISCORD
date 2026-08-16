"""Compatibility facade for the island-administration asset builder."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.builders.build_adiscord_island_administration_icon import main


if __name__ == "__main__":
    raise SystemExit(main())
