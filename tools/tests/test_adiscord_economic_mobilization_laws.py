import hashlib
import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
IDEAS_PATH = ROOT / "common" / "ideas" / "_economic.txt"
TRIGGERS_PATH = ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
MODIFIER_EFFECTS_PATH = (
    ROOT / "common" / "scripted_effects" / "ADISCORD_economy_modifier_effects.txt"
)
GENERAL_EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "00_scripted_effects.txt"
GFX_PATH = ROOT / "interface" / "ADISCORD_ideas.gfx"
RU_LOC_PATH = ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"

ACTIVE_LAWS = (
    "ADISCORD_civilian_oriented_economy",
    "civilian_economy",
    "low_economic_mobilisation",
    "partial_economic_mobilisation",
    "war_economy",
    "tot_economic_mobilisation",
)
EXPECTED_LEVELS = {
    "ADISCORD_civilian_oriented_economy": "6",
    "civilian_economy": "5",
    "low_economic_mobilisation": "4",
    "partial_economic_mobilisation": "3",
    "war_economy": "2",
    "tot_economic_mobilisation": "1",
}
EXPECTED_NEW_LAW_MODIFIERS = {
    "consumer_goods_expected_value": "0.38",
    "stability_factor": "0.12",
    "production_speed_industrial_complex_factor": "0.18",
    "production_speed_arms_factory_factor": "-0.40",
    "production_speed_dockyard_factor": "-0.35",
    "conversion_cost_civ_to_mil_factor": "0.40",
    "conversion_cost_mil_to_civ_factor": "-0.15",
    "production_factory_max_efficiency_factor": "-0.08",
    "industrial_capacity_factory": "-0.10",
    "max_fuel_factor": "-0.35",
    "fuel_gain_factor": "-0.45",
    "factory_energy_consumption": "-0.30",
    "ADISCORD_economy_civilian_factory_income_factor": "0.15",
    "ADISCORD_economy_military_industry_income_factor": "-0.15",
    "ADISCORD_economy_army_expense_factor": "-0.15",
    "ADISCORD_economy_inflation_pressure_factor": "-0.08",
    "ADISCORD_economy_price_stability_factor": "0.08",
    "ADISCORD_economy_creditworthiness_factor": "0.05",
    "ADISCORD_economy_state_overload_gain_factor": "-0.08",
    "ADISCORD_country_development_economic_growth_factor": "0.05",
}
EXPECTED_TEXTURES = {
    "GFX_idea_ADISCORD_economic_mobilization_1_civilian_oriented": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_1_civilian_oriented.png",
    "GFX_idea_ADISCORD_economic_mobilization_2_civilian": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_2_civilian.png",
    "GFX_idea_ADISCORD_economic_mobilization_3_early_mobilization": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_3_early_mobilization.png",
    "GFX_idea_ADISCORD_economic_mobilization_4_partial_mobilization": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_4_partial_mobilization.png",
    "GFX_idea_ADISCORD_economic_mobilization_5_war_economy": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_5_war_economy.png",
    "GFX_idea_ADISCORD_economic_mobilization_6_total_mobilization": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_6_total_mobilization.png",
}
EXPECTED_PICTURES = {
    "ADISCORD_civilian_oriented_economy": "ADISCORD_economic_mobilization_1_civilian_oriented",
    "civilian_economy": "ADISCORD_economic_mobilization_2_civilian",
    "low_economic_mobilisation": "ADISCORD_economic_mobilization_3_early_mobilization",
    "partial_economic_mobilisation": "ADISCORD_economic_mobilization_4_partial_mobilization",
    "war_economy": "ADISCORD_economic_mobilization_5_war_economy",
    "tot_economic_mobilisation": "ADISCORD_economic_mobilization_6_total_mobilization",
}
EXPECTED_SHA256 = {
    "GFX_idea_ADISCORD_economic_mobilization_1_civilian_oriented": "330E254423F2BC672C63EBEED2E47F24227CF3318F52D9F81837663EAD8517C4",
    "GFX_idea_ADISCORD_economic_mobilization_2_civilian": "6589B6A13380D6EA36E349DED05FFDE2E1942110FAE3002DAF5AB9DD33F55DB1",
    "GFX_idea_ADISCORD_economic_mobilization_3_early_mobilization": "D38526A25FFA3D5CEE1412CB331546241DF9CBD5BA60994A5DAE5AE9990218ED",
    "GFX_idea_ADISCORD_economic_mobilization_4_partial_mobilization": "FF677EEF383F90170CECA442776C645DBB586D4E5A6E6DD6B98F90B7DC17A2F5",
    "GFX_idea_ADISCORD_economic_mobilization_5_war_economy": "2AE5F8D3E02407763583BC0DB867B2CB567981F1519C78567560CEAEB141E1AE",
    "GFX_idea_ADISCORD_economic_mobilization_6_total_mobilization": "98934F65323573D1C63990078FD8F8C3BC09BA5202F410A546EFD8614C18C5C8",
}


