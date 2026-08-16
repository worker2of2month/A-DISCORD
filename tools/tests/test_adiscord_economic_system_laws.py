import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
IDEAS_PATH = ROOT / "common" / "ideas" / "_economic.txt"
GFX_PATH = ROOT / "interface" / "ADISCORD_ideas.gfx"
TRIGGERS_PATH = ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "ADISCORD_economy_effects.txt"
RU_LOC_PATH = ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"

SYSTEM_SUFFIXES = (
    "agrarian",
    "industrializing",
    "free_market",
    "mixed",
    "state_coordinated",
    "planned_bureaucratic",
    "syndicalist",
    "oligarchic_clan",
    "technocratic",
)
SYSTEM_IDS = tuple(f"ADISCORD_economic_system_{suffix}" for suffix in SYSTEM_SUFFIXES)
EXPECTED_TEXTURES = {
    system_id: f"gfx/interface/ideas/laws/economic_system/{system_id}.png"
    for system_id in SYSTEM_IDS
}
EXPECTED_SYNDICALIST_MODIFIERS = {
    "consumer_goods_expected_value": "0.05",
    "min_export": "-0.05",
    "industrial_capacity_factory": "0.03",
    "production_speed_industrial_complex_factor": "0.10",
    "production_speed_infrastructure_factor": "0.05",
    "line_change_production_efficiency_factor": "-0.05",
    "production_factory_max_efficiency_factor": "0.05",
    "production_factory_efficiency_gain_factor": "0.05",
    "political_power_gain": "-0.03",
    "stability_factor": "0.05",
    "ADISCORD_economy_tax_collection_factor": "0.05",
    "ADISCORD_economy_trade_income_factor": "-0.05",
    "ADISCORD_economy_civilian_factory_income_factor": "0.10",
    "ADISCORD_economy_building_income_factor": "0.08",
    "ADISCORD_economy_admin_expense_factor": "0.08",
    "ADISCORD_economy_creditworthiness_factor": "-0.05",
    "ADISCORD_economy_price_stability_factor": "0.05",
    "ADISCORD_economy_investment_confidence_factor": "-0.10",
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


def localisation_value(text, key):
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^"]*)"', text)
    if not match:
        raise AssertionError(f"missing localisation key: {key}")
    return match.group(1)


def walk(entries):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


class EconomicSystemLawContracts(unittest.TestCase):
    def test_economic_system_sprites_resolve_to_dedicated_pngs(self):
        parsed = parse_clausewitz(GFX_PATH.read_text(encoding="utf-8-sig"))
        sprite_types = unique_child(parsed, "spriteTypes")
        actual = {}
        for entry in sprite_types:
            if entry.key != "spriteType" or not isinstance(entry.value, list):
                continue
            name = scalar(entry.value, "name")
            if name.startswith("GFX_idea_ADISCORD_economic_system_"):
                system_id = name.removeprefix("GFX_idea_")
                actual[system_id] = scalar(entry.value, "texturefile")

        self.assertEqual(EXPECTED_TEXTURES, actual)
        for system_id, relative_path in EXPECTED_TEXTURES.items():
            with self.subTest(system_id=system_id), Image.open(
                ROOT / relative_path
            ) as image:
                self.assertEqual("PNG", image.format)
                self.assertEqual((64, 64), image.size)
                self.assertIn("A", image.getbands())

    def test_roster_and_syndicalist_law_match_the_approved_contract(self):
        parsed = parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig"))
        ideas = unique_child(parsed, "ideas")
        category = unique_child(ideas, "ADISCORD_economic_system_laws")
        law_entries = {
            entry.key: entry.value
            for entry in category
            if entry.key.startswith("ADISCORD_economic_system_")
            and isinstance(entry.value, list)
        }
        self.assertEqual(list(SYSTEM_IDS), list(law_entries))

        syndicalist = law_entries["ADISCORD_economic_system_syndicalist"]
        self.assertEqual(
            "ADISCORD_economic_system_syndicalist", scalar(syndicalist, "picture")
        )
        self.assertEqual("300", scalar(syndicalist, "cost"))
        self.assertEqual("-1", scalar(syndicalist, "removal_cost"))
        self.assertEqual("no", scalar(syndicalist, "cancel_if_invalid"))

        availability = unique_child(syndicalist, "available")
        availability_entries = list(walk(availability))
        self.assertEqual(
            {"anarchism", "utilitarism"},
            {
                entry.value
                for entry in availability_entries
                if entry.key == "has_government"
            },
        )
        self.assertEqual(
            ["ADISCORD_labor_policy_guild_protections"],
            [
                entry.value
                for entry in availability_entries
                if entry.key == "has_idea"
            ],
        )

        modifiers = unique_child(syndicalist, "modifier")
        actual_modifiers = {
            entry.key: entry.value
            for entry in modifiers
            if isinstance(entry.value, str)
        }
        self.assertEqual(EXPECTED_SYNDICALIST_MODIFIERS, actual_modifiers)

    def test_model_five_is_syndicalist_without_old_wartime_special_cases(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn(
            "has_idea = ADISCORD_economic_system_syndicalist",
            block(
                triggers,
                "ADISCORD_economy_has_idea_economic_system_syndicalist",
            ),
        )
        predicate = block(triggers, "ADISCORD_economy_model_is_syndicalist")
        self.assertIn("value = 5 compare = greater_than_or_equals", predicate)
        self.assertIn("value = 6 compare = less_than", predicate)

        refresh = block(effects, "ADISCORD_economy_update_model_and_cycle")
        self.assertIn(
            "else_if = { limit = { ADISCORD_economy_has_idea_economic_system_syndicalist = yes } set_variable = { var = ADISCORD_economy_model value = 5 } }",
            refresh,
        )
        obsolete = (
            "ADISCORD_economic_system_mobilization",
            "ADISCORD_economy_has_idea_economic_system_mobilization",
            "ADISCORD_economy_model_is_mobilization",
        )
        active_text = "\n".join(
            (IDEAS_PATH.read_text(encoding="utf-8-sig"), triggers, effects)
        )
        for symbol in obsolete:
            self.assertNotIn(symbol, active_text)
        self.assertNotIn("ADISCORD_economy_model_is_syndicalist", effects)

        advanced = block(triggers, "ADISCORD_economy_model_allows_advanced_taxation")
        market = block(triggers, "ADISCORD_economy_model_allows_market_expansion")
        self.assertIn("ADISCORD_economy_model_is_syndicalist = yes", advanced)
        self.assertIn("ADISCORD_economy_model_is_syndicalist = yes", market)
        for capability in (
            "ADISCORD_economy_model_allows_state_planning",
            "ADISCORD_economy_model_allows_mobilization_economy",
            "ADISCORD_economy_model_allows_emergency_extraction",
        ):
            self.assertNotIn(
                "ADISCORD_economy_model_is_syndicalist = yes",
                block(triggers, capability),
            )
        mobilization_capability = block(
            triggers, "ADISCORD_economy_model_allows_mobilization_economy"
        )
        self.assertIn(
            "ADISCORD_economy_model_is_state_coordinated = yes",
            mobilization_capability,
        )
        self.assertIn(
            "ADISCORD_economy_model_is_planned_bureaucratic = yes",
            mobilization_capability,
        )

    def test_syndicalist_localisation_is_bilingual_and_russian_keeps_bom(self):
        self.assertTrue(RU_LOC_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
        ru = RU_LOC_PATH.read_text(encoding="utf-8-sig")
        en = EN_LOC_PATH.read_text(encoding="utf-8-sig")
        self.assertEqual(
            "Синдикалистская экономика",
            localisation_value(ru, "ADISCORD_economic_system_syndicalist"),
        )
        self.assertEqual(
            "Синдикалистская экономика",
            localisation_value(ru, "ADISCORD_economy_model_5"),
        )
        self.assertEqual(
            "расширенное налогообложение, кооперативные инвестиции, гражданское строительство",
            localisation_value(ru, "ADISCORD_economy_model_unlocks_5"),
        )
        self.assertEqual(
            "административные расходы, слабые частные инвестиции и кредитоспособность",
            localisation_value(ru, "ADISCORD_economy_model_penalties_5"),
        )
        self.assertEqual(
            "Syndicalist Economy",
            localisation_value(en, "ADISCORD_economic_system_syndicalist"),
        )
        self.assertEqual(
            "Syndicalist economy",
            localisation_value(en, "ADISCORD_economy_model_5"),
        )
        self.assertNotIn("ADISCORD_economic_system_mobilization:", ru)
        self.assertGreater(
            len(
                localisation_value(
                    ru, "ADISCORD_economic_system_syndicalist_desc"
                )
            ),
            80,
        )
        self.assertGreater(
            len(
                localisation_value(
                    en, "ADISCORD_economic_system_syndicalist_desc"
                )
            ),
            80,
        )


if __name__ == "__main__":
    unittest.main()
