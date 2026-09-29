"""Tax spirits, war fatigue tiers and the AI tax response.

These tests inspect authored scripts, not the Clausewitz runtime.
"""

from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_economy_ai import ai_policy_contract_issues

ROOT = Path(__file__).resolve().parents[2]
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_economy_effects.txt"
IDEAS = ROOT / "common/ideas/ADISCORD_economy_ideas.txt"
SCRIPTED_LOC = ROOT / "common/scripted_localisation/ADISCORD_economy_scripted_loc.txt"
RU = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"

# Script variables are fixed point with three decimals and a 32-bit range.
VARIABLE_LIMIT = 2147483


def text(path):
    return path.read_text(encoding="utf-8-sig")


def definition(source, name):
    start = re.search(rf"(?m)^{re.escape(name)} = {{", source)
    if not start:
        raise AssertionError(f"{name} is not defined")
    depth = 0
    for index in range(start.end() - 1, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start.start():index + 1]
    raise AssertionError(f"{name} is not closed")


def loc_keys(path):
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'(?m)^\s+([A-Za-z0-9_.]+):\d*\s*"(.*)"\s*$', text(path))
    }


class TaxSpiritTests(unittest.TestCase):
    def test_every_non_neutral_tax_level_has_a_localised_spirit(self):
        ideas = text(IDEAS)
        ru = loc_keys(RU)
        en = loc_keys(EN)
        for level in (1, 2, 4, 5):
            idea = f"ADISCORD_economy_tax_burden_{level}"
            self.assertRegex(ideas, rf"(?m)^\t\t{idea} = {{")
            self.assertTrue(ru.get(idea) and en.get(idea), idea)
        self.assertNotIn("ADISCORD_economy_tax_burden_3 = {", ideas)

    def test_tax_change_swaps_the_spirit_and_the_monthly_refresh_keeps_it(self):
        effects = text(EFFECTS)
        refresh = definition(effects, "ADISCORD_economy_refresh_tax_policy")
        self.assertIn("ADISCORD_economy_refresh_tax_policy_idea = yes", refresh)
        swap = definition(effects, "ADISCORD_economy_refresh_tax_policy_idea")
        for level in (1, 2, 4, 5):
            self.assertIn(f"remove_ideas = ADISCORD_economy_tax_burden_{level}", swap)
        monthly = definition(effects, "ADISCORD_economy_refresh_spending_ideas")
        self.assertIn("ADISCORD_economy_add_tax_burden_idea = yes", monthly)
        for level in (1, 2, 4, 5):
            self.assertIn(f"remove_ideas = ADISCORD_economy_tax_burden_{level}", monthly)
        preview = definition(effects, "ADISCORD_economy_preview_tax_policy")
        self.assertNotIn("_idea", preview.replace("idea_", ""))

    def test_one_rate_scales_every_taxable_bucket_without_early_caps(self):
        table = definition(text(EFFECTS), "ADISCORD_economy_apply_tax_burden_to_income")
        rates = {}
        for level, body in re.findall(
            r"tax_burden_mode value = ([1-5]) compare = equals \} \}\n(.*?)\n\t\}", table, re.S
        ):
            factors = set(re.findall(r"_income value = (\d+\.\d+) \}", body))
            self.assertEqual(len(factors), 1, level)
            self.assertEqual(body.count("multiply_variable"), 4, level)
            rates[int(level)] = float(factors.pop())
        self.assertEqual(rates, {1: 0.50, 2: 0.75, 4: 1.40, 5: 1.85})
        # The pre-tax bases are capped at 100 and 50; the top rate must not be cut.
        for bucket, limit in (("personal", 500), ("factory", 500)):
            self.assertIn(f"clamp_variable = {{ var = ADISCORD_economy_{bucket}_income min = 0 max = {limit} }}", table)

    def test_level_tooltips_state_the_spirit_effects_inline(self):
        for path in (RU, EN):
            keys = loc_keys(path)
            for level in (1, 2, 4, 5):
                tooltip = keys[f"ADISCORD_economy_tax_level_{level}_tt"]
                self.assertNotIn("$", tooltip)
                self.assertIn("%", tooltip.split("\\n")[-1])


class IdeaSignatureTests(unittest.TestCase):
    def test_signature_halves_stay_inside_the_variable_range(self):
        monthly = definition(text(EFFECTS), "ADISCORD_economy_refresh_spending_ideas")
        multipliers = [
            int(value)
            for value in re.findall(r"multiply_temp_variable = \{ var = ADISCORD_economy_idea_(?:component|tier)_temp value = (\d+) \}", monthly)
        ]
        self.assertTrue(multipliers)
        # Each component is at most 5; the largest weight times nine digits must fit.
        self.assertLess(max(multipliers) * 9, VARIABLE_LIMIT)
        self.assertIn("ADISCORD_economy_last_idea_signature_b", monthly)


class WarFatigueTests(unittest.TestCase):
    def test_every_level_has_a_spirit_and_an_explanation(self):
        ideas = text(IDEAS)
        effects = text(EFFECTS)
        scripted = text(SCRIPTED_LOC)
        ru = loc_keys(RU)
        en = loc_keys(EN)
        for level in (1, 2, 3, 4):
            idea = f"ADISCORD_economy_war_fatigue_{level}"
            self.assertRegex(ideas, rf"(?m)^\t\t{idea} = {{")
            self.assertIn(f"add_ideas = {idea}", effects)
            self.assertIn(f"remove_ideas = {idea}", effects)
            key = f"ADISCORD_economy_war_fatigue_effect_{level}"
            self.assertIn(f"localization_key = {key}", scripted)
            self.assertTrue(ru.get(key) and en.get(key), key)

    def test_losing_wars_and_wartime_taxes_raise_fatigue(self):
        fatigue = definition(text(EFFECTS), "ADISCORD_economy_update_war_fatigue")
        self.assertIn("surrender_progress > 0.3", fatigue)
        self.assertIn("surrender_progress > 0.1", fatigue)
        self.assertIn("ADISCORD_economy_tax_burden_mode value = 5 compare = greater_than_or_equals", fatigue)
        side_effects = definition(text(EFFECTS), "ADISCORD_economy_apply_tax_burden_side_effects")
        self.assertNotIn("war_fatigue_score", side_effects.replace("clamp_variable = { var = ADISCORD_economy_war_fatigue_score", ""))


class AiTaxPolicyTests(unittest.TestCase):
    def test_policy_contract_holds_and_taxes_follow_mood_and_war(self):
        effects = text(EFFECTS)
        self.assertEqual(ai_policy_contract_issues(effects), [])
        policy = definition(effects, "ADISCORD_economy_ai_monthly_policy")
        self.assertGreaterEqual(policy.count("ADISCORD_economy_has_high_war_fatigue = yes"), 2)
        self.assertIn("has_stability < 0.4", policy)
        self.assertIn("ADISCORD_economy_war_fatigue_level value = 4 compare = greater_than_or_equals", policy)
        self.assertGreaterEqual(policy.count("ADISCORD_economy_increase_tax_burden = yes"), 4)
        self.assertGreaterEqual(policy.count("ADISCORD_economy_decrease_tax_burden = yes"), 6)


if __name__ == "__main__":
    unittest.main()
