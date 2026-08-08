"""Compatibility coverage for the evolving importable tools layout."""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class ToolEntrypointCompatibilityTests(unittest.TestCase):
    def test_importable_tool_packages_keep_existing_root_clis_available(self) -> None:
        """Moving a tool must not break package imports or read-only root CLIs."""
        # This catches a missing package marker, an incorrect shared-root calculation,
        # or a root-level facade that is no longer directly executable.
        for package_name in ("tools.builders", "tools.validators", "tools.tests", "tools.lib"):
            with self.subTest(package=package_name):
                self.assertIsNotNone(importlib.import_module(package_name))

        paths = importlib.import_module("tools.lib.paths")
        self.assertEqual(paths.repository_root(), REPOSITORY_ROOT)

        for script_name in (
            "build_adiscord_map_buildings.py",
            "validate_tc.py",
        ):
            with self.subTest(script=script_name):
                result = subprocess.run(
                    [sys.executable, str(REPOSITORY_ROOT / "tools" / script_name), "--help"],
                    cwd=REPOSITORY_ROOT,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
