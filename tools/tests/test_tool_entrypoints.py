"""Compatibility coverage for the evolving importable tools layout."""

from __future__ import annotations

import importlib
import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BUILDER_NAMES = (
    "build_adiscord_ainholm_mandate",
    "build_adiscord_doctrine_system",
    "build_adiscord_exclusion_zone_boundaries",
    "build_adiscord_inner_frontier_countries",
    "build_adiscord_map_buildings",
    "build_adiscord_new_states",
    "build_adiscord_northern_countries",
    "build_adiscord_outer_states",
    "build_adiscord_remainder_states",
    "build_adiscord_strategic_regions",
    "build_adiscord_technology_system",
    "build_adiscord_terrain_snow",
    "build_adiscord_val_operations_map",
    "build_adiscord_vorkerland_original_flags",
)

# These builders already expose a genuinely read-only default/check path.
# The remaining six are import-checked only until Task 5 adds explicit
# check/apply contracts; invoking their current default would rewrite output.
READ_ONLY_BUILDERS = (
    "build_adiscord_ainholm_mandate",
    "build_adiscord_exclusion_zone_boundaries",
    "build_adiscord_inner_frontier_countries",
    "build_adiscord_map_buildings",
    "build_adiscord_northern_countries",
    "build_adiscord_outer_states",
    "build_adiscord_remainder_states",
    "build_adiscord_terrain_snow",
)


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

    def test_builder_facades_match_package_modules(self) -> None:
        """Relocation must preserve every builder API and existing safe CLI."""
        # A facade that imports a different callable, a package module omitted
        # from the move, or a changed read-only CLI will fail this contract.
        for builder_name in BUILDER_NAMES:
            with self.subTest(builder=builder_name, contract="main"):
                implementation = importlib.import_module(f"tools.builders.{builder_name}")
                facade = importlib.import_module(f"tools.{builder_name}")
                self.assertIs(facade.main, implementation.main)

        for builder_name in READ_ONLY_BUILDERS:
            for arguments in (("--help",), ()):
                with self.subTest(builder=builder_name, arguments=arguments):
                    facade = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            str(REPOSITORY_ROOT / "tools" / f"{builder_name}.py"),
                            *arguments,
                        ],
                        cwd=REPOSITORY_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    package = subprocess.run(
                        [
                            sys.executable,
                            "-B",
                            "-m",
                            f"tools.builders.{builder_name}",
                            *arguments,
                        ],
                        cwd=REPOSITORY_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=60,
                    )
                    self.assertEqual(facade.returncode, package.returncode)
                    self.assertEqual(facade.stdout, package.stdout)
                    self.assertEqual(facade.stderr, package.stderr)
