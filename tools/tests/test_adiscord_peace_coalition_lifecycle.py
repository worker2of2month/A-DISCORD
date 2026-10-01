"""Execute treaty AST against destructive native peace and delayed capitulation.

This models observable script contracts, not the HOI4 runtime implementation.
Unknown instructions fail; unrelated presentation/economy calls are explicit stubs.
"""

from pathlib import Path
import unittest

from tools.tests.test_scripted_peace_on_actions import GenericPeaceFixture
from tools.tests.test_adiscord_stp_preparation import scalar
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]


class TreatyFixture(GenericPeaceFixture):
    def __init__(self):
        super().__init__()
        self.countries = [
            "VAL",
            "NOD",
            "STP",
            "STS",
            "BJK",
            "BLD",
            "BHG",
            "BGT",
            "BBV",
            "BCM",
            "NAM",
            "EFL",
            "AZH",
            "SLF",
            "RHM",
            "MZR",
            "SHL",
            "KYZ",
            "GLP",
            "ZZZ",
            "RUS",
            "SLA",
            "RZA",
            "MLR",
            "ERT",
            "IRT",
            "SCA",
            "SUB",
            "YPR",
            "COF",
            "TFF",
        ]
        self.flags = {t: set() for t in self.countries}
        self.subjects = {}
        self.controllers = {}
        self.majors = set()
        self.variables = {}
        self.calls = []
        self.factions = {}
        self.wars = set()
        self.effects, self.triggers = {}, {}
        self.stubs = {
            "ADISCORD_economy_mark_dirty",
            "ADISCORD_release_non_participating_minor_optimization",
            "VAL_initialize_partition_administration",
            "VAL_cancel_nam_concession",
            "VAL_settle_resource_aid",
            "VAL_install_nodrul_administration",
        }
        self.existing = set(self.countries)
        self.targets = {}
        self.capitals = {}

    def load(self, path, triggers=False):
        target = self.triggers if triggers else self.effects
        target.update(
            {
                e.key: e.value
                for e in parse_clausewitz((ROOT / path).read_text(encoding="utf-8"))
            }
        )

    def resolve(self, token, stack):
        if token == "OVERLORD":
            return self.subjects[stack[-1]]
        return super().resolve(token, stack)

    def matches(self, rows, stack):
        current = stack[-1]

        def one(e):
            k, v = e.key, e.value
            if k in ("AND", "limit"):
                return self.matches(v, stack)
            if k == "OR":
                return any(one(x) for x in v)
            if k == "NOT":
                return not any(one(x) for x in v)
            if k in self.countries or k.isdigit():
                return self.matches(v, stack + [k])
            if k.startswith("event_target:"):
                return self.matches(v, stack + [self.targets[k]])
            if k == "exists":
                return (current in self.existing) == (v == "yes")
            if k == "country_exists":
                return v in self.existing
            if k == "capital_scope":
                return self.matches(v, stack + [self.capitals[current]])
            if k == "is_controlled_by":
                return self.controllers.get(current) == v
            if k == "controller":
                return self.matches(v, stack + [self.controllers[current]])
            if k in self.triggers:
                return self.matches(self.triggers[k], stack) == (v == "yes")
            if k == "is_subject":
                return (current in self.subjects) == (v == "yes")
            if k == "is_subject_of":
                return self.subjects.get(current) == v
            if k == "is_faction_leader":
                return (current == "BJK") == (v == "yes")
            if k == "is_major":
                return (current in self.majors) == (v == "yes")
            if k == "is_in_array":
                return scalar(v, "value") in self.arrays.get(scalar(v, "array"), [])
            if k == "check_variable":
                return self.variables.get((current, scalar(v, "var")), 0) == float(
                    scalar(v, "value")
                )
            return super(TreatyFixture, self).matches([e], stack)

        return all(one(e) for e in rows)

    def execute(self, rows, stack=None):
        stack = stack or [self.root]
        current = stack[-1]
        taken = False
        for e in rows:
            k, v = e.key, e.value
            if k in ("if", "else_if", "else"):
                if k == "if":
                    taken = False
                limit = next((x.value for x in v if x.key == "limit"), [])
                if not taken and self.matches(limit, stack):
                    taken = True
                    self.execute([x for x in v if x.key != "limit"], stack)
            elif k in self.countries or k.isdigit() or k == "OVERLORD":
                self.execute(v, stack + [self.resolve(k, stack)])
            elif k in self.stubs:
                self.calls.append((k, current))
            elif k in self.effects:
                self.execute(self.effects[k], stack)
            elif k == "set_country_flag":
                self.flags[current].add(v if isinstance(v, str) else scalar(v, "flag"))
            elif k == "set_global_flag":
                self.global_flags.add(v)
            elif k == "clr_global_flag":
                self.global_flags.discard(v)
            elif k == "set_variable":
                self.variables[current, scalar(v, "var")] = float(scalar(v, "value"))
            elif k == "set_major":
                (self.majors.add if v == "yes" else self.majors.discard)(current)
            elif k == "dismantle_faction":
                self.factions.clear()
            elif k == "leave_faction":
                self.factions.pop(current, None)
            elif k == "set_autonomy":
                tag = scalar(v, "target")
                if scalar(v, "autonomy_state") == "autonomy_free":
                    self.subjects.pop(tag, None)
                else:
                    self.subjects[tag] = current
            elif k == "white_peace":
                # Even after faction dissolution, a native peace may end the merged war.
                self.wars.clear()
                self.capitulated.clear()
                self.controllers = {s: "BJK" for s in self.controllers}
            elif k in (
                "set_rule",
                "load_focus_tree",
                "remove_ideas",
                "remove_mission",
                "news_event",
            ):
                pass
            else:
                super().execute([e], stack)


