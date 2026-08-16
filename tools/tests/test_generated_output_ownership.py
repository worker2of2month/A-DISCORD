"""Contracts for generated-output ownership and safe builder CLIs."""

from __future__ import annotations

import os
from collections import Counter
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_val_operations_map as val_operations_map
from tools.builders.build_adiscord_diplomacy_ui_assets import expected_outputs as diplomacy_ui_asset_outputs
from tools.builders.build_adiscord_resource_assets import expected_outputs as resource_asset_outputs
from tools.lib.generated_outputs import (
    load_registry,
    run_apply_pipeline,
    run_registered_command,
    snapshot_outputs,
    validated_sandbox_root,
)


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FAMILIES = {
    "ainholm_mandate",
    "decision_ui_assets",
    "diplomacy_ui_assets",
    "production_ui_assets",
    "doctrine_system",
    "exclusion_zone_boundaries",
    "inner_frontier_countries",
    "island_administration_icon",
    "ivn_geography",
    "minimap",
    "map_buildings",
    "state_history",
    "northern_countries",
    "outer_states",
    "remainder_states",
    "resource_assets",
    "strategic_regions",
    "trade_regions",
    "technology_system",
    "technology_ui_assets",
    "terrain_snow",
    "val_operations_map",
    "vorkerland_flags",
    "vorkerland_cities",
    "vorkerland_theatre",
}


class GeneratedOutputOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(ROOT)
        cls.entries = {entry["id"]: entry for entry in cls.registry["families"]}

    def test_registry_covers_every_mutating_builder_and_required_family(self) -> None:
        builder_modules = {
            f"tools.builders.{path.stem}"
            for path in (ROOT / "tools" / "builders").glob("build_*.py")
        }
        registered_modules = {entry["owner_module"] for entry in self.entries.values()}
        self.assertEqual(set(self.entries), REQUIRED_FAMILIES)
        self.assertEqual(registered_modules, builder_modules)

        for entry in self.entries.values():
            with self.subTest(family=entry["id"]):
                self.assertTrue(entry["output_globs"])
                self.assertTrue(entry["source_inputs"])
                self.assertIsInstance(entry["may_delete_outputs"], bool)
                self.assertEqual(
                    entry["check_command"],
                    ["{python}", "-B", "-m", entry["owner_module"]],
                )
                self.assertEqual(entry["apply_command"][-1], "--apply")

        self.assertTrue(
            {
                "gfx/flags/WRK.tga",
                "gfx/flags/medium/WRK.tga",
                "gfx/flags/small/WRK.tga",
            }
            <= set(self.entries["vorkerland_flags"]["source_inputs"]),
            "copied joint-government flags depend on all three base WRK TGA inputs",
        )

    def test_registry_declares_every_builder_that_writes_map_buildings(self) -> None:
        declared_owners = {
            entry["id"]
            for entry in self.entries.values()
            if "map/buildings.txt" in entry["output_globs"]
        }
        self.assertEqual(
            declared_owners,
            {"map_buildings", "outer_states", "remainder_states", "state_history"},
        )
        self.assertTrue(
            {"map/buildings.txt", "history/states/*.txt"}
            <= set(self.entries["state_history"]["source_inputs"]),
        )

    def test_resource_asset_registry_owns_every_exact_generated_path_and_source(self) -> None:
        entry = self.entries["resource_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for path in resource_asset_outputs()
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertTrue(
            {
                "gfx/interface/ADISCORD_trade_gui/source/strategic_resources_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/country_trade_entry_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/topbar_glyphs_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/topbar_indicators_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/international_market_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/command_power_phone_source.png",
                "gfx/interface/ADISCORD_trade_gui/source/topbar_background_extended_source.png",
                "gfx/interface/ADISCORD_economy_gui/source/treasury_topbar_source.png",
            }
            <= set(entry["source_inputs"])
        )

    def test_diplomacy_ui_asset_registry_owns_every_exact_generated_path_and_source(self) -> None:
        entry = self.entries["diplomacy_ui_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for path in diplomacy_ui_asset_outputs()
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertEqual(
            set(entry["source_inputs"]),
            {
                "gfx/interface/diplomacy/source/ADISCORD_diplomacy_leader_overlay_master.png",
                "gfx/interface/diplomacy/source/ADISCORD_diplomacy_parties_overlay_master.png",
                "gfx/interface/diplomacy/source/ADISCORD_diplomacy_flag_overlay_master.png",
            },
        )

    def test_val_check_rejects_an_unexpected_owned_png(self) -> None:
        self.assertTrue(self.entries["val_operations_map"]["may_delete_outputs"])
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            expected = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
            outputs = {"VAL_ops_expected.png": expected}
            expected.save(output_dir / "VAL_ops_expected.png")
            Image.new("RGBA", (2, 2), (40, 50, 60, 255)).save(
                output_dir / "VAL_ops_stale.png"
            )

            with patch.object(val_operations_map, "OUT", output_dir):
                issues = val_operations_map.validate_outputs(outputs)

            self.assertIn("VAL_ops_stale.png", "\n".join(issues))

    def test_val_apply_removes_only_unexpected_owned_pngs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            expected = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
            outputs = {"VAL_ops_expected.png": expected}
            expected.save(output_dir / "VAL_ops_expected.png")
            Image.new("RGBA", (2, 2), (40, 50, 60, 255)).save(
                output_dir / "VAL_ops_stale.png"
            )
            unrelated = output_dir / "unrelated.png"
            Image.new("RGBA", (2, 2), (70, 80, 90, 255)).save(unrelated)
            unrelated_before = unrelated.read_bytes()

            with patch.object(val_operations_map, "OUT", output_dir):
                val_operations_map.apply(outputs)

            self.assertTrue((output_dir / "VAL_ops_expected.png").is_file())
            self.assertFalse((output_dir / "VAL_ops_stale.png").exists())
            self.assertEqual(unrelated.read_bytes(), unrelated_before)

    def test_pipeline_is_explicit_and_repeats_northern_after_exclusion(self) -> None:
        sequence = self.registry["apply_sequence"]
        self.assertEqual(set(sequence), set(self.entries))
        expected_counts = Counter({family_id: 1 for family_id in self.entries})
        expected_counts["northern_countries"] = 2
        self.assertEqual(Counter(sequence), expected_counts)
        first_northern = sequence.index("northern_countries")
        exclusion = sequence.index("exclusion_zone_boundaries")
        second_northern = sequence.index("northern_countries", first_northern + 1)
        self.assertLess(first_northern, exclusion)
        self.assertLess(exclusion, second_northern)
        self.assertLess(
            sequence.index("technology_system"),
            sequence.index("doctrine_system"),
            "technology localisation must be generated before doctrine removes migrated keys",
        )
        self.assertLess(
            sequence.index("ivn_geography"),
            sequence.index("map_buildings"),
        )

    def test_registry_rejects_unsafe_or_empty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "tools" / "data").mkdir(parents=True)
            (root / "inputs").mkdir()
            (root / "generated").mkdir()
            (root / "inputs" / "source.txt").write_text("source", encoding="utf-8")
            (root / "generated" / "out.txt").write_text("output", encoding="utf-8")
            registry_path = root / "tools" / "data" / "generated_output_owners.json"

            def write_registry(output_glob: str, source_input: str | list[str]) -> None:
                source_inputs = [source_input] if isinstance(source_input, str) else source_input
                payload = {
                    "schema": 1,
                    "apply_sequence": ["fixture"],
                    "families": [
                        {
                            "id": "fixture",
                            "owner_module": "tools.builders.build_fixture",
                            "output_globs": [output_glob],
                            "source_inputs": source_inputs,
                            "check_command": [
                                "{python}", "-B", "-m", "tools.builders.build_fixture"
                            ],
                            "apply_command": [
                                "{python}", "-B", "-m", "tools.builders.build_fixture", "--apply"
                            ],
                            "may_delete_outputs": False,
                            "ownership_mode": "exclusive",
                        }
                    ],
                }
                registry_path.write_text(json.dumps(payload), encoding="utf-8")

            for unsafe in ("../outside.txt", str((root / "absolute.txt").resolve())):
                with self.subTest(kind="unsafe-output", pattern=unsafe):
                    write_registry(unsafe, "inputs/source.txt")
                    with self.assertRaisesRegex(ValueError, "relative"):
                        load_registry(root)

            write_registry("generated/missing.txt", "inputs/source.txt")
            with self.assertRaisesRegex(ValueError, "output_globs.*materialize"):
                load_registry(root)

            write_registry("generated/out.txt", "inputs/missing.txt")
            with self.assertRaisesRegex(ValueError, "source_inputs.*materialize"):
                load_registry(root)

            write_registry(
                "generated/out.txt",
                ["inputs/source.txt", "inputs/missing.txt"],
            )
            with self.assertRaisesRegex(
                ValueError,
                r"fixture: source_inputs pattern inputs/missing\.txt must materialize",
            ):
                load_registry(root)

    def test_snapshot_and_sandbox_cannot_escape_their_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "sandbox"
            root.mkdir()
            (base / "outside.txt").write_text("outside", encoding="utf-8")
            registry = {"families": [{"output_globs": ["../outside.txt"]}]}
            with self.assertRaisesRegex(ValueError, "escapes repository root"):
                snapshot_outputs(root, registry)

        for candidate in (ROOT, ROOT / "tools", ROOT.parent):
            with self.subTest(candidate=candidate):
                with self.assertRaisesRegex(ValueError, "authoritative"):
                    validated_sandbox_root(candidate, authoritative_root=ROOT)

    def test_default_checks_and_help_are_non_mutating(self) -> None:
        before = snapshot_outputs(ROOT, self.registry)
        for entry in self.entries.values():
            with self.subTest(family=entry["id"], command="check"):
                result = run_registered_command(ROOT, entry["check_command"], timeout=300)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with self.subTest(family=entry["id"], command="help"):
                result = subprocess.run(
                    [sys.executable, "-B", "-m", entry["owner_module"], "--help"],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("--check", result.stdout)
                self.assertIn("--apply", result.stdout)
        self.assertEqual(snapshot_outputs(ROOT, self.registry), before)

    @unittest.skipUnless(
        os.environ.get("ADISCORD_GENERATOR_SANDBOX"),
        "full apply idempotence requires an explicit disposable full-repo sandbox",
    )
    def test_full_apply_pipeline_is_idempotent(self) -> None:
        sandbox = validated_sandbox_root(
            os.environ["ADISCORD_GENERATOR_SANDBOX"],
            authoritative_root=ROOT,
        )
        registry = load_registry(sandbox)
        run_apply_pipeline(sandbox, registry, timeout=900)
        first = snapshot_outputs(sandbox, registry)
        run_apply_pipeline(sandbox, registry, timeout=900)
        second = snapshot_outputs(sandbox, registry)
        self.assertEqual(second, first)
        for entry in registry["families"]:
            result = run_registered_command(sandbox, entry["check_command"], timeout=300)
            self.assertEqual(
                result.returncode,
                0,
                f"post-apply check failed for {entry['id']}\n{result.stdout}{result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
