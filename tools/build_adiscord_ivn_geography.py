"""Compatibility facade for the Ivanland geography builder."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.builders.build_adiscord_ivn_geography import main


if __name__ == "__main__":
    raise SystemExit(main())