def unique_child(entries, key):
    matches = [entry for entry in entries if entry.key == key]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one block {key}, found {len(matches)}")
    return matches[0].value


def scalar(entries, key):
    matches = [
        entry.value
        for entry in entries
        if entry.key == key and isinstance(entry.value, str)
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one scalar {key}, found {len(matches)}")
    return matches[0]


def block(text, name):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    raise AssertionError(f"unclosed block: {name}")


def law_entries():
    parsed = parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig"))
    ideas = unique_child(parsed, "ideas")
    economy = unique_child(ideas, "economy")
    return {
        entry.key: entry.value
        for entry in economy
        if entry.key and isinstance(entry.value, list)
    }


def localisation_value(text, key):
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^"]*)"', text)
    if not match:
        raise AssertionError(f"missing localisation key: {key}")
    return match.group(1)


class EconomicMobilizationLawContracts(unittest.TestCase):
    def test_active_progression_has_six_unique_levels_and_new_default(self):
        laws = law_entries()
        self.assertEqual(list(ACTIVE_LAWS), [law for law in laws if law in ACTIVE_LAWS])
        self.assertEqual(
            EXPECTED_LEVELS,
            {law: scalar(laws[law], "level") for law in ACTIVE_LAWS},
        )
        defaults = [
            law
            for law in ACTIVE_LAWS
            if any(
                entry.key == "default" and entry.value == "yes"
                for entry in laws[law]
            )
        ]
        self.assertEqual(["ADISCORD_civilian_oriented_economy"], defaults)

        self.assertEqual("8", scalar(laws["undisturbed_isolation"], "level"))
        self.assertEqual("7", scalar(laws["isolation"], "level"))
        for disabled in ("undisturbed_isolation", "isolation"):
            self.assertEqual("no", scalar(unique_child(laws[disabled], "allowed"), "always"))

    def test_new_default_law_matches_the_approved_balance(self):
        law = law_entries()["ADISCORD_civilian_oriented_economy"]
        self.assertEqual("150", scalar(law, "cost"))
        self.assertEqual("-1", scalar(law, "removal_cost"))
        self.assertEqual("6", scalar(law, "level"))
        self.assertEqual("no", scalar(unique_child(law, "available"), "has_war"))
        self.assertEqual("no", scalar(law, "cancel_if_invalid"))
        actual_modifiers = {
            entry.key: entry.value
            for entry in unique_child(law, "modifier")
            if isinstance(entry.value, str)
        }
        self.assertEqual(EXPECTED_NEW_LAW_MODIFIERS, actual_modifiers)

    def test_runtime_wrapper_cache_and_upgrade_sequence_cover_all_six_tiers(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        modifier_effects = MODIFIER_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        general_effects = GENERAL_EFFECTS_PATH.read_text(encoding="utf-8-sig")

        wrapper = block(
            triggers, "ADISCORD_economy_has_idea_civilian_oriented_economy"
        )
        self.assertIn("has_idea = ADISCORD_civilian_oriented_economy", wrapper)

        cache = block(modifier_effects, "ADISCORD_economy_recalculate_policy_modifiers")
        new_cache_branch = (
            "if = { limit = { ADISCORD_economy_has_idea_civilian_oriented_economy = yes } "
            "set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 1.0 } }"
        )
        civilian_cache_branch = (
            "else_if = { limit = { ADISCORD_economy_has_idea_civilian_economy = yes } "
            "set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 0.7 } }"
        )
        self.assertIn(new_cache_branch, cache)
        self.assertIn(civilian_cache_branch, cache)
        self.assertLess(cache.index(new_cache_branch), cache.index(civilian_cache_branch))

        upgrade = block(general_effects, "upgrade_economy_law")
        self.assertEqual(
            list(ACTIVE_LAWS[:-1]),
            re.findall(r"\bhas_idea\s*=\s*([A-Za-z0-9_]+)", upgrade),
        )
        self.assertEqual(
            list(ACTIVE_LAWS[1:]),
            re.findall(r"\badd_ideas\s*=\s*([A-Za-z0-9_]+)", upgrade),
        )

    def test_six_law_sprites_resolve_to_byte_preserved_pngs(self):
        laws = law_entries()
        self.assertEqual(
            EXPECTED_PICTURES,
            {law: scalar(laws[law], "picture") for law in ACTIVE_LAWS},
        )
        self.assertEqual(
            set(EXPECTED_TEXTURES),
            {f"GFX_idea_{picture}" for picture in EXPECTED_PICTURES.values()},
        )

        parsed = parse_clausewitz(GFX_PATH.read_text(encoding="utf-8-sig"))
        sprite_types = unique_child(parsed, "spriteTypes")
        matching = []
        for entry in sprite_types:
            if entry.key != "spriteType" or not isinstance(entry.value, list):
                continue
            name = scalar(entry.value, "name")
            if name in EXPECTED_TEXTURES:
                matching.append((name, scalar(entry.value, "texturefile")))

        self.assertEqual(len(EXPECTED_TEXTURES), len(matching))
        self.assertEqual(EXPECTED_TEXTURES, dict(matching))
        for sprite_name, relative_path in EXPECTED_TEXTURES.items():
            path = ROOT / relative_path
            self.assertEqual(
                EXPECTED_SHA256[sprite_name],
                hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            )
            with self.subTest(sprite_name=sprite_name), Image.open(path) as image:
                self.assertEqual("PNG", image.format)
                self.assertEqual((64, 64), image.size)
                self.assertIn("A", image.getbands())

    def test_new_tier_is_bilingual_and_existing_russian_names_stay_stable(self):
        self.assertTrue(RU_LOC_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
        ru = RU_LOC_PATH.read_text(encoding="utf-8-sig")
        en = EN_LOC_PATH.read_text(encoding="utf-8-sig")
        self.assertEqual(
            "Гражданско-ориентированная экономика",
            localisation_value(ru, "ADISCORD_civilian_oriented_economy"),
        )
        self.assertEqual(
            "Civilian-Oriented Economy",
            localisation_value(en, "ADISCORD_civilian_oriented_economy"),
        )
        self.assertGreater(
            len(localisation_value(ru, "ADISCORD_civilian_oriented_economy_desc")),
            120,
        )
        self.assertGreater(
            len(localisation_value(en, "ADISCORD_civilian_oriented_economy_desc")),
            120,
        )
        expected_existing = {
            "civilian_economy": "Гражданская экономика",
            "low_economic_mobilisation": "Подготовительная мобилизация",
            "partial_economic_mobilisation": "Частичная мобилизация",
            "war_economy": "Военная экономика",
            "tot_economic_mobilisation": "Тотальная мобилизация",
        }
        self.assertEqual(
            expected_existing,
            {key: localisation_value(ru, key) for key in expected_existing},
        )


if __name__ == "__main__":
    unittest.main()
