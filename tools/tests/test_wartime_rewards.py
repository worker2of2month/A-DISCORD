"""Campaign-specific activation, payment and expiry of prepared military rewards."""

from dataclasses import replace
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_stp_party_route import one
from tools.tests.test_adiscord_stp_preparation import matches_conditions, selected_effects
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node.value, list):
            yield from walk(node.value)


def definitions(relative):
    return parse_clausewitz(read(relative))


class WartimeRewardsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.decisions = {}
        for family in ("STP", "vorkerland", "RUS", "VAL"):
            for category in definitions(f"common/decisions/ADISCORD_{family}_decisions.txt"):
                for decision in category.value:
                    cls.decisions[decision.key] = decision.value
        cls.ideas = {}
        for family in ("STP_civil_war", "vorkerland", "RUS", "VAL_rework"):
            for category in one(definitions(f"common/ideas/ADISCORD_{family}_ideas.txt"), "ideas"):
                cls.ideas.update({node.key: node.value for node in category.value})
        cls.triggers = {
            node.key: node.value
            for node in definitions("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        }
        cls.effects = definitions("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")

    def expand_plan_triggers(self, nodes):
        result = []
        for node in nodes:
            if node.key in self.triggers and isinstance(node.value, str):
                self.assertIn(node.value, ("yes", "no"))
                conjunction = replace(
                    node,
                    key="AND",
                    value=self.expand_plan_triggers(self.triggers[node.key]),
                )
                result.append(conjunction if node.value == "yes" else replace(
                    node, key="NOT", value=[conjunction]
                ))
            elif isinstance(node.value, list):
                result.append(replace(node, value=self.expand_plan_triggers(node.value)))
            else:
                result.append(node)
        return result

    def facts(self, tag, enemy, focus):
        countries = ("WKR", "VAD", "TVA", "SRA", "CSL", "SOL", "STS", "VAL", "NOD", "RUS")
        facts = {
            (tag, "has_completed_focus", focus): True,
            (tag, "has_capitulated", "no"): True,
            (tag, "has_global_flag", "ADISCORD_vorkerland_collapse_wars_started"): True,
        }
        for country in countries:
            facts[(tag, "has_war_with", country)] = country == enemy
            facts[(country, "tag", country)] = True
        return facts

    def test_focus_plans_keep_full_duration_for_their_own_war(self):
        plans = {
            key: value for key, value in self.decisions.items()
            if key.endswith("_activate_plan") and key != "WKR_solar_counter_activate_plan"
        }
        self.assertEqual(len(plans), 33)
        native_focuses = {}
        for filename in (
            "ADISCORD_STP_civil_war.txt", "ADISCORD_Vorkerland_wkr.txt",
            "ADISCORD_Vorkerland_vad.txt", "ADISCORD_Vorkerland_tva.txt",
        ):
            for node in walk(definitions("common/national_focus/" + filename)):
                if node.key == "focus" and isinstance(node.value, list):
                    native_focuses[one(node.value, "id")] = node.value
        for decision_id, decision in plans.items():
            focus = decision_id.removesuffix("_activate_plan")
            tag = "STS" if focus.startswith("STP_") else focus[:3]
            enemy = "WKR" if tag in ("VAD", "TVA") else "VAD"
            if focus == "VAD_map_the_solar_corridors":
                enemy = "SRA"
            elif tag == "STS":
                enemy = "VAL" if focus.endswith("val_defense") else "NOD"
            timed = [node for node in walk(decision) if node.key == "add_timed_idea"]
            self.assertEqual(len(timed), 1)
            idea = one(timed[0].value, "idea")
            self.assertEqual(one(decision, "cost"), "0")
            self.assertEqual(one(decision, "fire_only_once"), "yes")
            reward = one(native_focuses[focus], "completion_reward")
            self.assertFalse(any(node.key == "add_timed_idea" for node in walk(reward)))
            self.assertIn(decision_id, [node.value for node in walk(reward) if node.key == "unlock_decision_tooltip"])
            for actual_enemy, expected in ((None, False), ("RUS", False), (enemy, True)):
                facts = self.facts(tag, actual_enemy, focus)
                with self.subTest(plan=decision_id, enemy=actual_enemy):
                    self.assertTrue(matches_conditions(one(decision, "visible"), facts, tag))
                    self.assertEqual(matches_conditions(
                        self.expand_plan_triggers(one(decision, "available")), facts, tag
                    ), expected)
                    effects = list(selected_effects(
                        self.expand_plan_triggers(one(decision, "complete_effect")), facts, tag
                    ))
                    self.assertEqual(sum(node.key == "add_timed_idea" for _, node in effects), int(expected))
                    self.assertEqual(matches_conditions(
                        self.expand_plan_triggers(one(self.ideas[idea], "cancel")), facts, tag
                    ), not expected)
            facts = self.facts(tag, enemy, focus)
            facts[(tag, "has_idea", idea)] = True
            self.assertFalse(matches_conditions(
                self.expand_plan_triggers(one(decision, "available")), facts, tag
            ))
            self.assertEqual(list(selected_effects(
                self.expand_plan_triggers(one(decision, "complete_effect")), facts, tag
            )), [])
            facts[(tag, "has_idea", idea)] = False
            facts[(tag, "has_completed_focus", focus)] = False
            self.assertFalse(matches_conditions(one(decision, "visible"), facts, tag))
            self.assertEqual(list(selected_effects(
                self.expand_plan_triggers(one(decision, "complete_effect")), facts, tag
            )), [])

    def test_campaign_readiness_is_untimed_and_consumed_once(self):
        cases = (
            ("STS", "VAL", "STP_pc_val_campaign_ready", "STP_pc_val_campaign_plan", 90, "STP_pc_apply_prepared_campaigns"),
            ("STS", "NOD", "STP_pc_nod_campaign_ready", "STP_pc_nod_campaign_plan", 90, "STP_pc_apply_prepared_campaigns"),
            ("VAL", "STS", "STP_pc_campaign_defence_ready", "STP_pc_campaign_defence", 70, "STP_pc_apply_campaign_defence"),
            ("NOD", "STS", "STP_pc_campaign_defence_ready", "STP_pc_campaign_defence", 70, "STP_pc_apply_campaign_defence"),
        )
        for tag, enemy, ready, active, days, effect_id in cases:
            with self.subTest(tag=tag, enemy=enemy):
                self.assertEqual(one(self.ideas[ready], "modifier"), [])
                if tag == "STS":
                    preparation = self.decisions[f"STP_pw_prepare_{enemy.lower()}_campaign"]
                    grants = [node for node in walk(one(preparation, "remove_effect")) if node.key == "add_ideas"]
                    self.assertEqual([node.value for node in grants], [ready])
                    self.assertFalse(any(node.key == "add_timed_idea" for node in walk(preparation)))
                effect = one(self.effects, effect_id)
                facts = {(tag, "has_idea", ready): True}
                self.assertEqual(list(selected_effects(effect, facts, tag)), [])
                facts[(tag, "has_war_with", enemy)] = True
                grants = []
                for _, node in selected_effects(effect, facts, tag):
                    if node.key == "remove_ideas":
                        facts[(tag, "has_idea", node.value)] = False
                    elif node.key == "add_timed_idea":
                        grants.append((one(node.value, "idea"), int(one(node.value, "days"))))
                self.assertIn((active, days), grants)
                self.assertEqual(list(selected_effects(effect, facts, tag)), [])
                self.assertFalse(matches_conditions(one(self.ideas[active], "cancel"), facts, tag))
                facts[(tag, "has_war_with", enemy)] = False
                facts[(tag, "has_war_with", "RUS")] = True
                self.assertTrue(matches_conditions(one(self.ideas[active], "cancel"), facts, tag))

    def test_paid_border_exercises_store_preparation_and_block_duplicate_payment(self):
        decision = self.decisions["STP_pw_party_frontier_exercise"]
        ready = "STP_pw_party_frontier_prepared"
        active = "STP_pw_party_frontier_drill"
        activation = "STP_pw_party_activate_frontier_drill"
        self.assertEqual(one(self.ideas[ready], "modifier"), [])
        self.assertFalse(any(node.key == "cancel" for node in self.ideas[ready]))
        for war in (False, True):
            for existing in (None, ready, active):
                for cash in (539.99, 540):
                    facts = {
                        ("STP", "STP_pw_can_reconstruct", "yes"): True,
                        ("STP", "has_completed_focus", "STP_pw_party_southern_defence"): True,
                        ("STP", "has_war_with", "VAL"): war,
                        ("STP", "variable", "ADISCORD_economy_treasury"): cash,
                        ("STP", "has_idea", existing): True,
                    }
                    with self.subTest(war=war, existing=existing, cash=cash):
                        effects = [node for _, node in selected_effects(one(decision, "complete_effect"), facts)]
                        self.assertTrue(matches_conditions(one(decision, "visible"), facts))
                        self.assertEqual(matches_conditions(one(decision, "available"), facts), existing is None)
                        expected = int(cash >= 540 and existing is None)
                        for key in ("subtract_from_variable", "add_ideas", activation):
                            self.assertEqual(sum(node.key == key for node in effects), expected)
                        self.assertFalse(any(node.key == "add_timed_idea" for node in effects))
                        if expected:
                            self.assertEqual(next(node.value for node in effects if node.key == "add_ideas"), ready)
                            debit = next(node.value for node in effects if node.key == "subtract_from_variable")
                            self.assertEqual(one(debit, "value"), "540")
                            facts[("STP", "has_idea", ready)] = True
                            grants = [node for _, node in selected_effects(one(self.effects, activation), facts)]
                            self.assertEqual(sum(node.key == "add_timed_idea" for node in grants), int(war))

    def test_frontier_preparation_activates_once_for_kefreyt_in_either_war_direction(self):
        ready = "STP_pw_party_frontier_prepared"
        active = "STP_pw_party_frontier_drill"
        activation = "STP_pw_party_activate_frontier_drill"
        effect = one(self.effects, activation)
        hooks = one(definitions("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_actions")
        hook = one(one(hooks, "on_war_relation_added"), "effect")
        for root, other in (("STP", "VAL"), ("VAL", "STP"), ("STP", "NOD")):
            def bind_scopes(nodes):
                bound = []
                for node in nodes:
                    key = {"ROOT": root, "FROM": other}.get(node.key, node.key)
                    value = bind_scopes(node.value) if isinstance(node.value, list) else node.value
                    bound.append(replace(node, key=key, value=value))
                return bound

            calls = [(scope, node) for scope, node in selected_effects(bind_scopes(hook), {}, root)
                     if node.key == activation]
            self.assertEqual(len(calls), int(other != "NOD"))
            if calls:
                self.assertEqual(calls[0][0], "STP")
        facts = {("STP", "has_idea", ready): True, ("STP", "has_war_with", "NOD"): True}
        self.assertEqual(list(selected_effects(effect, facts)), [])
        facts[("STP", "has_war_with", "VAL")] = True
        grants = [node for _, node in selected_effects(effect, facts)]
        timed = next(node.value for node in grants if node.key == "add_timed_idea")
        self.assertEqual(one(timed, "idea"), active)
        self.assertEqual(one(timed, "days"), "180")
        self.assertIn(ready, [node.value for node in grants if node.key == "remove_ideas"])
        self.assertFalse(any(node.key == "subtract_from_variable" for node in grants))
        facts[("STP", "has_idea", ready)] = False
        facts[("STP", "has_idea", active)] = True
        self.assertEqual(list(selected_effects(effect, facts)), [])
        self.assertFalse(matches_conditions(one(self.ideas[active], "cancel"), facts))
        facts[("STP", "has_war_with", "VAL")] = False
        self.assertTrue(matches_conditions(one(self.ideas[active], "cancel"), facts))

    def test_party_mobilization_preparation_keeps_recruitment_and_starts_timer_once(self):
        cases = (
            ("STP_pw_party_security_prepared", "STP_pw_party_security_cordon",
             "STP_pw_party_activate_security_reserve", None),
            ("STP_pw_party_nod_mobilization_prepared", "STP_pw_party_nod_emergency_mobilization_idea",
             "STP_pw_party_activate_nod_mobilization", "NOD"),
        )
        hooks = one(definitions("common/on_actions/02_ADISCORD_STP_on_actions.txt"), "on_actions")
        hook = one(one(hooks, "on_war_relation_added"), "effect")
        for ready, active, activation, enemy in cases:
            effect = one(self.effects, activation)
            self.assertEqual(
                {node.key: node.value for node in one(self.ideas[ready], "modifier")},
                {node.key: node.value for node in one(self.ideas[active], "modifier")},
            )
            self.assertGreater(float(one(one(self.ideas[ready], "modifier"), "mobilization_speed")), 0)
            for other in ("NOD", "VAL"):
                for root, from_country in (("STP", other), (other, "STP")):
                    def bind_scopes(nodes):
                        bound = []
                        for node in nodes:
                            key = {"ROOT": root, "FROM": from_country}.get(node.key, node.key)
                            value = bind_scopes(node.value) if isinstance(node.value, list) else node.value
                            bound.append(replace(node, key=key, value=value))
                        return bound

                    calls = [(scope, node) for scope, node in selected_effects(bind_scopes(hook), {}, root)
                             if node.key == activation]
                    self.assertEqual(len(calls), int(enemy is None or other == enemy))
                    if calls:
                        self.assertEqual(calls[0][0], "STP")
            for actual_enemy in (None, "VAL", "NOD"):
                facts = {
                    ("STP", "has_idea", ready): True,
                    ("STP", "has_war", "yes"): actual_enemy is not None,
                    ("STP", "has_war_with", actual_enemy): True,
                }
                effects = [node for _, node in selected_effects(effect, facts)]
                expected = actual_enemy is not None and (enemy is None or actual_enemy == enemy)
                self.assertEqual(sum(node.key == "add_timed_idea" for node in effects), int(expected))
                self.assertFalse(any(node.key in ("add_manpower", "add_equipment_to_stockpile", "subtract_from_variable") for node in effects))
                if expected:
                    self.assertIn(ready, [node.value for node in effects if node.key == "remove_ideas"])
                    timed = next(node.value for node in effects if node.key == "add_timed_idea")
                    self.assertEqual(one(timed, "idea"), active)
                    self.assertEqual(one(timed, "days"), "180")
                    facts[("STP", "has_idea", ready)] = False
                    facts[("STP", "has_idea", active)] = True
                    self.assertEqual(list(selected_effects(effect, facts)), [])
            if enemy:
                cancel = one(self.ideas[ready], "cancel")
                threat = {("STP", "STP_pw_party_nod_threat_current", "yes"): True}
                dispatch = {("STP", "has_country_flag", "STP_pw_party_nod_invasion_active"): True}
                self.assertFalse(matches_conditions(cancel, threat))
                self.assertFalse(matches_conditions(cancel, dispatch))
                self.assertTrue(matches_conditions(cancel, {}))
                for end in (("STP", "is_subject", "yes"), ("STP", "has_capitulated", "yes"), ("NOD", "exists", "no")):
                    self.assertTrue(matches_conditions(cancel, threat | {end: True}))
                self.assertTrue(matches_conditions(one(self.ideas[active], "cancel"), {}))
            else:
                self.assertFalse(any(node.key == "cancel" for node in self.ideas[ready]))

    def test_party_mobilization_delivers_materials_before_war_without_starting_timer(self):
        decision = self.decisions["STP_pw_party_nod_emergency_mobilization"]
        for pp, cash, threat, paid_before in (
            (50, 900, True, False), (49.99, 900, True, False),
            (50, 899.99, True, False), (50, 900, False, False), (50, 900, True, True),
        ):
            facts = {
                ("STP", "STP_pw_party_nod_threat_current", "yes"): threat,
                ("STP", "numeric", "has_political_power"): pp,
                ("STP", "variable", "ADISCORD_economy_treasury"): cash,
                ("STP", "has_country_flag", "STP_pw_party_nod_emergency_mobilized"): paid_before,
            }
            effects = [node for _, node in selected_effects(one(decision, "complete_effect"), facts)]
            paid = pp >= 50 and cash >= 900 and threat and not paid_before
            for key in ("add_political_power", "subtract_from_variable", "add_manpower", "add_ideas", "add_war_support"):
                self.assertEqual(sum(node.key == key for node in effects), int(paid))
            self.assertFalse(any(node.key == "add_timed_idea" for node in effects))
            if paid:
                self.assertEqual(next(node.value for node in effects if node.key == "add_manpower"), "10000")
                self.assertEqual(next(node.value for node in effects if node.key == "add_ideas"), "STP_pw_party_nod_mobilization_prepared")
                self.assertEqual(next(node.value for node in effects if node.key == "add_political_power"), "-50")
                debit = next(node.value for node in effects if node.key == "subtract_from_variable")
                self.assertEqual(one(debit, "value"), "900")
                equipment = {one(node.value, "type"): one(node.value, "amount")
                             for node in effects if node.key == "add_equipment_to_stockpile"}
                self.assertEqual(equipment, {"infantry_equipment": "12000", "support_equipment": "100", "artillery_equipment": "60"})
        reserve = self.decisions["STP_pw_party_security_reserve"]
        for cash, existing in ((539.99, None), (540, None), (540, "STP_pw_party_security_prepared"), (540, "STP_pw_party_security_cordon")):
            facts = {
                ("STP", "STP_pw_can_reconstruct", "yes"): True,
                ("STP", "has_completed_focus", "STP_pw_party_firm_settlement"): True,
                ("STP", "variable", "ADISCORD_economy_treasury"): cash,
                ("STP", "has_idea", existing): True,
            }
            effects = [node for _, node in selected_effects(one(reserve, "complete_effect"), facts)]
            paid = cash >= 540 and existing is None
            for key in ("add_ideas", "subtract_from_variable", "STP_pw_party_activate_security_reserve"):
                self.assertEqual(sum(node.key == key for node in effects), int(paid))
            self.assertFalse(any(node.key == "add_timed_idea" for node in effects))

    def test_rus_programmes_require_war_before_payment(self):
        triggers = definitions("common/scripted_triggers/ADISCORD_RUS_scripted_triggers.txt")
        for kind, focus in (("defensive", "RUS_entrenched_reserves"), ("mobile", "RUS_mobile_supply_columns")):
            gate = one(triggers, f"RUS_{kind}_preparation_available")
            decision = self.decisions[f"RUS_{kind}_preparation"]
            for war in (False, True):
                facts = {
                    ("RUS", "RUS_bunker_operational", "yes"): True,
                    ("RUS", "has_completed_focus", focus): True,
                    ("RUS", "has_war", "yes"): war,
                    ("RUS", "has_war", "no"): not war,
                }
                self.assertEqual(matches_conditions(gate, facts, "RUS"), war)
                idea = self.ideas[f"RUS_{kind}_preparation_spirit"]
                self.assertEqual(matches_conditions(one(idea, "cancel"), facts, "RUS"), not war)
            self.assertIn(f"RUS_{kind}_preparation_available", [node.key for node in walk(one(decision, "complete_effect"))])

    def test_plan_names_and_descriptions_are_single_line_localisation(self):
        for language in ("russian", "english"):
            all_keys = {}
            for family in ("STP", "vorkerland"):
                path = ROOT / f"localisation/{language}/ADISCORD_{family}_l_{language}.yml"
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
                all_keys.update(dict(re.findall(r'^ ([^ :]+):\d* "([^"\n]*)"$', path.read_text(encoding="utf-8-sig"), re.M)))
            for key in self.decisions:
                if key.endswith("_activate_plan"):
                    self.assertIn(key, all_keys)
                    self.assertIn(key + "_desc", all_keys)

    def test_val_council_awards_wait_for_war_and_cannot_overwrite_active_bonus(self):
        modifiers = definitions("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        for kind in ("garrison", "front"):
            decision = self.decisions[f"VAL_council_{kind}_execute"]
            modifier = f"VAL_council_favour_{kind}"
            for earned, war, active in ((True, False, False), (False, True, False), (True, True, True), (True, True, False)):
                facts = {
                    ("VAL", "has_country_flag", f"VAL_council_{kind}_plan_ready"): earned,
                    ("VAL", "VAL_council_operational", "yes"): True,
                    ("VAL", "has_war", "yes"): war,
                    ("VAL", "has_war", "no"): not war,
                    ("VAL", "has_capitulated", "no"): True,
                    ("VAL", "has_dynamic_modifier", modifier): active,
                }
                effects = [node for _, node in selected_effects(one(decision, "complete_effect"), facts, "VAL")]
                granted = [node for node in effects if node.key == "add_dynamic_modifier"]
                self.assertEqual(len(granted), int(earned and war and not active))
                self.assertEqual(sum(node.key == "clr_country_flag" for node in effects), len(granted))
                if granted:
                    self.assertEqual(one(granted[0].value, "days"), "90")
                self.assertEqual(matches_conditions(one(one(modifiers, modifier), "remove_trigger"), facts, "VAL"), not war)

    def test_rus_shock_fist_cannot_charge_support_in_peacetime(self):
        decision = self.decisions["RUS_favour_shock_fist"]
        for war in (False, True):
            facts = {
                ("RUS", "has_war", "yes"): war,
                ("RUS", "RUS_favour_army_20_affordable", "yes"): True,
            }
            effects = [node for _, node in selected_effects(one(decision, "complete_effect"), facts, "RUS")]
            self.assertEqual(sum(node.key == "RUS_faction_support_change" for node in effects), int(war))

    def test_val_transport_rechecks_war_and_trucks_before_payment(self):
        decision = self.decisions["VAL_frontier_transport_contract"]
        for war in (False, True):
            for trucks in (99.99, 100):
                for cash in (False, True):
                    facts = {
                        ("VAL", "VAL_frontier_has_campaign_war", "yes"): war,
                        ("VAL", "has_capitulated", "no"): True,
                        ("VAL", "ADISCORD_economy_can_spend_50", "yes"): cash,
                        ("VAL", "equipment", "motorized_equipment"): trucks,
                    }
                    effects = [node for _, node in selected_effects(one(decision, "complete_effect"), facts, "VAL")]
                    expected = int(war and cash and trucks >= 100)
                    self.assertEqual(sum(node.key == "ADISCORD_economy_spend_50" for node in effects), expected)
                    self.assertEqual(sum(node.key == "add_timed_idea" for node in effects), expected)


if __name__ == "__main__":
    unittest.main()
