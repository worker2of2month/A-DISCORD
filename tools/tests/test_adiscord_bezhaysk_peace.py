from pathlib import Path
import unittest

from tools.lib.on_actions import read_scripted_peace
from tools.tests.test_scripted_peace_on_actions import GenericPeaceFixture
from tools.tests.test_adiscord_stp_preparation import scalar
from tools.tests.test_adiscord_val_refugees import load

ROOT = Path(__file__).resolve().parents[2]
REALM = ("BLD", "BHG", "BGT", "BBV", "BCM", "BJK")
ADMIN_FLAG = "ADISCORD_bezhaysk_val_administration"
GORNIN = "STP_ilya_gornin"


class BezhayskUnificationFixture(GenericPeaceFixture):
    """Execute the merge after diplomacy is settled; annex may leave state 999."""

    def __init__(self, val_awards=REALM, gornin_home="STP"):
        super().__init__()
        self.countries = ["VAL", "NOD", "COF", "STP", "STS", *REALM]
        self.owners = dict(zip((31, 5, 4, 7, 9, 41), REALM))
        self.owners.update({6: "BLD", 999: "BLD", 14: "COF"})
        self.controllers = dict(self.owners)
        self.cores = {state: {owner} for state, owner in self.owners.items()}
        self.overlords = {tag: "VAL" if tag in val_awards else "NOD" for tag in REALM}
        self.overlords["COF"] = "VAL"
        self.flags = {
            tag: {ADMIN_FLAG} if tag in val_awards else set()
            for tag in self.countries
        }
        self.troops = {tag: 10 for tag in self.countries}
        self.targets = {}
        self.cosmetics = {}
        self.dirty = set()
        self.arrays = {"ADISCORD_bezhaysk_settlement_members": list(REALM)}
        self.gornin_home = gornin_home
        self.gornin_roles = {"steland_liberationism"}
        self.leaders = {}
        self.politics = {}
        self.effects = load("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")

    def resolve(self, token, stack):
        if token.startswith("event_target:"):
            return self.targets[token.split(":", 1)[1]]
        return super().resolve(token, stack)

    def matches(self, rows, stack):
        current = stack[-1]
        for row in rows:
            key, value = row.key, row.value
            if key == "OR":
                result = any(self.matches([child], stack) for child in value)
            elif key == "NOT":
                result = not any(self.matches([child], stack) for child in value)
            elif key in (*self.countries, GORNIN) or key.startswith("event_target:"):
                result = self.matches(value, stack + [self.resolve(key, stack)])
            elif key == "has_character":
                result = value == GORNIN and self.gornin_home == current
            elif key == "has_ideology":
                result = value in self.gornin_roles
            elif key == "is_subject_of":
                result = self.overlords.get(current) == self.resolve(value, stack)
            elif key == "is_in_array":
                result = scalar(value, "value") in self.arrays[scalar(value, "array")]
            elif key == "is_core_of":
                result = self.resolve(value, stack) in self.cores[current]
            elif key == "is_controlled_by":
                result = self.controllers[current] == self.resolve(value, stack)
            elif key == "controller":
                result = self.matches(value, stack + [self.controllers[current]])
            else:
                result = super().matches([row], stack)
            if not result:
                return False
        return True

    def execute(self, rows, stack=None):
        stack = stack or ["VAL"]
        current = stack[-1]
        taken = False
        for row in rows:
            key, value = row.key, row.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                guard = next((child.value for child in value if child.key == "limit"), [])
                if not taken and self.matches(guard, stack):
                    taken = True
                    self.execute([child for child in value if child.key != "limit"], stack)
            elif key in (*self.countries, GORNIN) or key.startswith("event_target:"):
                self.execute(value, stack + [self.resolve(key, stack)])
            elif key in self.effects:
                self.execute(self.effects[key], stack)
            elif key == "save_event_target_as":
                self.targets[value] = current
            elif key == "add_core_of":
                self.cores[current].add(self.resolve(value, stack))
            elif key == "set_state_controller_to":
                self.controllers[current] = self.resolve(value, stack)
            elif key == "annex_country":
                target = self.resolve(scalar(value, "target"), stack)
                if scalar(value, "transfer_troops") == "yes":
                    self.troops[current] += self.troops[target]
                    self.troops[target] = 0
                super().execute([row], stack)
                for state, owner in self.owners.items():
                    if owner == current and self.controllers[state] == target:
                        self.controllers[state] = current
            elif key == "set_cosmetic_tag":
                self.cosmetics[current] = value
            elif key == "set_country_flag":
                self.flags[current].add(value)
            elif key == "ADISCORD_economy_mark_dirty":
                self.dirty.add(current)
            elif key == "remove_country_leader_role":
                self.gornin_roles.discard(scalar(value, "ideology"))
            elif key == "set_nationality":
                assert scalar(value, "character") == GORNIN
                assert self.gornin_home == current
                assert not self.gornin_roles, "An active office prevents native transfer"
                self.gornin_home = self.resolve(scalar(value, "target_country"), stack)
            elif key == "recruit_character":
                raise AssertionError("Character recruitment is only valid in history")
            elif key == "add_country_leader_role":
                assert scalar(value, "character") == GORNIN
                assert self.gornin_home == current
                role = next(child.value for child in value if child.key == "country_leader")
                self.gornin_roles.add(scalar(role, "ideology"))
            elif key == "promote_character":
                assert scalar(value, "character") == GORNIN
                assert self.gornin_home == current
                assert scalar(value, "ideology") in self.gornin_roles
                self.leaders[current] = GORNIN
            elif key == "set_politics":
                self.politics[current] = scalar(value, "ruling_party")
            else:
                super().execute([row], stack)

    def run(self):
        self.execute(self.effects["ADISCORD_bezhaysk_unify_val_administration"])


