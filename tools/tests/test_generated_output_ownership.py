"""Contracts for generated-output ownership and safe builder CLIs."""

from __future__ import annotations

import os
from collections import Counter
import json
import re
import subprocess
import sys
import tempfile
import unittest
from fnmatch import fnmatchcase
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.builders import build_adiscord_battalion_icons as battalion_icons
from tools.builders import build_adiscord_party_texticons as party_texticons
from tools.builders import build_adiscord_deployment_ui_assets as deployment_ui_assets
from tools.builders import (
    build_adiscord_intelligence_ui_assets as intelligence_ui_assets,
)
from tools.builders import build_adiscord_stp_regions_map as stp_regions_map
from tools.builders import build_adiscord_support_company_icons as support_company_icons
from tools.builders import build_adiscord_technology_ui_assets as technology_ui_assets
from tools.builders import build_adiscord_val_operations_map as val_operations_map
from tools.builders.build_adiscord_diplomacy_ui_assets import (
    expected_outputs as diplomacy_ui_asset_outputs,
)
from tools.builders.build_adiscord_resource_assets import (
    expected_outputs as resource_asset_outputs,
)
from tools.lib.generated_outputs import (
    load_registry,
    run_apply_pipeline,
    run_registered_command,
    snapshot_outputs,
    validated_sandbox_root,
)


