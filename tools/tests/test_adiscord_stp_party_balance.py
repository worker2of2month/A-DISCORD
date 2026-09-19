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

    def test_party_route_requires_staged_defensive_recovery(self) -> None:
        actions = read(ROOT / "common/on_actions/02_ADISCORD_STP_on_actions.txt")
        self.assertIn("STP_ps_begin_defence = yes", actions)
        begin = named_block(self.effects, "STP_ps_begin_defence")
        self.assertIn("NOT = { has_variable = STP_ps_stage }", begin)
        recovery = named_block(self.effects, "STP_ps_refresh_defence")
        for value in ("-0.45", "-0.3", "-0.15"):
            self.assertIn("var = STP_ps_breakthrough value = " + value, recovery)
        self.assertNotIn("army_defence_factor = -", recovery)
        self.assertNotIn("STP_cw_party_initial_disarray", self.effects)
        for stage in (1, 2, 3):
            funded = named_block(self.decisions, f"STP_ps_reorg_{stage}_funded")
            self.assertIn("STP_ps_reorg_deposit", funded)
            self.assertIn("activate_mission", funded)

    def test_congress_crisis_depends_on_the_city_and_penalizes_once(self) -> None:
        crisis = named_block(self.effects, "STP_ps_open_congress_crisis")
        self.assertIn("STP_ps_holds_congress = no", crisis)
        self.assertIn("NOT = { has_country_flag = STP_ps_congress_fell }", crisis)
        self.assertIn("add_war_support = -0.10", crisis)
        self.assertIn("add_stability = -0.15", crisis)
        self.assertIn("var = STP_apparatus_loyalty_change value = -20", crisis)
        self.assertIn("STP_change_apparatus_loyalty = yes", crisis)
        self.assertIn("STP_ps_pause_reorganisation = yes", crisis)
        banquet = named_block(self.effects, "STP_cw_resolve_last_banquet_success")
        self.assertNotIn("STP_cw_congress_fall_crisis_applied", banquet)

    def test_balance_mechanics_have_player_facing_localisation(self) -> None:
        for key in ("STP_ps_reorg_1:", "STP_ps_reorg_1_desc:",
                    "STP_ps_congress_deadline:", "STP_ps_congress_deadline_desc:"):
            self.assertIn(key, self.loc)


if __name__ == "__main__":
    unittest.main()