class BezhayskUnificationTests(unittest.TestCase):
    def test_single_victory_preserves_all_land_cores_and_troops_in_one_client(self):
        model = BezhayskUnificationFixture()
        model.run()
        for state in (31, 5, 4, 7, 9, 41, 6, 999):
            self.assertEqual(model.owners[state], "BJK")
            self.assertEqual(model.controllers[state], "BJK")
            self.assertIn("BJK", model.cores[state])
        self.assertEqual(model.troops["BJK"], 60)
        self.assertEqual(model.overlords["BJK"], "VAL")
        self.assertEqual(model.cosmetics, {"BJK": "BJK_VAL_administration"})
        self.assertIn("BJK", model.dirty)
        self.assertEqual(model.owners[14], "COF")

    def test_joint_victory_preserves_nodrul_awards_when_it_gets_the_capital(self):
        model = BezhayskUnificationFixture(val_awards=("BLD", "BHG", "BGT"))
        model.run()
        self.assertEqual({model.owners[state] for state in (31, 5, 4, 6, 999)}, {"BLD"})
        self.assertEqual(model.troops["BLD"], 30)
        for state, tag in ((41, "BJK"), (7, "BBV"), (9, "BCM")):
            self.assertEqual(model.owners[state], tag)
            self.assertEqual(model.overlords[tag], "NOD")
            self.assertEqual(model.troops[tag], 10)
        self.assertEqual(model.cosmetics, {"BLD": "BJK_VAL_administration"})

    def test_no_val_awards_does_not_rename_or_annex_any_country(self):
        model = BezhayskUnificationFixture(val_awards=())
        before = dict(model.owners)
        model.run()
        self.assertEqual(model.owners, before)
        self.assertEqual(model.cosmetics, {})
        self.assertEqual(model.annexed, [])

    def test_unrelated_occupation_and_noncore_land_keep_their_status(self):
        model = BezhayskUnificationFixture()
        model.controllers[999] = "NOD"
        model.cores[999] = {"COF"}
        model.run()
        self.assertEqual(model.owners[999], "BJK")
        self.assertEqual(model.controllers[999], "NOD")
        self.assertEqual(model.cores[999], {"COF"})

    def test_gornin_transfers_from_either_successor_and_leads_the_awarded_client(self):
        for donor in ("STP", "STS"):
            for awards, recipient in ((REALM, "BJK"), (("BLD", "BHG"), "BLD")):
                with self.subTest(donor=donor, recipient=recipient):
                    model = BezhayskUnificationFixture(awards, gornin_home=donor)
                    model.run()
                    self.assertEqual(model.gornin_home, recipient)
                    self.assertEqual(model.leaders, {recipient: GORNIN})
                    self.assertEqual(model.politics[recipient], "etatism")

    def test_missing_gornin_does_not_interrupt_settlement_or_recreate_him(self):
        model = BezhayskUnificationFixture(gornin_home=None)
        model.run()
        self.assertIsNone(model.gornin_home)
        self.assertEqual(model.leaders, {})
        self.assertEqual(model.troops["BJK"], 60)
        self.assertEqual(model.cosmetics, {"BJK": "BJK_VAL_administration"})
        self.assertIn("BJK", model.dirty)

    def test_without_val_land_gornin_stays_in_his_country(self):
        model = BezhayskUnificationFixture(val_awards=(), gornin_home="STS")
        model.run()
        self.assertEqual(model.gornin_home, "STS")
        self.assertEqual(model.leaders, {})