class CoalitionLifecycleTests(unittest.TestCase):
    def val_northern(self):
        f = TreatyFixture()
        f.root = "VAL"
        f.load("common/scripted_effects/ADISCORD_VAL_effects.txt")
        f.load("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt", True)
        f.flags["VAL"].add("VAL_northern_coalition_campaign_active")
        for tag in ("YPR", "COF", "TFF"):
            f.flags[tag].update(
                (
                    "VAL_northern_coalition_added_major",
                    "VAL_northern_coalition_campaign_member",
                )
            )
            f.majors.add(tag)
            f.wars.add(frozenset(("VAL", tag)))
        return f

    def test_val_north_external_exit_releases_campaign_without_awards_or_ending_other_wars(
        self,
    ):
        for tag in ("YPR", "COF", "TFF"):
            for foreign_subject in (False, True):
                with self.subTest(tag=tag, foreign_subject=foreign_subject):
                    f = self.val_northern()
                    if foreign_subject:
                        f.subjects[tag] = "ZZZ"
                    else:
                        f.wars.discard(frozenset(("VAL", tag)))
                    wars = f.wars.copy()
                    subjects = f.subjects.copy()
                    f.execute(f.effects["VAL_reconcile_northern_coalition_campaign"])
                    self.assertNotIn(
                        "VAL_northern_coalition_campaign_active", f.flags["VAL"]
                    )
                    self.assertFalse(f.majors)
                    self.assertEqual(f.wars, wars)
                    self.assertEqual(f.subjects, subjects)

    def test_val_north_current_capitulation_stays_valid_but_foreign_puppet_cannot_be_awarded(
        self,
    ):
        f = self.val_northern()
        f.root = "TFF"
        f.capitulated = {"YPR", "COF"}
        f.flags["TFF"].add("VAL_northern_coalition_capitulation_reserved")
        f.wars.discard(frozenset(("VAL", "TFF")))
        ready = f.triggers["VAL_northern_coalition_campaign_victory_ready"]
        self.assertTrue(f.matches(ready, ["VAL"]))
        f.execute(f.effects["VAL_reconcile_northern_coalition_campaign"], ["VAL"])
        self.assertIn("VAL_northern_coalition_campaign_active", f.flags["VAL"])
        f.subjects["YPR"] = "ZZZ"
        self.assertFalse(f.matches(ready, ["VAL"]))

    def test_every_timed_receipt_is_reset_before_a_new_defeat_and_consumed_last(self):
        from tools.tests.test_scripted_peace_on_actions import native_hooks
        from tools.tests.test_adiscord_stp_preparation import block, walk

        source = (
            ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
        ).read_text(encoding="utf-8")
        hooks = native_hooks(source)
        transient = {
            scalar(e.value, "flag")
            for e in walk(hooks)
            if e.key == "set_country_flag"
            and isinstance(e.value, list)
            and scalar(e.value, "days")
            and "capitulation" in scalar(e.value, "flag")
        }
        immediate = block(block(hooks, "on_capitulation_immediate"), "effect")
        late = block(block(hooks, "on_capitulation"), "effect")
        self.assertGreaterEqual(len(transient), 12)
        for prefix in (immediate[:1], late[-1:]):
            f = TreatyFixture()
            f.root = "NOD"
            f.flags["NOD"] = transient | {"VAL_final_defeat_pending"}
            f.execute(prefix)
            self.assertEqual(f.flags["NOD"], {"VAL_final_defeat_pending"})

    def test_all_six_rus_targets_accept_current_native_defeat_without_full_occupation(
        self,
    ):
        for index, tag in enumerate(("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"), 1):
            f = TreatyFixture()
            f.root = tag
            f.load("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt", True)
            f.variables["RUS", "ADISCORD_vorkerland_rus_campaign_target"] = index
            f.wars = {frozenset(("RUS", tag)), frozenset(("SUB", tag))}
            f.subjects["SUB"] = "RUS"
            f.capitals[tag] = "999"
            f.controllers["999"] = "SUB"
            gate = f.triggers["ADISCORD_vorkerland_rus_current_target_capitulated"]
            self.assertFalse(f.matches(gate, ["RUS"]))
            f.flags[tag].add("ADISCORD_vorkerland_rus_capitulation_current")
            self.assertTrue(f.matches(gate, ["RUS"]), tag)
            f.root = "VAL"
            self.assertFalse(f.matches(gate, ["RUS"]), tag)
            f.root = tag
            f.wars.discard(frozenset(("SUB", tag)))
            self.assertFalse(f.matches(gate, ["RUS"]), tag)

    def northern_scenario(self):
        from tools.tests.test_adiscord_stp_civil_war import NorthernCampaignContracts

        case = NorthernCampaignContracts()
        case.setUp()
        facts, writes, callback, run = case.northern_callback_scenario()
        for tag in ("YPR", "COF", "TFF"):
            facts[(tag, "has_war_with", "NOD")] = True
        effects = {e.key: e.value for e in case.effects}
        return facts, writes, run, effects

    def test_deliberate_frontier_deferral_does_not_cancel_northern_war(self):
        facts, writes, run, effects = self.northern_scenario()
        facts["NOD", "has_war_with", "TFF"] = False
        facts["TFF", "has_war_with", "NOD"] = False
        facts["VAL", "exists", "yes"] = True
        facts["VAL", "has_country_flag", "VAL_campaign_mobilizing"] = True
        facts["NOD", "has_country_flag", "VAL_campaign_target"] = True
        facts["YPR", "has_capitulated", "no"] = False
        facts["YPR", "has_capitulated", "yes"] = True
        run(effects["STP_cw_poll_northern_campaign"], "NOD", "YPR")
        self.assertEqual(facts["NOD", "variable", "STP_cw_northern_campaign_status"], 1)
        self.assertFalse(any(k == "white_peace" for _, k, _ in writes))
        facts["VAL", "has_war_with", "NOD"] = True
        run(effects["STP_cw_release_tff_to_northern_war"], "NOD", "VAL")
        self.assertTrue(facts["TFF", "has_war_with", "NOD"])

    def test_failed_frontier_entry_after_deferral_closes_campaign_without_award(self):
        facts, writes, run, effects = self.northern_scenario()
        facts["NOD", "has_war_with", "TFF"] = False
        facts["TFF", "has_war_with", "NOD"] = False
        facts["TFF", "native_war_entry_failed", "NOD"] = True
        run(effects["STP_cw_poll_northern_campaign"], "NOD", "NOD")
        self.assertEqual(facts["NOD", "variable", "STP_cw_northern_campaign_status"], 4)
        self.assertFalse(
            any(
                k in ("puppet", "annex_country", "transfer_state") for _, k, _ in writes
            )
        )

    def test_northern_cleanup_preserves_a_preexisting_major(self):
        f = TreatyFixture()
        f.root = "VAL"
        f.load("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        f.majors = {"VAL"}
        for name in ("STP_cw_reserve_northern_major", "STP_cw_release_northern_major"):
            f.execute(f.effects[name])
        self.assertEqual(f.majors, {"VAL"})

    def bezhaysk(self, winner, neutral=None):
        f = TreatyFixture()
        f.root = winner
        tags = ["BLD", "BHG", "BGT", "BBV", "BCM", "BJK"]
        f.factions = {t: "feudal" for t in tags}
        f.wars = {frozenset((winner, t)) for t in tags}
        if neutral:
            f.factions.pop(neutral)
            f.wars.discard(frozenset((winner, neutral)))
        f.controllers = dict(zip(["31", "5", "4", "7", "9", "41"], ["VAL", "NOD"] * 3))
        f.load("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")
        return f, tags

    def test_all_members_survive_first_peace_mutating_every_war_relation(self):
        for winner in ("STP", "STS"):
            with self.subTest(winner=winner):
                f, tags = self.bezhaysk(winner)
                f.execute(
                    f.effects[f"ADISCORD_bezhaysk_settle_{winner.lower()}_victory"]
                )
                self.assertCountEqual(f.annexed, tags)
                self.assertFalse(any(f.arrays.values()))

    def test_foreign_neutral_country_is_not_included_in_partition(self):
        for winner in ("STP", "STS", "VAL"):
            f, tags = self.bezhaysk(winner, neutral="BCM")
            f.execute(f.effects[f"ADISCORD_bezhaysk_settle_{winner.lower()}_victory"])
            self.assertNotIn("BCM", f.annexed)
            self.assertNotIn("BCM", f.subjects)
            self.assertEqual(len(f.annexed or f.subjects), 5)

    def test_joint_awards_keep_every_pre_peace_capital_controller(self):
        f, tags = self.bezhaysk("VAL")
        f.wars.update(frozenset(("NOD", t)) for t in tags)
        f.execute(f.effects["ADISCORD_bezhaysk_settle_val_nod_joint_victory"])
        self.assertEqual(f.subjects, dict(zip(tags, ["VAL", "NOD"] * 3)))
        self.assertFalse(any(f.arrays.values()))

    def nam(self):
        f = TreatyFixture()
        f.root = "EFL"
        f.winner = "NAM"
        f.load("common/scripted_effects/ADISCORD_nam_resource_war_effects.txt")
        f.load("common/scripted_triggers/ADISCORD_nam_resource_war_triggers.txt", True)
        f.global_flags.add("ADISCORD_nam_resource_war_started")
        f.wars = {frozenset(("NAM", t)) for t in ("EFL", "AZH", "SLF")}
        # Observe dispatch into the final territorial outcome; its lifecycle is tested separately.
        f.stubs.add("ADISCORD_nam_resource_war_resolve_nam_victory")
        return f

    def test_nam_waits_for_both_defeats_in_either_order(self):
        for first, last in (("EFL", "AZH"), ("AZH", "EFL")):
            f = self.nam()
            for tag in (first, last):
                f.root = tag
                f.flags[tag].add("ADISCORD_nam_capitulation_reserved")
                name = "eflor" if tag == "EFL" else "azhar"
                f.execute(
                    f.effects[f"ADISCORD_nam_resource_war_mark_{name}_defeated"],
                    ["NAM"],
                )
                if tag == first:
                    self.assertFalse(f.calls)
                    self.assertTrue(f.wars)
                    f.capitulated.add(tag)
            self.assertEqual(
                f.calls, [("ADISCORD_nam_resource_war_resolve_nam_victory", "NAM")]
            )

    def test_liberated_nam_enemy_with_unexpired_receipt_blocks_joint_victory(self):
        f = self.nam()
        f.root = "AZH"
        for tag in ("EFL", "AZH"):
            f.global_flags.add(f"ADISCORD_nam_resource_war_{tag}_defeated")
            f.flags[tag].add("ADISCORD_nam_capitulation_reserved")
        f.execute(f.effects["ADISCORD_nam_resource_war_check_nam_victory"], ["NAM"])
        self.assertFalse(f.calls)

    def test_external_nam_subjugation_closes_only_remaining_wars_and_added_majors(self):
        for lost in ("NAM", "EFL", "AZH"):
            f = self.nam()
            f.root = "ZZZ"
            f.subjects[lost] = "ZZZ"
            f.majors = {"NAM", "EFL", "AZH", "ZZZ"}
            for tag in ("NAM", "EFL", "AZH"):
                f.flags[tag].add("ADISCORD_nam_resource_war_added_major")
            f.execute(f.effects["ADISCORD_nam_resource_war_close_external"])
            self.assertFalse(f.wars)
            self.assertEqual(f.majors, {"ZZZ"})
            self.assertIn("ADISCORD_nam_resource_war_resolved", f.global_flags)
            self.assertNotIn("ADISCORD_nam_resource_war_started", f.global_flags)
            self.assertFalse(f.annexed)
            before = list(f.calls)
            f.execute(f.effects["ADISCORD_nam_resource_war_close_external"])
            self.assertEqual(f.calls, before)

    def test_external_shl_subjugation_releases_principals_and_closes_allied_war(self):
        f = TreatyFixture()
        f.root = "SHL"
        f.subjects["SHL"] = "ZZZ"
        f.load("common/scripted_effects/ADISCORD_SHL_scripted_effects.txt")
        f.variables["SHL", "SHL_war_mzr"] = 1
        f.wars = {frozenset((t, "MZR")) for t in ("SHL", "KYZ", "GLP")}
        f.majors = {"SHL", "MZR", "ZZZ"}
        for tag in ("SHL", "MZR"):
            f.flags[tag].add("SHL_mzr_added_major")
        f.execute(f.effects["SHL_close_external_mzr_war"])
        self.assertFalse(f.wars)
        self.assertEqual(f.majors, {"ZZZ"})
        self.assertEqual(f.variables["SHL", "SHL_war_mzr"], 0)
        self.assertFalse(f.annexed)

    def test_stelander_restoration_does_not_capture_neutral_nod_or_other_stelander(
        self,
    ):
        f = TreatyFixture()
        f.root = "STS"
        f.load("common/scripted_effects/ADISCORD_VAL_effects.txt")
        outer = f.effects["VAL_restore_stelander_conquered_administrations"][0].value
        gate = next(e.value for e in outer if e.key == "limit")
        nod = next(e.value for e in outer if e.key == "if")
        nod_gate = next(e.value for e in nod if e.key == "limit")
        target = "event_target:VAL_settlement_country"
        f.targets[target] = "STP"
        self.assertFalse(f.matches(gate, ["VAL"]))
        f.targets[target] = "STS"
        self.assertTrue(f.matches(gate, ["VAL"]))
        self.assertFalse(f.matches(nod_gate, ["VAL"]))
        f.subjects["NOD"] = "STS"
        self.assertTrue(f.matches(nod_gate, ["VAL"]))

    def test_exile_return_accepts_only_current_receipt_or_visible_capitulation(self):
        f = TreatyFixture()
        f.root = "STS"
        f.existing.remove("STP")
        f.load("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        f.flags["NOD"].add("STP_ps_return_campaign")
        body = f.effects["STP_ps_settle_return"][0].value
        gate = next(e.value for e in body if e.key == "limit")
        self.assertFalse(f.matches(gate, ["NOD"]))
        f.flags["STS"].add("STP_ps_return_capitulation_current")
        self.assertTrue(f.matches(gate, ["NOD"]))
        f.root = "NOD"
        self.assertFalse(f.matches(gate, ["NOD"]))
        f.capitulated.add("STS")
        self.assertTrue(f.matches(gate, ["NOD"]))
        f.existing.add("STP")
        self.assertFalse(f.matches(gate, ["NOD"]))

    def test_nam_new_foreign_defeat_clears_unexpired_old_receipt(self):
        f = self.nam()
        f.root = "EFL"
        f.winner = "ZZZ"
        f.flags["EFL"].add("ADISCORD_nam_capitulation_reserved")
        source = (
            ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
        ).read_text(encoding="utf-8")
        immediate = source.split("# BEGIN nam:on_capitulation_immediate", 1)[1].split(
            "# END nam:on_capitulation_immediate", 1
        )[0]
        f.execute(parse_clausewitz(immediate))
        self.assertNotIn("ADISCORD_nam_capitulation_reserved", f.flags["EFL"])
        self.assertFalse(f.calls)


if __name__ == "__main__":
    unittest.main()
