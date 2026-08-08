"""Stable repository-path helpers for package modules and root-level facades.

``repository_root`` derives the root from this file's location, so it is
identical when imported as ``tools.lib.paths`` or as ``lib.paths`` by a tool
run directly from the legacy ``tools/`` directory.
"""

from __future__ import annotations

from pathlib import Path


def repository_root() -> Path:
    """Return the A-Discord repository root containing the ``tools`` directory."""
    return Path(__file__).resolve().parents[2]
