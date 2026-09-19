from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]

IDEAS = ROOT / "common/ideas/ADISCORD_STP_civil_war_ideas.txt"
EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
LOC = ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def named_block(text: str, name: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(name) + r"\s*=\s*\{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    start = match.start()
    brace = text.find("{", match.start())
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unterminated block {name}")


class StelanderPartyBalanceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ideas = read(IDEAS)
        cls.effects = read(EFFECTS)
        cls.decisions = read(DECISIONS)
        cls.loc = read(LOC)

    def test_faction_negotiations_remain_bounded_and_expensive(self) -> None:
        for faction in ("conservatives", "borons", "security", "army", "advisers", "merchants", "radicals"):
            block = named_block(self.decisions, f"STP_pf_negotiate_{faction}")
            self.assertRegex(block, r"(?m)^\s*cost\s*=\s*35\s*$")
            self.assertRegex(
                block,
                rf"check_variable\s*=\s*\{{\s*var\s*=\s*STP_pf_{faction}_influence\s+value\s*=\s*60\s+compare\s*=\s*less_than\s*\}}",
            )
            self.assertRegex(
                block,
                r"flag\s*=\s*STP_pf_negotiation_cooldown\s+value\s*=\s*1\s+days\s*=\s*30",
            )

        calculate = named_block(self.effects, "STP_pf_calculate")
        coefficients = [
            abs(float(value))
            for value in re.findall(
                r"multiply_temp_variable\s*=\s*\{[^}]*?value\s*=\s*(-?0\.\d+)",
                calculate,
                flags=re.S,
            )
        ]
        self.assertTrue(coefficients)
        self.assertLessEqual(max(coefficients), 0.004)

        shift = named_block(self.effects, "STP_pf_shift")
        self.assertRegex(
            shift,
            r"set_temp_variable\s*=\s*\{\s*var\s*=\s*STP_pf_gain\s+value\s*=\s*5\s*\}",
        )
        # Deals stop below 60 influence. A final +5 step can only cross to <65;
        # with support clamped at 100 and effects centered on 50, even the
        # strongest manual-deal effect stays below 13%.
        manual_deal_ceiling = 65
        self.assertLess(max(coefficients) * manual_deal_ceiling * 50 / 100, 0.131)

    def test_human_party_route_opens_with_a_real_defensive_phase(self) -> None:
        begin = named_block(self.effects, "STP_cw_begin_hostilities")
        self.assertIn("is_ai = no has_country_flag = STP_sided_with_the_party_flag", begin)
        self.assertIn(
            "add_timed_idea = { idea = STP_cw_party_initial_disarray days = 35 }",
            begin,
        )

        idea = named_block(self.ideas, "STP_cw_party_initial_disarray")
        self.assertIn("army_attack_factor = -0.25", idea)
        self.assertIn("breakthrough_factor = -0.20", idea)
        self.assertIn("planning_speed = -0.10", idea)
        self.assertNotIn("army_defence_factor = -", idea)

    def test_bronze_congress_loss_is_a_heavy_player_party_crisis(self) -> None:
        success = named_block(self.effects, "STP_cw_resolve_last_banquet_success")
        self.assertIn("STP_cw_congress_fall_crisis_applied", success)
        self.assertIn("add_war_support = -0.10", success)
        self.assertIn(
            "add_timed_idea = { idea = STP_cw_congress_fall_crisis days = 70 }",
            success,
        )
        self.assertIn("var = STP_apparatus_loyalty_change value = -12", success)
        self.assertIn("STP_change_apparatus_loyalty = yes", success)

        crisis = named_block(self.ideas, "STP_cw_congress_fall_crisis")
        self.assertIn("stability_factor = -0.10", crisis)
        self.assertIn("political_power_gain = -0.15", crisis)
        self.assertIn("army_org_factor = -0.10", crisis)
        self.assertIn("planning_speed = -0.15", crisis)

    def test_balance_mechanics_have_player_facing_localisation(self) -> None:
        for key in (
            "STP_cw_party_initial_disarray:",
            "STP_cw_party_initial_disarray_desc:",
            "STP_cw_congress_fall_crisis:",
            "STP_cw_congress_fall_crisis_desc:",
        ):
            self.assertIn(key, self.loc)


if __name__ == "__main__":
    unittest.main()
