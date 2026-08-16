import re
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
