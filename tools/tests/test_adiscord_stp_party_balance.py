from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_party_route import one
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

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
        arithmetic = one(parse_clausewitz(calculate), "STP_pf_calculate")
        coefficients = []
        for faction in ("conservatives", "borons", "security", "army", "advisers", "merchants", "radicals"):
            target = f"STP_pf_{faction}_effect"
            writes = [e for e in arithmetic if isinstance(e.value, list)
                      and any(c.key == "var" and c.value == target for c in e.value)]
            self.assertEqual([e.key for e in writes], [
                "set_variable", "subtract_from_variable", "multiply_variable",
                "divide_variable", "multiply_variable",
            ] + (["clamp_variable"] if faction == "advisers" else []), faction)
            if faction == "advisers":
                self.assertEqual(one(writes[-1].value, "min"), "0")
                self.assertEqual(one(writes[-1].value, "max"), "0.2")
            values = [one(e.value, "value") for e in writes if e.key != "clamp_variable"]
            self.assertEqual(values[:4], [f"STP_pf_{faction}_support", "50",
                                          f"STP_pf_{faction}_influence", "100"])
            coefficients.append(abs(float(values[4])))
        self.assertEqual(len(coefficients), 7)
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

    def test_northern_preparation_charges_both_currencies(self) -> None:
        for action, pp, cash in (("emergency_mobilization", 50, 900),
                                 ("fortify_border", 35, 1080),
                                 ("staff_readiness", 35, 720)):
            block = named_block(self.decisions, f"STP_pw_party_nod_{action}")
            self.assertRegex(block, r"(?m)^\s*cost = 0\s*$")
            price = named_block(block, "custom_cost_trigger")
            reward = named_block(block, "complete_effect")
            self.assertIn(f"has_political_power < {pp}", price)
            self.assertIn(f"value = {cash}", price)
            self.assertEqual(reward.count(f"add_political_power = -{pp}"), 1)
            self.assertIn("STP_pw_party_nod_threat_current = yes", reward)
            key = f"STP_pw_party_nod_{action}_cost"
            for suffix in ("", "_blocked", "_tooltip"):
                self.assertIn(key + suffix + ":", self.loc)

    def test_sovereignty_dispatch_does_not_read_its_own_completion(self) -> None:
        start = named_block(self.effects, "STP_pw_party_start_nod_invasion_threat")
        self.assertNotIn("has_completed_focus = STP_pw_party_sovereignty", start)
        self.assertIn("STP_pw_party_nod_threat_active", named_block(start, "limit"))

    def test_reform_capstones_require_delivered_recovery(self) -> None:
        focus = read(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt")
        parsed = parse_clausewitz(focus)
        focuses = {one(f.value, "id"): f.value for tree in parsed
                   if tree.key == "focus_tree" for f in tree.value if f.key == "focus"}
        for fid, requirement in (("STP_pw_party_civil_charter", "STP_pw_recovery_services"),
                                 ("STP_party_technical_institutes", "STP_pw_recovery_services"),
                                 ("STP_pw_party_industrial_settlement", "STP_pw_recovery_industry")):
            self.assertIn(requirement, str(one(focuses[fid], "available")))

    def test_northern_timeout_distinguishes_war_defeat_and_absent_enemy(self) -> None:
        effect = one(parse_clausewitz(self.effects), "STP_pw_party_launch_nod_invasion")
        base = {("STP", "tag", "STP"): True,
                ("STP", "has_country_flag", "STP_pw_party_nod_threat_active"): True,
                ("NOD", "exists", "yes"): True,
                ("NOD", "has_capitulated", "no"): True,
                ("NOD", "is_subject", "no"): True}
        scenarios = [({}, "active", True),
                     ({("STP", "has_war_with", "NOD"): True}, "active", False),
                     ({("NOD", "exists", "yes"): False}, "defeated", False),
                     ({("NOD", "has_capitulated", "no"): False}, "defeated", False),
                     ({("STP", "has_capitulated", "yes"): True}, "lost", False),
                     ({("STP", "is_subject", "yes"): True}, "lost", False)]
        for changes, outcome, declaration in scenarios:
            with self.subTest(changes=changes):
                effects = list(selected_effects(effect, base | changes))
                marks = [e.value for scope, e in effects if scope == "STP" and e.key == "set_country_flag"]
                self.assertEqual(marks, ["STP_pw_party_nod_invasion_" + outcome])
                self.assertEqual(any(e.key == "declare_war_on" for _, e in effects), declaration)
        self.assertEqual(list(selected_effects(effect, base | {
            ("STP", "has_country_flag", "STP_pw_party_nod_threat_active"): False})), [])

    def test_northern_payments_reject_fractional_shortfalls(self) -> None:
        for action, pp, cash in (("emergency_mobilization", 50, 900),
                                 ("fortify_border", 35, 1080), ("staff_readiness", 35, 720)):
            parsed = one(parse_clausewitz(named_block(self.decisions, "STP_pw_party_nod_" + action)),
                         "STP_pw_party_nod_" + action)
            price = one(parsed, "custom_cost_trigger")
            for actual_pp, actual_cash, expected in ((pp, cash, True), (pp - .01, cash, False),
                                                   (pp, cash - .01, False), (pp + 1, cash + 1, True)):
                facts = {("STP", "numeric", "has_political_power"): actual_pp,
                         ("STP", "variable", "ADISCORD_economy_treasury"): actual_cash}
                self.assertEqual(matches_conditions(price, facts), expected)

    def test_prewar_settlement_eases_but_does_not_lock_postwar_course(self) -> None:
        parsed = parse_clausewitz(read(ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"))
        focuses = {one(f.value, "id"): f.value for tree in parsed
                   if tree.key == "focus_tree" for f in tree.value if f.key == "focus"}
        for fid, faction, preparation in (
                ("STP_pw_party_district_congress", "borons", "STP_party_district_compact"),
                ("STP_pw_party_executive_secretariat", "security", "STP_ROTATE_DISTRICT_COMMAND")):
            for prepared, support, expected in ((False, 49.99, False), (False, 50, True),
                                                (True, 34.99, False), (True, 35, True)):
                facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                         ("STP", "has_completed_focus", preparation): prepared,
                         ("STP", "variable", f"STP_pf_{faction}_support"): support}
                self.assertEqual(matches_conditions(one(focuses[fid], "available"), facts), expected)
        for fid in ("STP_pw_party_northern_protocol", "STP_pw_party_protectorate"):
            self.assertTrue(matches_conditions(one(focuses[fid], "bypass"), {
                ("STP", "is_subject_of", "NOD"): True}))

    def test_ai_negotiates_for_the_pending_reform_only_until_consent(self) -> None:
        for faction, prerequisite, capstone, threshold in (
                ("borons", "STP_party_local_cadres", "STP_pw_party_district_congress", 50),
                ("security", "STP_party_chain_of_command", "STP_pw_party_executive_secretariat", 50),
                ("merchants", "STP_party_port_contracts", "STP_pw_party_commercial_recovery", 45),
                ("army", "STP_party_industrial_board", "STP_pw_party_defence_combine", 45)):
            name = "STP_pf_negotiate_" + faction
            decision = one(parse_clausewitz(named_block(self.decisions, name)), name)
            priority = next(e.value for e in one(decision, "ai_will_do")
                            if e.key == "modifier" and one(e.value, "factor") == "50")
            conditions = [e for e in priority if e.key != "factor"]
            facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                     ("STP", "has_completed_focus", prerequisite): True,
                     ("STP", "variable", f"STP_pf_{faction}_support"): threshold - .01}
            self.assertTrue(matches_conditions(conditions, facts))
            for changes in ({("STP", "has_completed_focus", prerequisite): False},
                            {("STP", "has_completed_focus", capstone): True},
                            {("STP", "variable", f"STP_pf_{faction}_support"): threshold}):
                self.assertFalse(matches_conditions(conditions, facts | changes))

    def test_settlement_event_left_open_cannot_spend_after_charter(self) -> None:
        events = parse_clausewitz(read(ROOT / "events/ADISCORD_STP_events.txt"))
        for number in (26, 27):
            event = next(e.value for e in events if e.key == "country_event"
                         and one(e.value, "id") == f"ADISCORD_STP_pc.{number}")
            self.assertEqual(one(event, "fire_only_once"), "yes")
            options = [e.value for e in event if e.key == "option"]
            self.assertFalse(any(e.key == "trigger" for e in options[0]))
            paid = options[1]
            facts = {("STP", "STP_pw_can_reconstruct", "yes"): True,
                     ("STP", "STP_pf_active", "yes"): True,
                     ("STP", "variable", "ADISCORD_economy_treasury"): 540}
            self.assertTrue(matches_conditions(one(paid, "trigger"), facts))
            payload = [e for e in paid if e.key == "if"]
            for changes in ({("STP", "has_completed_focus", "STP_pw_party_civil_charter"): True},
                            {("STP", "variable", "ADISCORD_economy_treasury"): 539.99},
                            {("STP", "STP_pf_active", "yes"): False}):
                self.assertEqual(list(selected_effects(payload, facts | changes)), [])


if __name__ == "__main__":
    unittest.main()
