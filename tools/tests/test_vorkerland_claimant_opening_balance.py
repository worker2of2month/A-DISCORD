from pathlib import Path
import re
import unittest

from tools.validators.validate_adiscord_vorkerland_collapse import named_block

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8-sig")


class VorkerlandClaimantOpeningBalanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        cls.initial = named_block(
            cls.effects, "ADISCORD_vorkerland_prepare_initial_combatants"
        )
        cls.wkr = named_block(cls.initial, "WKR")

    def test_claimants_have_equal_deployed_air_and_replacements(self):
        packages = {}
        for tag, oob in (("WKR", "WRK"), ("VAD", "VAD"), ("TVA", "TVA")):
            air = named_block(read(f"history/units/{oob}_vorkerland_collapse_air.txt"), "air_wings")
            setup = (
                named_block(self.effects, "ADISCORD_vorkerland_setup_tva")
                if tag == "TVA"
                else named_block(self.initial, tag)
            )
            package = {}
            for equipment in ("ADISCORD_fighter_airframe_2163", "ADISCORD_cas_airframe_2170"):
                deployed = sum(int(amount) for amount in re.findall(
                    rf'{equipment}\s*=\s*\{{\s*owner\s*=\s*"{tag}"\s+amount\s*=\s*(\d+)', air
                ))
                reserve = sum(int(amount) for amount in re.findall(
                    rf'type\s*=\s*{equipment}\s+amount\s*=\s*(\d+)\s+producer\s*=\s*{tag}', setup
                ))
                self.assertGreater(deployed, 0)
                package[equipment] = (deployed, reserve)
            packages[tag] = package
        self.assertEqual(packages["WKR"], packages["VAD"])
        self.assertEqual(packages["WKR"], packages["TVA"])

    def test_wkr_opening_air_reserve_and_fuel_are_bounded(self):
        self.assertIn(
            "type = ADISCORD_fighter_airframe_2163 amount = 30 producer = WKR", self.wkr
        )
        self.assertIn(
            "type = ADISCORD_cas_airframe_2170 amount = 15 producer = WKR", self.wkr
        )
        self.assertIn("add_fuel = 10000", self.wkr)
        self.assertNotIn("add_fuel = 15000", self.wkr)

    def test_wkr_opens_with_one_ready_mobile_group(self):
        mobile = re.search(
            r'division = "name = \\"1st Workerland Mobile Group\\".*?"\s*owner = WKR\s*count = (\d+)',
            self.wkr,
            re.S,
        )
        self.assertIsNotNone(mobile)
        self.assertEqual(mobile.group(1), "1")

    def test_balance_pass_keeps_wkr_home_guard_bounded(self):
        home = named_block(self.effects, "ADISCORD_vorkerland_ensure_wkr_home_guard")
        self.assertIn("add_manpower = 12000", home)
        self.assertIn("amount = 960 producer = WKR", home)
        self.assertEqual(home.count("count = 3"), 2)

    def test_tva_has_one_mobile_group_without_losing_front_coverage(self):
        oob = read("history/units/TVA_vorkerland_collapse.txt")
        self.assertEqual(oob.count('division_template = "TVA Mobile Test Group"'), 1)
        self.assertEqual(oob.count('division_template = "TVA Collapse Militia"'), 18)

    def test_initiative_roll_covers_all_claimants_equally_and_only_once(self):
        effect = named_block(self.effects, "ADISCORD_vorkerland_roll_central_initiative")
        self.assertTrue(effect, "The central war has no campaign variation")
        guard = " ".join(named_block(effect, "limit").split())
        self.assertIn("NOT = { has_global_flag = ADISCORD_vorkerland_central_initiative_rolled }", guard)
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(f"{tag} = {{ exists = yes is_ai = yes", guard)
        self.assertIn("WRK = { exists = yes is_ai = no }", guard)
        roll = named_block(effect, "random_list")
        awards = re.findall(
            r'(\d+)\s*=\s*\{\s*(WKR|VAD|TVA)\s*=\s*\{\s*add_timed_idea\s*=\s*\{\s*idea\s*=\s*ADISCORD_vorkerland_central_initiative\s+days\s*=\s*(\d+)',
            roll,
        )
        self.assertEqual(len(awards), 3)
        self.assertEqual({tag for _, tag, _ in awards}, {"WKR", "VAD", "TVA"})
        self.assertEqual(len({weight for weight, _, _ in awards}), 1)
        self.assertTrue(all(int(weight) > 0 and 0 < int(days) <= 730 for weight, _, days in awards))
        events = read("events/ADISCORD_vorkerland_events.txt")
        self.assertEqual(events.count("ADISCORD_vorkerland_roll_central_initiative = yes"), 1)

    def test_initiative_is_limited_to_peers_and_removed_at_settlement(self):
        idea = named_block(read("common/ideas/ADISCORD_vorkerland_ideas.txt"),
                           "ADISCORD_vorkerland_central_initiative")
        self.assertTrue(idea)
        self.assertEqual(re.findall(r"targeted_modifier\s*=\s*\{\s*tag\s*=\s*(\w+)", idea),
                         ["WKR", "VAD", "TVA"])
        cancel = " ".join(named_block(idea, "cancel").split())
        for token in ("is_ai = no", "has_capitulated = yes",
                      "has_global_flag = ADISCORD_vorkerland_collapse_finished"):
            self.assertIn(token, cancel)
        for tag in ("WKR", "VAD", "TVA", "WRK"):
            self.assertIn(f"{tag} = {{ exists = yes is_ai = no }}", cancel)
        cleanup = named_block(self.effects, "ADISCORD_vorkerland_clear_claimant_war_modifiers")
        self.assertIn("remove_ideas = ADISCORD_vorkerland_central_initiative", cleanup)

    def test_tva_permanent_spirits_do_not_outscale_peer_claimants(self):
        ideas = read("common/ideas/ADISCORD_vorkerland_ideas.txt")

        def modifier(idea, key):
            block = named_block(named_block(ideas, idea), "modifier")
            match = re.search(rf"\b{key}\s*=\s*(-?[\d.]+)", block)
            return float(match.group(1)) if match else 0.0

        tva = ("ADISCORD_vorkerland_tva_field_directorate_3",
               "ADISCORD_vorkerland_tva_ideological_fanaticism")
        vad = ("ADISCORD_vorkerland_vad_restoration_war_cabinet_2",)
        for key in ("army_attack_factor", "army_org_factor", "breakthrough_factor"):
            self.assertLessEqual(
                sum(modifier(idea, key) for idea in tva),
                sum(modifier(idea, key) for idea in vad) + 0.01,
                key,
            )
        for function in ("ADISCORD_vorkerland_prepare_conflict_country",
                         "ADISCORD_vorkerland_finalize_conflict_spirits"):
            branch = re.search(
                r"limit = \{ tag = TVA \}(.*?)\n\t\}", named_block(self.effects, function), re.S
            )
            self.assertIsNotNone(branch, function)
            self.assertNotIn("ADISCORD_vorkerland_mobilized_periphery", branch.group(1))

    def test_tva_repeatable_war_decisions_match_peer_cadence(self):
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        for decision, days in (
            ("ADISCORD_vorkerland_tva_reroute_city_grid", 40),
            ("ADISCORD_vorkerland_tva_deploy_field_laboratories", 45),
            ("ADISCORD_vorkerland_tva_raise_technical_battalions", 120),
            ("ADISCORD_vorkerland_tva_disrupt_enemy_logistics", 60),
        ):
            self.assertIn(f"days_re_enable = {days}", named_block(decisions, decision))

    def test_central_minor_spheres_partition_the_districts_evenly(self):
        triggers = read("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        sphere = named_block(triggers, "ADISCORD_vorkerland_central_minor_is_open_to_ROOT")
        owners = {}
        for minors, claimant in re.findall(
            r"OR = \{ ((?:tag = \w+ )+)\}\s*OR = \{\s*ROOT = \{ (?:OR = \{ )?tag = (\w+)", sphere
        ):
            for minor in re.findall(r"tag = (\w+)", minors):
                self.assertNotIn(minor, owners)
                owners[minor] = claimant
        self.assertEqual(set(owners), {"EYR", "EGC", "RIV", "REV", "YOR", "NDN", "SWB", "VHV", "OSV"})
        for claimant in ("WKR", "VAD", "TVA"):
            self.assertIn(f"NOT = {{ {claimant} = {{ ADISCORD_vorkerland_is_live_claimant = yes }} }}", sphere)

        from tools.lib.adiscord_vorkerland_theatre_manifest import (
            VORKERLAND_THEATRE_PACKAGE_TOTALS as totals,
        )
        shares = {tag: totals[tag] for tag in ("WKR", "VAD", "TVA")}
        for minor, claimant in owners.items():
            shares[claimant] += totals[minor]
        self.assertLessEqual(max(shares.values()) - min(shares.values()), 10, shares)

        viability = named_block(triggers, "ADISCORD_vorkerland_has_adjacent_viable_central_minor")
        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        wave = named_block(decisions, "ADISCORD_vorkerland_launch_central_minor_wave")
        for block in (viability, named_block(wave, "complete_effect")):
            self.assertEqual(block.count("ADISCORD_vorkerland_central_minor_is_open_to_ROOT = yes"), 9)

    def test_comeback_pressure_follows_the_territorial_leader(self):
        coalition = named_block(self.effects, "ADISCORD_vorkerland_refresh_claimant_coalition")
        self.assertEqual(coalition.count("ADISCORD_vorkerland_is_central_control_leader = yes"), 3)
        self.assertNotIn("ADISCORD_vorkerland_legitimacy_leader", coalition)
        join = named_block(
            named_block(read("common/decisions/ADISCORD_vorkerland_decisions.txt"),
                        "ADISCORD_vorkerland_join_claimant_coalition"),
            "ai_will_do",
        )
        self.assertIn("factor = 0.25 FROM = { ADISCORD_vorkerland_is_central_control_leader = yes }", join)
        self.assertIn("factor = 2 FROM = { ADISCORD_vorkerland_is_central_control_laggard = yes }", join)

    def test_theatre_package_is_not_rewritten_as_a_balance_shortcut(self):
        manifest = read("tools/lib/adiscord_vorkerland_theatre_manifest.py")
        self.assertIn('"WKR": 62', manifest)
        self.assertIn('"VAD": 66', manifest)
        self.assertIn('"TVA": 77', manifest)


if __name__ == "__main__":
    unittest.main()