ROOT = Path(__file__).resolve().parents[2]
REQUIRED_FAMILIES = {
    "debug_idea_catalogue",
    "ambient_audio",
    "battalion_icons",
    "azhar_palace",
    "isaiah_clock_tower",
    "coastal_geography",
    "ainholm_mandate",
    "decision_ui_assets",
    "deployment_ui_assets",
    "diplomacy_ui_assets",
    "western_diplomacy_assets",
    "west_influence_map",
    "event_ui_assets",
    "focus_ui_assets",
    "focus_trees",
    "superevent_music",
    "superevent_animation",
    "superevent_art",
    "event_pictures",
    "production_ui_assets",
    "doctrine_system",
    "exclusion_zone_boundaries",
    "inner_frontier_countries",
    "intelligence_ui_assets",
    "operation_art",
    "island_administration_icon",
    "ivn_geography",
    "logistics_ui_assets",
    "market_ui_assets",
    "minimap",
    "mon_geography",
    "map_buildings",
    "state_history",
    "starting_navies",
    "northern_countries",
    "outer_states",
    "party_texticons",
    "remainder_states",
    "resource_assets",
    "strategic_regions",
    "stp_regions_map",
    "vorkerland_capital_map",
    "nam_basin_map",
    "shl_furnace_map",
    "nam_piracy_map",
    "nam_naval_models",
    "southern_marines",
    "support_company_icons",
    "nam_oilfields",
    "nam_focus_icons",
    "nam_subject_flags",
    "factory_models",
    "map_facility_models",
    "stp_flags",
    "stp_portraits",
    "stp_party_ideologies",
    "ideology_icons",
    "startup_ui_assets",
    "trade_regions",
    "technology_system",
    "technology_screen_ui_assets",
    "technology_ui_assets",
    "terrain_snow",
    "val_operations_map",
    "val_flags",
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

    def test_support_company_textures_and_sprite_bindings_match_their_sources(self) -> None:
        expected = support_company_icons.outputs()
        designer = ROOT / support_company_icons.LARGE
        cross_box = (8, 3, 21, 18)
        with Image.open(designer / "support_unit_field_hospital_icon.dds") as hospital:
            cross = hospital.crop(cross_box)
            self.assertEqual(cross.getpixel((14 - cross_box[0], 9 - cross_box[1])), (141, 175, 255, 255))
        registered = {
            path
            for pattern in self.entries["support_company_icons"]["output_globs"]
            for path in ROOT.glob(pattern)
        }
        self.assertEqual(set(expected), registered)
        for path, content in expected.items():
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(path.read_bytes(), content)
                if path.parent == designer:
                    with Image.open(path) as strip:
                        self.assertEqual(strip.crop(cross_box).tobytes(), cross.tobytes())
                        self.assertIsNone(strip.getchannel("A").crop((21, 3, 23, 18)).getbbox())

    def test_battalion_counter_dimensions_and_ownership(self) -> None:
        expected = battalion_icons.outputs()
        owned = self.entries["battalion_icons"]["output_globs"]
        self.assertEqual({ROOT / path for path in owned}, set(expected))
        sizes = ((152, 42), (60, 12), (60, 12), (25, 12))
        for unit in battalion_icons.BATTALIONS:
            for path, size in zip(unit.paths(), sizes, strict=True):
                with self.subTest(unit=unit.unit, path=path):
                    self.assertEqual((ROOT / path).read_bytes(), expected[ROOT / path])
                    with Image.open(ROOT / path) as image:
                        self.assertEqual(image.size, size)
                        self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
                        if path.parent == battalion_icons.MAP or battalion_icons.MAP in path.parents:
                            red, green, blue, _ = image.split()
                            self.assertEqual(red.tobytes(), green.tobytes())
                            self.assertEqual(red.tobytes(), blue.tobytes())

    def test_designer_group_and_taran_aliases_load_the_same_art(self) -> None:
        large = ROOT / battalion_icons.LARGE
        self.assertEqual((large / "unit_art_icon.dds").read_bytes(),
                         (large / "ADISCORD_line_artillery_icon.dds").read_bytes())
        self.assertNotEqual((large / "unit_art_icon.dds").read_bytes(),
                            (large / "support_unit_art_icon.dds").read_bytes())
        for folder, filename in (
            (battalion_icons.LARGE, "STP_taran_icon.dds"),
            (battalion_icons.MAP, "STP_taran_icon.dds"),
            (battalion_icons.TEXT, "STP_taran_icon_small.dds"),
        ):
            with self.subTest(folder=folder):
                self.assertEqual((ROOT / folder / filename).read_bytes(),
                                 (ROOT / folder / "battalions" / filename).read_bytes())

    def test_every_land_unit_and_regiment_group_resolves_to_mod_art(self) -> None:
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.validators.validate_adiscord_strategic_resources_ui import BASE_GAME

        game = Path(os.environ.get("HOI4_GAME_DIR", BASE_GAME))
        if not (game / "interface/subuniticons.gfx").is_file():
            self.skipTest("Set HOI4_GAME_DIR to verify inherited sprite declarations")

        variants = {}
        groups = set()
        for path in (ROOT / "common/units").glob("*.txt"):
            for block in parse_clausewitz(path.read_text(encoding="utf-8-sig")):
                if block.key != "sub_units":
                    continue
                for unit in block.value:
                    fields = {field.key: field.value for field in unit.value}
                    if "group" not in fields and unit.key != "railway_gun":
                        continue
                    groups.update(field.value for field in fields.get("allowed_battalion_groups", []))
                    if fields.get("group") not in (None, "support"):
                        groups.add(fields["group"])
                    for suffix in ("medium", "medium_white", "small"):
                        variants[f"GFX_unit_{unit.key}_icon_{suffix}"] = 2
                    variants[f"GFX_nato_unit_{unit.key}_icon_small"] = 1
        self.assertIn("GFX_unit_infantry_icon_medium", variants)
        for group in groups:
            variants[f"GFX_group_{group}_icon"] = 2

        declarations = {}
        pattern = re.compile(r'\bspriteType\s*=\s*\{\s*name\s*=\s*"([^"]+)"([^{}]*)\}', re.I)
        native = game / "interface"
        local = ROOT / "interface"
        for directory in (native, local, local / "replace"):
            for path in sorted(directory.glob("*.gfx")):
                for match in pattern.finditer(path.read_text(encoding="utf-8-sig", errors="replace")):
                    if match[1] in variants:
                        declarations[match[1]] = match[2]
        owned = set(battalion_icons.outputs()) | set(support_company_icons.outputs())
        for name, frames in variants.items():
            with self.subTest(sprite=name):
                self.assertTrue(name in declarations, f"Missing sprite {name}")
                body = declarations[name]
                texture = re.search(r'\btexturefile\s*=\s*"([^"]+)"', body, re.I)
                frame_count = re.search(r'\bnoofframes\s*=\s*(\d+)', body, re.I)
                self.assertIsNotNone(texture)
                self.assertEqual(int(frame_count[1]) if frame_count else 1, frames)
                path = ROOT / texture[1]
                self.assertIn(path, owned)
                original = game / texture[1]
                if original.is_file():
                    self.assertNotEqual(path.read_bytes(), original.read_bytes())

    def test_stp_ideology_exports_do_not_require_a_temporary_preview(self) -> None:
        from tools.builders import build_adiscord_stp_party_ideologies as ideologies

        sources = set(self.entries["stp_party_ideologies"]["source_inputs"])
        for subtype in ideologies.LABELS:
            if subtype != "aristocratic_hedonism":
                self.assertIn((ideologies.SOURCE / f"{subtype}.png").as_posix(), sources)
        ordinary = dict(ideologies.outputs())
        self.assertNotIn(ideologies.PREVIEW, set(ordinary))
        preview = dict(ideologies.outputs(include_preview=True))
        self.assertEqual(set(preview), {*ordinary, ideologies.PREVIEW})
        self.assertEqual(
            set(self.entries["stp_party_ideologies"]["output_globs"]),
            {path.as_posix() for path in preview},
        )
        for path, data in ordinary.items():
            self.assertEqual(data, preview[path])

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

    def test_stp_focus_art_stays_outside_generated_outputs(self) -> None:
        patterns = self.entries["focus_ui_assets"]["authored_asset_exclusions"]
        for pattern in patterns:
            paths = list(ROOT.glob(pattern))
            self.assertTrue(paths, pattern)
            for path in paths:
                relative = path.relative_to(ROOT).as_posix()
                owners = [
                    entry["id"]
                    for entry in self.entries.values()
                    if any(fnmatchcase(relative, glob) for glob in entry["output_globs"])
                ]
                self.assertEqual(owners, [], relative)

    def test_focus_registry_covers_every_current_authored_output(self) -> None:
        from tools.builders.build_adiscord_focus_trees import SOURCES

        self.assertEqual(
            set(self.entries["focus_trees"]["output_globs"]),
            {f"common/national_focus/{name}" for name in SOURCES.values()},
        )

    def test_weapon_icon_registry_does_not_claim_other_technology_art(self) -> None:
        from tools.builders.build_adiscord_technology_icons import load_manifest

        declared = {
            path for path in self.entries["technology_ui_assets"]["output_globs"]
            if path.startswith("gfx/interface/technologies/")
        }
        self.assertEqual(
            declared,
            {f"gfx/interface/technologies/{spec.output}" for spec in load_manifest()},
        )
        self.assertTrue(
            {"map/buildings.txt", "history/states/*.txt"}
            <= set(self.entries["state_history"]["source_inputs"]),
        )

    def test_resource_asset_registry_owns_every_exact_generated_path_and_source(
        self,
    ) -> None:
        entry = self.entries["resource_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix() for path in resource_asset_outputs()
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertTrue(
            {
                "tools/assets/source/trade_gui/strategic_resources_source.png",
                "tools/assets/source/trade_gui/country_trade_entry_source.png",
                "tools/assets/source/trade_gui/topbar_glyphs_source.png",
                "tools/assets/source/trade_gui/topbar_indicators_source.png",
                "tools/assets/source/trade_gui/international_market_source.png",
                "tools/assets/source/trade_gui/command_power_phone_source.png",
                "tools/assets/source/trade_gui/topbar_background_extended_source.png",
                "tools/assets/source/economy_gui/treasury_topbar_source.png",
            }
            <= set(entry["source_inputs"])
        )

    def test_diplomacy_ui_asset_registry_owns_every_exact_generated_path_and_source(
        self,
    ) -> None:
        entry = self.entries["diplomacy_ui_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix() for path in diplomacy_ui_asset_outputs()
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertEqual(
            set(entry["source_inputs"]),
            {
                "tools/assets/source/diplomacy_gui/ADISCORD_diplomacy_leader_overlay_master.png",
                "tools/assets/source/diplomacy_gui/ADISCORD_diplomacy_parties_overlay_master.png",
                "tools/assets/source/diplomacy_gui/ADISCORD_diplomacy_flag_overlay_master.png",
                "gfx/interface/diplomacy/ADISCORD_diplomacy_focus_button.dds",
                "gfx/interface/decisions/ui/ADISCORD_decisions_item_bg.dds",
            },
        )

    def test_intelligence_ui_registry_exactly_matches_builder_outputs_and_sources(
        self,
    ) -> None:
        entry = self.entries["intelligence_ui_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for path in intelligence_ui_assets.expected_outputs(include_preview=True)
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertEqual(
            set(entry["source_inputs"]),
            {
                "tools/builders/build_adiscord_intelligence_ui_assets.py",
                "tools/lib/adiscord_ui_contracts.py",
                "tools/lib/adiscord_ui_surfaces.py",
                "tools/assets/source/production_gui/production_surface_source.png",
                "tools/assets/source/intelligence_gui/ADISCORD_intelligence_agent_cutout.png",
                "map/terrain.bmp",
            },
        )
        self.assertTrue(entry["may_delete_outputs"])

    def test_deployment_ui_registry_exactly_matches_builder_outputs_and_sources(
        self,
    ) -> None:
        entry = self.entries["deployment_ui_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for path in deployment_ui_assets.expected_outputs(include_preview=True)
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertEqual(
            set(entry["source_inputs"]),
            {
                "tools/builders/build_adiscord_deployment_ui_assets.py",
                "tools/lib/adiscord_ui_contracts.py",
                "tools/lib/adiscord_ui_surfaces.py",
                "tools/assets/source/production_gui/production_surface_source.png",
            },
        )
        self.assertTrue(entry["may_delete_outputs"])

    def test_technology_ui_registry_exactly_matches_builder_outputs_and_sources(
        self,
    ) -> None:
        entry = self.entries["technology_screen_ui_assets"]
        expected_paths = {
            path.relative_to(ROOT).as_posix()
            for path in technology_ui_assets.expected_outputs(include_preview=True)
        }
        self.assertEqual(set(entry["output_globs"]), expected_paths)
        self.assertTrue(all("*" not in path for path in entry["output_globs"]))
        self.assertEqual(
            set(entry["source_inputs"]),
            {
                "tools/builders/build_adiscord_technology_ui_assets.py",
                "tools/lib/adiscord_ui_contracts.py",
                "tools/lib/adiscord_ui_surfaces.py",
                "tools/assets/source/technology/technology_surface.png",
                "tools/assets/source/technology/folder_tabs.png",
            },
        )
        self.assertTrue(entry["may_delete_outputs"])

    def test_technology_system_registry_tracks_ui_skin_generation_dependencies(
        self,
    ) -> None:
        entry = self.entries["technology_system"]
        self.assertTrue(
            {
                "tools/builders/build_adiscord_technology_ui_assets.py",
                "tools/lib/adiscord_ui_contracts.py",
                "tools/lib/adiscord_ui_surfaces.py",
            }
            <= set(entry["source_inputs"]),
            "tree GUI/GFX generation imports the technology UI skin and helpers",
        )
        state_outputs = {
            "interface/zz_ADISCORD_technology_states.gfx",
            "gfx/interface/technology/ui/ADISCORD_technology_node_unavailable.dds",
            "gfx/interface/technology/ui/ADISCORD_technology_node_available.dds",
            "gfx/interface/technology/ui/ADISCORD_technology_node_researched.dds",
            "gfx/interface/technology/ui/ADISCORD_technology_node_branch.dds",
            "gfx/interface/technology/ui/ADISCORD_technology_node_researching.dds",
            "docs/development/previews/ADISCORD_technology_tree_preview.png",
        }
        self.assertTrue(
            state_outputs
            <= set(self.entries["technology_screen_ui_assets"]["output_globs"])
        )
        self.assertTrue(state_outputs.isdisjoint(entry["output_globs"]))
        for output in state_outputs:
            owners = {
                family_id
                for family_id, candidate in self.entries.items()
                if any(
                    fnmatchcase(output, pattern)
                    for pattern in candidate["output_globs"]
                )
            }
            self.assertEqual(owners, {"technology_screen_ui_assets"}, output)

    def test_party_texticon_registry_exactly_matches_assets_and_is_exclusive(
        self,
    ) -> None:
        entry = self.entries["party_texticons"]
        expected_outputs = [
            path.relative_to(ROOT).as_posix()
            for path in party_texticons.expected_outputs()
        ]
        expected_sources = [
            "tools/builders/build_adiscord_party_texticons.py",
            "tools/data/adiscord_party_texticons.json",
            *(
                asset.source.as_posix()
                for asset in party_texticons.ASSETS
                if asset.source is not None
            ),
            *(protected.output.as_posix() for protected in party_texticons.PROTECTED),
        ]
        self.assertEqual(entry["output_globs"], expected_outputs)
        self.assertEqual(entry["source_inputs"], expected_sources)
        self.assertEqual(self.registry["apply_sequence"].count("party_texticons"), 1)
        self.assertEqual(entry["ownership_mode"], "exclusive")

        for output in expected_outputs:
            owners = {
                family_id
                for family_id, candidate in self.entries.items()
                if any(
                    fnmatchcase(output, pattern)
                    for pattern in candidate["output_globs"]
                )
            }
            self.assertEqual(owners, {"party_texticons"}, output)

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

    def test_stp_regions_check_rejects_an_unexpected_owned_png(self) -> None:
        self.assertTrue(self.entries["stp_regions_map"]["may_delete_outputs"])
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            expected = Image.new("RGBA", (2, 2), (10, 20, 30, 255))
            outputs = {"STP_regions_state_1.png": expected}
            expected.save(output_dir / "STP_regions_state_1.png")
            Image.new("RGBA", (2, 2), (40, 50, 60, 255)).save(
                output_dir / "STP_regions_state_999.png"
            )

            with patch.object(stp_regions_map, "OUT", output_dir):
                issues = stp_regions_map.validate_outputs(outputs)

            self.assertIn("STP_regions_state_999.png", "\n".join(issues))

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
                source_inputs = (
                    [source_input] if isinstance(source_input, str) else source_input
                )
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
                                "{python}",
                                "-B",
                                "-m",
                                "tools.builders.build_fixture",
                            ],
                            "apply_command": [
                                "{python}",
                                "-B",
                                "-m",
                                "tools.builders.build_fixture",
                                "--apply",
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
                result = run_registered_command(
                    ROOT, entry["check_command"], timeout=300
                )
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
            result = run_registered_command(
                sandbox, entry["check_command"], timeout=300
            )
            self.assertEqual(
                result.returncode,
                0,
                f"post-apply check failed for {entry['id']}\n{result.stdout}{result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