class BezhayskStelanderFixture(BezhayskUnificationFixture):
    """Run direct annexation with a subject absent from the victor's war."""

    def __init__(self, winner="STS"):
        super().__init__()
        self.winner = winner
        self.root = "BJK"
        self.overlords = {tag: "BJK" for tag in REALM if tag != "BJK"}
        self.factions = {tag: "bezhaysk" for tag in REALM}
        self.wars = {frozenset((winner, tag)) for tag in REALM if tag != "BGT"}
        self.wars.add(frozenset((winner, "NOD")))
        self.owners = dict(zip((31, 5, 4, 7, 9, 41), REALM))
        self.owners[10] = "NOD"
        self.controllers = dict(self.owners)
        self.flags[winner].add("ADISCORD_bezhaysk_campaign_active")

    def run(self):
        self.execute(
            self.effects[f"ADISCORD_bezhaysk_settle_{self.winner.lower()}_victory"],
            [self.winner],
        )


class BezhayskStelanderTests(unittest.TestCase):
    def test_unjoined_subject_is_annexed_while_nodrul_war_continues(self):
        for winner in ("STS", "STP"):
            with self.subTest(winner=winner):
                model = BezhayskStelanderFixture(winner)
                model.run()
                self.assertEqual(model.owners[4], winner)
                self.assertEqual(model.controllers[4], winner)
                self.assertEqual(set(model.annexed), set(REALM))
                self.assertIn(frozenset((winner, "NOD")), model.wars)
                self.assertEqual(model.owners[10], "NOD")
                self.assertNotIn("ADISCORD_bezhaysk_campaign_active", model.flags[winner])

    def test_unjoined_faction_member_is_not_treated_as_a_subject(self):
        for winner in ("STS", "STP"):
            with self.subTest(winner=winner):
                model = BezhayskStelanderFixture(winner)
                del model.overlords["BGT"]
                model.run()
                self.assertEqual(model.owners[4], "BGT")
                self.assertNotIn("BGT", model.annexed)

    def test_nodrul_fighting_bezhaysk_does_not_leave_an_unjoined_vassal(self):
        model = BezhayskStelanderFixture()
        model.wars.discard(frozenset(("STS", "NOD")))
        model.wars.update(frozenset(("NOD", tag)) for tag in REALM)
        model.run()
        self.assertEqual(model.owners[4], "STS")
        self.assertEqual(model.controllers[4], "STS")
        self.assertEqual(model.owners[10], "NOD")
        self.assertEqual(set(model.annexed), set(REALM))

    def test_fighting_faction_member_is_included_without_subject_status(self):
        model = BezhayskStelanderFixture()
        del model.overlords["BGT"]
        model.wars.add(frozenset(("STS", "BGT")))
        model.run()
        self.assertEqual(model.owners[4], "STS")

    def test_nodrul_war_does_not_make_a_detached_country_part_of_the_settlement(self):
        model = BezhayskStelanderFixture()
        model.overlords["BGT"] = "NOD"
        del model.factions["BGT"]
        model.wars.add(frozenset(("STS", "BGT")))
        model.run()
        self.assertEqual(model.owners[4], "BGT")
        self.assertIn(frozenset(("STS", "BGT")), model.wars)


