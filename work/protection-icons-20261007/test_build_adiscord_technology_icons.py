from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tools" / "data" / "adiscord_technology_weapon_icons.json"
SOURCE_DIR = ROOT / "tools" / "assets" / "source" / "technology_weapons"
FACADE = ROOT / "tools" / "build_adiscord_technology_icons.py"


class ShabratUniformAssetTests(unittest.TestCase):
    def test_shabrat_family_builds_only_three_current_transparent_cards(self):
        from tools.builders import build_adiscord_technology_icons as builder

        outputs = builder.render_outputs(ROOT, "service_STS")
        self.assertEqual(set(outputs), {
            Path(f"gfx/interface/technologies/ADISCORD_STS_weapon_{kind}.dds")
            for kind in ("01_reclaimed_arsenal", "02_recovered_service_rifle", "03_standardized_battle_rifle")
        })
        self.assertEqual(outputs, builder.render_outputs(ROOT, "service_STS"))
        specs = {
            spec.output: spec for spec in builder.load_manifest(MANIFEST)
            if spec.family == "service_STS"
        }
        for relative, content in outputs.items():
            self.assertEqual((ROOT / relative).read_bytes(), content)
            with Image.open(BytesIO(content)) as icon:
                self.assertEqual(icon.format, "DDS")
                self.assertEqual(icon.size, (176, 72))
                self.assertEqual(icon.getchannel("A").getextrema(), (0, 255))
                with Image.open(SOURCE_DIR / specs[relative.name].source) as source:
                    self.assertEqual(icon.convert("RGBA").tobytes(), source.tobytes())

    def test_family_apply_preserves_unrelated_connector_files(self):
        from tools.builders import build_adiscord_technology_icons as builder

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            connector = root / builder.DEPRECATED_CONNECTOR_OUTPUTS[0]
            connector.parent.mkdir(parents=True)
            connector.write_bytes(b"unrelated artwork")
            builder.apply({Path("new.dds"): b"new artwork"}, root, clean_connectors=False)
            self.assertEqual(connector.read_bytes(), b"unrelated artwork")
            self.assertEqual((root / "new.dds").read_bytes(), b"new artwork")


