from pathlib import Path

path = Path('tools/tests/test_build_adiscord_technology_icons.py')
text = path.read_text(encoding='utf-8')
start = text.index('    def test_night_icons_use_generated_complete_sprite_cells')
end = text.index('    def test_manifest_has_twelve_ranked_personal_antitank_icons', start)
replacement = '''    def test_night_icons_preserve_selected_runtime_artwork(self) -> None:
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

'''
path.write_text(text[:start] + replacement + text[end:], encoding='utf-8')