class BezhayskPeaceTests(unittest.TestCase):
    def read(self, path: str) -> str:
        return (ROOT / path).read_text(encoding="utf-8-sig")

    def test_val_explicitly_calls_every_current_vassal_on_the_defensive_side(self):
        effect = load("common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt")[
            "ADISCORD_bezhaysk_join_val_campaign"
        ]
        self.assertEqual({e.key for e in effect}, {"BLD", "BHG", "BGT", "BBV", "BCM"})
        for scope in effect:
            body = scope.value[0].value
            war = next(e.value for e in body if e.key == "add_to_war")
            self.assertEqual(scalar(war, "targeted_alliance"), "BJK")
            self.assertEqual(scalar(war, "enemy"), "VAL")
        from tools.builders.build_adiscord_val_operations_map import (
            BJK_STATES,
            MAP_TAGS,
        )

        self.assertLessEqual({4, 5, 6, 7, 9, 31, 41}, set(BJK_STATES))
        self.assertLessEqual({"BJK", "BLD", "BHG", "BGT", "BBV", "BCM"}, set(MAP_TAGS))

    def test_both_campaigns_record_their_authored_war(self) -> None:
        stp = self.read("events/ADISCORD_STP_events.txt")
        val = self.read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", stp)
        self.assertIn("set_country_flag = ADISCORD_bezhaysk_campaign_active", val)

    def test_capitulation_router_uses_runtime_receipts_not_focus_history(self) -> None:
        source = self.read(
            "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
        )
        immediate = source.split("# BEGIN bezhaysk:on_capitulation_immediate", 1)[
            1
        ].split("# END bezhaysk:on_capitulation_immediate", 1)[0]
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_campaign_active", immediate)
        for focus_id in (
            "VAL_Bezhaysk_Operation",
            "STP_pw_party_bezhaysk_campaign",
            "STP_pw_take_bezhaysk",
        ):
            self.assertNotIn(f"has_completed_focus = {focus_id}", immediate)

        late = source.split("# BEGIN bezhaysk:on_capitulation\n", 1)[1].split(
            "# END bezhaysk:on_capitulation", 1
        )[0]
        self.assertIn("has_country_flag = ADISCORD_bezhaysk_capitulation_pending", late)
        self.assertNotIn("has_war_with", late)
        self.assertNotIn("has_completed_focus", late)
        self.assertNotIn("is_subject_of", late)
        self.assertNotIn("is_in_faction_with", late)

    def test_capitulation_router_handles_all_authored_routes(self) -> None:
        router = read_scripted_peace(
            ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt",
            "bezhaysk",
        )
        for effect in (
            "ADISCORD_bezhaysk_settle_sts_victory = yes",
            "ADISCORD_bezhaysk_settle_stp_victory = yes",
            "ADISCORD_bezhaysk_settle_val_victory = yes",
            "ADISCORD_bezhaysk_settle_val_nod_joint_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_val_victory = yes",
            "ADISCORD_bezhaysk_settle_forest_nod_victory = yes",
        ):
            self.assertIn(effect, router)
        self.assertEqual(router.count("set_global_flag = skip_default_capitulation"), 7)

    def test_settlement_covers_the_feudal_bloc(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", effects)
        self.assertIn("white_peace = BJK", effects)

    def test_party_has_an_authored_bezhaysk_settlement(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        start = effects.index("ADISCORD_bezhaysk_settle_stp_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_val_victory = {")
        settlement = effects[start:end]
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(
                f"annex_country = {{ target = {tag} transfer_troops = no }}", settlement
            )
        self.assertIn("set_country_flag = STP_pw_party_bezhaysk_victory", settlement)

    def test_kefreyt_uses_contract_clients_instead_of_direct_annexation(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        start = effects.index("ADISCORD_bezhaysk_settle_val_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        settlement = effects[start:end]
        self.assertNotIn("annex_country", settlement)
        self.assertIn(
            "ADISCORD_bezhaysk_unify_val_administration = yes", settlement
        )

    def test_joint_kefreyt_nodrul_settlement_is_prioritized(self) -> None:
        router = read_scripted_peace(
            ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt",
            "bezhaysk",
        )
        joint = router.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = yes")
        single_val = router.index("ADISCORD_bezhaysk_settle_val_victory = yes")
        self.assertLess(joint, single_val)
        self.assertIn("has_war_together_with = NOD", router)
        self.assertIn("ADISCORD_bezhaysk_joint_default_nod", router)
        self.assertIn("ADISCORD_bezhaysk_joint_default_val", router)

    def test_joint_settlement_keeps_feudal_holdings_as_client_states(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        start = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        joint = effects[start:]
        self.assertNotIn("annex_country", joint)
        for tag in ("BJK", "BLD", "BHG", "BGT", "BBV", "BCM"):
            self.assertIn(f"target = {tag}", joint)
        for capital in (41, 31, 5, 4, 7, 9):
            self.assertIn(f"{capital} = {{ controller =", joint)
        self.assertIn("autonomy_state = autonomy_VAL_contract_administration", joint)
        self.assertIn("autonomy_state = autonomy_NOD_protected_administration", joint)
        self.assertIn("ADISCORD_bezhaysk_unify_val_administration = yes", joint)
        self.assertGreaterEqual(
            joint.count("set_country_flag = ADISCORD_bezhaysk_joint_settlement"), 2
        )

    def test_joint_award_is_selected_before_white_peace(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        start = effects.index("ADISCORD_bezhaysk_settle_val_nod_joint_victory = {")
        end = effects.index("ADISCORD_bezhaysk_settle_forest_val_victory = {")
        joint = effects[start:end]
        for tag, capital in (
            ("BLD", 31),
            ("BHG", 5),
            ("BGT", 4),
            ("BBV", 7),
            ("BCM", 9),
            ("BJK", 41),
        ):
            package_start = joint.index(f"limit = {{ {tag} = {{ exists = yes")
            package = joint[package_start:]
            controller = package.index(f"{capital} = {{ controller =")
            first_peace = package.index("white_peace =")
            self.assertLess(controller, first_peace, tag)

    def test_feudal_faction_is_dismantled_before_new_overlords(self) -> None:
        effects = self.read(
            "common/scripted_effects/ADISCORD_bezhaysk_peace_effects.txt"
        )
        for name in (
            "ADISCORD_bezhaysk_settle_val_victory = {",
            "ADISCORD_bezhaysk_settle_val_nod_joint_victory = {",
        ):
            start = effects.index(name)
            end = effects.find("\nADISCORD_", start + len(name))
            block = effects[start:] if end == -1 else effects[start:end]
            self.assertIn("dismantle_faction = yes", block)
            self.assertLess(
                block.index("dismantle_faction = yes"), block.index("set_autonomy = {")
            )

    def test_nodrul_has_a_distinct_protected_administration_level(self) -> None:
        autonomy = self.read("common/autonomous_states/ADISCORD_contract_clients.txt")
        self.assertIn("id = autonomy_NOD_protected_administration", autonomy)
        self.assertIn(
            "allowed_levels_filter = { autonomy_NOD_protected_administration }",
            autonomy,
        )
        self.assertIn("use_overlord_color = no", autonomy)

    def test_grandfather_lishay_can_be_taken_in_a_separate_late_campaign(self) -> None:
        state = self.read("history/states/14-Flaem-Prana.txt")
        decisions = self.read("common/decisions/ADISCORD_bezhaysk_decisions.txt")
        val_decisions = self.read("common/decisions/ADISCORD_VAL_decisions.txt")
        self.assertIn("victory_points = { 75 5 }", state)
        self.assertIn("owner = COF", state)
        self.assertIn("ADISCORD_bezhaysk_subjugate_forest_val", val_decisions)
        self.assertNotIn("ADISCORD_bezhaysk_subjugate_forest_val", decisions)
        self.assertIn("ADISCORD_bezhaysk_subjugate_forest_nod", decisions)
        self.assertNotIn("ADISCORD_bezhaysk_subjugate_forest_nod", val_decisions)
        self.assertEqual(
            (decisions + val_decisions).count(
                "declare_war_on = { target = COF type = annex_everything }"
            ),
            2,
        )

    def test_bezhaysk_starting_faction_uses_real_hachoesia_tag(self) -> None:
        history = self.read("history/countries/BJK - Besjaysk.txt")
        self.assertIn("add_to_faction = BHG", history)
        self.assertNotIn("add_to_faction = BHD", history)


if __name__ == "__main__":
    unittest.main()