class TechnologyIconSourceTests(unittest.TestCase):
    def test_manifest_has_unique_ranked_weapon_sources(self) -> None:
        self.assertTrue(MANIFEST.is_file(), MANIFEST)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        icons = manifest["icons"]
        wide = [
            entry
            for entry in icons
            if entry["kind"] == "wide" and entry.get("family", "service") == "service"
        ]

        self.assertEqual([entry["tier"] for entry in wide], list(range(1, 10)))
        self.assertEqual(len({entry["key"] for entry in icons}), len(icons))
        self.assertEqual(len({entry["source"] for entry in wide}), 9)
        self.assertEqual(len(wide), 9)

    def test_manifest_has_nine_ranked_squad_weapon_sources(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        squad = [entry for entry in manifest["icons"] if entry.get("family") == "squad"]

        self.assertEqual([entry["tier"] for entry in squad], list(range(1, 10)))
        self.assertEqual(len({entry["source"] for entry in squad}), 9)
        self.assertTrue(all(entry["kind"] == "wide" for entry in squad))

    def test_regional_uniform_sets_cover_every_service_weapon(self) -> None:
        icons = json.loads(MANIFEST.read_text(encoding="utf-8"))["icons"]
        default = [
            entry
            for entry in icons
            if entry["kind"] == "wide" and entry.get("family", "service") == "service"
        ]
        for tag in ("STP", "VAL"):
            regional = [
                entry for entry in icons if entry.get("family") == f"service_{tag}"
            ]
            with self.subTest(country=tag):
                self.assertEqual(
                    [entry["tier"] for entry in regional], list(range(1, 10))
                )
                self.assertEqual(len({entry["source"] for entry in regional}), 9)
                self.assertEqual(
                    [entry["output"] for entry in regional],
                    [
                        entry["output"].replace("ADISCORD_", f"ADISCORD_{tag}_", 1)
                        for entry in default
                    ],
                )
                self.assertTrue(all(entry["kind"] == "wide" for entry in regional))

    def test_infantry_equipment_has_twenty_distinct_compact_icons(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        equipment = [
            entry for entry in manifest["icons"] if entry.get("family") == "equipment"
        ]
        self.assertEqual(len(equipment), 20)
        self.assertEqual(len({entry["output"] for entry in equipment}), 20)
        self.assertTrue(all(entry["kind"] == "compact" for entry in equipment))

    def test_manifest_sources_preserve_rgba_geometry_and_hashes(self) -> None:
        self.assertTrue(MANIFEST.is_file(), MANIFEST)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

        for entry in manifest["icons"]:
            source = SOURCE_DIR / entry["source"]
            self.assertTrue(source.is_file(), source)
            self.assertRegex(entry["source_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(), entry["source_sha256"]
            )
            with Image.open(source) as image:
                self.assertEqual(
                    image.size, tuple(entry.get("source_size", (1893, 831)))
                )
                self.assertEqual(image.mode, "RGBA")

    def test_night_icons_preserve_selected_runtime_artwork(self) -> None:
        from tools.builders import build_adiscord_technology_icons as builder

        specs = [spec for spec in builder.load_manifest() if spec.family == "night"]
        self.assertEqual(
            {spec.source for spec in specs},
            {f"night_{number:02}.png" for number in range(1, 5)},
        )
        outputs = builder.render_outputs(ROOT, "night")
        self.assertEqual(len(outputs), 6)
        for spec in specs:
            with self.subTest(icon=spec.key):
                self.assertTrue(spec.runtime_master)
                self.assertIsNone(spec.crop)
                path = Path("gfx/interface/technologies") / spec.output
                with Image.open(SOURCE_DIR / spec.source) as source:
                    with Image.open(BytesIO(outputs[path])) as icon:
                        self.assertEqual(icon.size, (72, 72))
                        self.assertEqual(icon.crop((1, 1, 71, 71)).tobytes(), source.tobytes())
                        alpha = icon.getchannel("A")
                        for border in ((0, 0, 72, 1), (0, 71, 72, 72),
                                       (0, 0, 1, 72), (71, 0, 72, 72)):
                            self.assertEqual(alpha.crop(border).getextrema(), (0, 0))

    def test_night_technology_sprites_resolve_to_selected_artwork(self) -> None:
        from tools.builders import build_adiscord_technology_system as generator

        branch = next(branch for branch in generator.BRANCHES if branch.key == "night_combat")
        expected = {
            "passive_intensifier_cells": "ADISCORD_night_01_passive_intensifier",
            "sealed_night_mounts": "ADISCORD_night_01_passive_intensifier",
            "fused_low_light_sights": "ADISCORD_night_01_passive_intensifier",
            "nocturnal_sensor_discipline": "ADISCORD_night_01_passive_intensifier",
            "thermal_observation_channels": "ADISCORD_night_02_thermal_channel",
            "thermal_target_libraries": "ADISCORD_night_02_thermal_channel",
            "low_signature_illumination": "ADISCORD_night_05_counter_illumination",
            "counter_illumination_warnings": "ADISCORD_night_05_counter_illumination",
            "squad_target_sharing": "ADISCORD_night_04_squad_target_sharing",
            "distributed_night_engagements": "ADISCORD_night_04_squad_target_sharing",
            "nocturnal_combat_mesh": "ADISCORD_night_04_squad_target_sharing",
        }
        gfx = (ROOT / "interface/ADISCORD_technologies.gfx").read_text(encoding="utf-8")
        for index, tech in enumerate(branch.techs):
            if tech.key not in expected:
                continue
            icon = expected[tech.key]
            with self.subTest(technology=tech.key):
                self.assertEqual(generator.icon_for_technology(branch, index), icon)
                sprite = gfx.split(f'name = "GFX_{tech.id}_medium"', 1)[1].split("}", 1)[0]
                self.assertIn(f'textureFile = "gfx/interface/technologies/{icon}.dds"', sprite)
                self.assertTrue((ROOT / f"gfx/interface/technologies/{icon}.dds").is_file())

    def test_manifest_has_twelve_ranked_personal_antitank_icons(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        antitank = [
            entry
            for entry in manifest["icons"]
            if entry.get("family") == "personal_antitank"
        ]

        self.assertEqual([entry["tier"] for entry in antitank], list(range(1, 13)))
        self.assertEqual(len({entry["key"] for entry in antitank}), 12)
        self.assertEqual(len({entry["output"] for entry in antitank}), 12)
        self.assertEqual(len({entry["source"] for entry in antitank}), 12)
        self.assertTrue(all(entry["kind"] == "compact" for entry in antitank))
        self.assertTrue(
            all(len(entry["crop"]) == 4 for entry in antitank if entry["tier"] == 6)
        )
        self.assertTrue(
            all("crop" not in entry for entry in antitank if entry["tier"] != 6)
        )

    def test_redrawn_personal_antitank_icons_use_individual_sources(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        antitank = {
            entry["tier"]: entry
            for entry in manifest["icons"]
            if entry.get("family") == "personal_antitank"
        }

        self.assertEqual(
            {tier: antitank[tier]["source"] for tier in range(3, 13)},
            {
                3: "personal_antitank_03_shaped_charge_grenade.dds",
                4: "personal_antitank_04_antitank_rifle.dds",
                5: "personal_antitank_05_wire_guidance.png",
                6: "personal_antitank_06_recoilless_launcher.png",
                7: "personal_antitank_07_saclos_guidance.png",
                8: "personal_antitank_08_rocket_launcher.dds",
                9: "personal_antitank_09_top_attack_seeker.dds",
                10: "personal_antitank_10_tandem_warhead.png",
                11: "personal_antitank_11_loitering_munition.png",
                12: "personal_antitank_12_multispectral_targeting.png",
            },
        )
        self.assertEqual(
            antitank[1]["source"], "personal_antitank_01_incendiary_bottle.dds"
        )
        self.assertEqual(
            antitank[2]["source"], "personal_antitank_02_satchel_charge.dds"
        )
        self.assertEqual(
            {tier for tier, entry in antitank.items() if entry.get("runtime_master")},
            {1, 2, 3, 4, 8, 9},
        )


class TechnologyIconBuilderTests(unittest.TestCase):
    def _builder(self):
        module_name = "tools.builders.build_adiscord_technology_icons"
        self.assertIsNotNone(importlib.util.find_spec(module_name), module_name)
        return importlib.import_module(module_name)

    def test_builder_rejects_opaque_source_exports(self) -> None:
        builder = self._builder()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "tools/assets/source/technology_weapons/opaque.png"
            source.parent.mkdir(parents=True)
            for mode, color in (("RGB", (255, 0, 255)), ("RGBA", (255, 0, 255, 255))):
                with self.subTest(mode=mode):
                    Image.new(mode, (16, 16), color).save(source)
                    spec = builder.IconSpec(
                        key="opaque",
                        source=source.name,
                        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                        tier=1,
                        kind="wide",
                        output="opaque.dds",
                        source_size=(16, 16),
                    )
                    with self.assertRaisesRegex(
                        RuntimeError, "alpha channel|transparent background"
                    ):
                        builder.render_icon(spec, root)

    def test_rendered_dds_outputs_have_exact_contract_geometry(self) -> None:
        builder = self._builder()
        outputs = builder.render_outputs(ROOT)
        dds_outputs = {
            path: payload
            for path, payload in outputs.items()
            if path.suffix == ".dds" and path.parent.name == "technologies"
        }

        self.assertEqual(len(dds_outputs), len(builder.load_manifest()))
        for path, payload in dds_outputs.items():
            with Image.open(BytesIO(payload)) as image:
                expected = (
                    (72, 72)
                    if path.name.startswith(
                        ("ADISCORD_night_", "ADISCORD_antitank_", "ADISCORD_equipment_")
                    )
                    else (176, 72)
                )
                self.assertEqual(image.size, expected, path)
                self.assertEqual(image.mode, "RGBA", path)

    def test_rendered_personal_antitank_icons_are_compact(self) -> None:
        builder = self._builder()
        outputs = builder.render_outputs(ROOT)
        antitank = {
            path: payload
            for path, payload in outputs.items()
            if path.name.startswith("ADISCORD_antitank_")
        }

        self.assertEqual(len(antitank), 12)
        for path, payload in antitank.items():
            with Image.open(BytesIO(payload)) as image:
                self.assertEqual(image.size, (72, 72), path)
                self.assertEqual(image.mode, "RGBA", path)

    def test_infantry_sprites_have_transparent_margins_and_no_key_colour(self) -> None:
        builder = self._builder()
        for spec in builder.load_manifest():
            if spec.kind != "wide" and spec.family != "equipment":
                continue
            with self.subTest(icon=spec.key):
                icon = builder.render_icon(spec)
                alpha = icon.getchannel("A")
                bbox = alpha.getbbox()
                self.assertIsNotNone(bbox)
                self.assertGreaterEqual(bbox[0], 3)
                self.assertGreaterEqual(bbox[1], 3)
                self.assertLessEqual(bbox[2], icon.width - 3)
                self.assertLessEqual(bbox[3], icon.height - 3)
                self.assertGreater(
                    alpha.histogram()[0], icon.width * icon.height * 0.25
                )
                self.assertFalse(
                    any(
                        opacity >= 32
                        and min(red, blue) > 45
                        and min(red, blue) - green > 40
                        for red, green, blue, opacity in icon.get_flattened_data()
                    ),
                    spec.key,
                )

    def test_rendered_personal_antitank_icons_are_clean_alpha_cutouts(self) -> None:
        builder = self._builder()
        outputs = builder.render_outputs(ROOT)
        issues: list[str] = []

        for path, payload in outputs.items():
            if not path.name.startswith("ADISCORD_antitank_"):
                continue
            tier = int(path.name.split("_")[2])
            if tier < 3:
                continue
            with Image.open(BytesIO(payload)) as image:
                rgba = image.convert("RGBA")
                alpha = rgba.getchannel("A")
                histogram = alpha.histogram()
                transparent_ratio = sum(histogram[:8]) / (72 * 72)
                partial_alpha = sum(histogram[8:248])
                bbox = alpha.getbbox()
                magenta_pixels = sum(
                    1
                    for red, green, blue, opacity in rgba.get_flattened_data()
                    if opacity >= 16
                    and red >= 175
                    and blue >= 175
                    and green <= 110
                    and abs(red - blue) <= 65
                )

            if transparent_ratio < 0.45:
                issues.append(f"{path.name}: transparent_ratio={transparent_ratio:.3f}")
            if partial_alpha < 16:
                issues.append(f"{path.name}: partial_alpha={partial_alpha}")
            if magenta_pixels:
                issues.append(f"{path.name}: magenta_pixels={magenta_pixels}")
            if (
                bbox is None
                or bbox[0] < 3
                or bbox[1] < 3
                or bbox[2] > 69
                or bbox[3] > 69
            ):
                issues.append(f"{path.name}: unsafe_bbox={bbox}")

        self.assertEqual(issues, [])

    def test_icon_builder_does_not_override_vanilla_techtree_connectors(self) -> None:
        builder = self._builder()
        outputs = builder.render_outputs(ROOT)

        self.assertFalse(any(path.parent.name == "techtree" for path in outputs))

    def test_apply_removes_obsolete_generated_connector_overrides(self) -> None:
        builder = self._builder()
        obsolete = (
            "techtree_line_vertical.dds",
            "techtree_line_horisontal.dds",
            "techline_center_all_researched.dds",
            "techline_center_bottom_left_researched.dds",
            "techline_center_bottom_right_researched.dds",
            "techline_center_down_researched.dds",
            "techline_center_left_researched.dds",
            "techline_center_right_researched.dds",
            "techline_center_top_left_researched.dds",
            "techline_center_top_right_researched.dds",
            "techline_center_up_researched.dds",
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            connector_dir = root / "gfx" / "interface" / "techtree"
            connector_dir.mkdir(parents=True)
            for name in obsolete:
                (connector_dir / name).write_bytes(b"obsolete")

            builder.apply({}, root)

            self.assertFalse(any((connector_dir / name).exists() for name in obsolete))

    def test_rendered_outputs_are_byte_deterministic(self) -> None:
        builder = self._builder()
        first = builder.render_outputs(ROOT)
        second = builder.render_outputs(ROOT)

        self.assertEqual(first, second)
        self.assertIn(builder.CONTACT_SHEET.relative_to(ROOT), first)

    def test_contact_sheet_separates_service_squad_and_night_rows(self) -> None:
        builder = self._builder()
        payload = builder.render_outputs(ROOT)[builder.CONTACT_SHEET.relative_to(ROOT)]

        with Image.open(BytesIO(payload)) as sheet:
            self.assertLessEqual(sheet.width, 2000)
            self.assertGreaterEqual(sheet.height, 340)

    def test_command_line_facade_exists(self) -> None:
        self.assertTrue(FACADE.is_file(), FACADE)


if __name__ == "__main__":
    unittest.main()
