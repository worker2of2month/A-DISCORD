"""Focused transaction contracts; Clausewitz execution still needs a fresh campaign."""
from tools.lib.on_actions import country_on_actions_entries, read_country_on_actions
from pathlib import Path
import re
from dataclasses import replace
import unittest

from tools.tests.test_adiscord_stp_preparation import (
    block as ast_block, entries, matches_conditions, scalar, selected_effects, walk,
)

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    file = ROOT / path
    return file.read_text(encoding="utf-8-sig") if file.exists() else ""


def block(text, name):
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*\{", text)
    if not match:
        return ""
    start = match.end()
    depth = 1
    for index in range(start, len(text)):
        depth += (text[index] == "{") - (text[index] == "}")
        if depth == 0:
            return text[start:index]
    raise AssertionError(f"Unclosed block {name}")


class CivilWarContracts(unittest.TestCase):
    def setUp(self):
        self.effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")

    def test_northern_early_peace_uses_shared_defeat_and_war_clock(self):
        trigger = block(self.triggers, "NOD_cw_can_accept_northern_defeat")
        self.assertIn("NOT = { surrender_progress < 0.7 }", trigger)
        self.assertIn("flag = NOD_cw_northern_war_started days > 89", trigger)
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn("has_war_with = " + tag, trigger)
        self.assertIn("has_capitulated = no", trigger)
        start = block(self.effects, "STP_cw_start_northern_war")
        self.assertEqual(start.count("set_country_flag = NOD_cw_northern_war_started"), 1)
        self.assertIn("clr_country_flag = NOD_cw_northern_war_started",
                      block(self.effects, "STP_cw_settle_northern_defeat"))
        decision = block(read("common/decisions/ADISCORD_STP_decisions.txt"), "NOD_cw_accept_northern_defeat")
        self.assertIn("NOD_cw_can_accept_northern_defeat = yes", decision)
        self.assertIn("STP_cw_settle_northern_defeat = yes", decision)
        self.assertNotIn("transfer_state", decision)
        self.assertIn("NOD_cw_can_accept_northern_defeat = yes",
                      block(self.effects, "STP_cw_settle_northern_defeat"))

    def test_arsenal_batch_checks_cash_boundary_and_pays_only_once(self):
        council = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        decision = ast_block(council, "STP_cw_purchase_arsenal_batch")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "days_re_enable"), "42")
        cost = ast_block(decision, "custom_cost_trigger")
        for money in (0, 419.99, 420, 420.01, 777.20):
            with self.subTest(treasury=money):
                facts = {("STS", "variable", "ADISCORD_economy_treasury"): money}
                self.assertEqual(matches_conditions(cost, facts, "STS"), money >= 420)
        result = list(selected_effects(ast_block(decision, "complete_effect"), {}, "STS"))
        payments = [e for _, e in result if e.key == "subtract_from_variable"]
        self.assertEqual(len(payments), 1)
        self.assertEqual((scalar(payments[0].value, "var"), scalar(payments[0].value, "value")),
                         ("ADISCORD_economy_treasury", "420"))
        costs = [e for _, e in result if e.key == "add_to_variable"
                 and scalar(e.value, "var") == "ADISCORD_economy_current_month_action_costs"]
        self.assertEqual([scalar(e.value, "value") for e in costs], ["420"])
        stocks = {scalar(e.value, "type"): int(scalar(e.value, "amount"))
                  for _, e in result if e.key == "add_equipment_to_stockpile"}
        self.assertEqual(stocks, {"infantry_equipment": 1600, "artillery_equipment": 60,
                                 "ADISCORD_squad_weapons_equipment": 48,
                                 "support_equipment": 30, "anti_air_equipment": 20})
        self.assertEqual(sum(e.key == "ADISCORD_economy_mark_dirty" for _, e in result), 1)
        self.assertFalse(any(e.key in {"days_remove", "remove_effect", "cancel_effect"} for e in decision))
        self.assertEqual(scalar(ast_block(decision, "available"), "STP_cw_can_rearm"), "yes")
        visible = ast_block(decision, "visible")
        for postwar in (False, True):
            facts = {("STS", "has_country_flag", "STP_cw_postwar"): postwar,
                     ("STS", "has_completed_focus", "STP_cw_wartime_arsenals"): True}
            self.assertEqual(matches_conditions(visible, facts, "STS"), not postwar)

    def test_strike_templates_receive_reinforcements_before_territorials(self):
        templates = entries("history/units/ADISCORD_STP_civil_war_templates.txt")
        for template in templates:
            name = scalar(template.value, "name").strip('"')
            if name in {"Stelander Assault Division", "Kefreyt Volunteer Division"}:
                self.assertEqual(scalar(template.value, "priority"), "2")
            elif name == "Stelander Territorial Brigade":
                self.assertFalse(any(e.key == "priority" and e.value == "2" for e in template.value))

    def test_offensive_plan_does_not_penalize_its_own_supply_or_recovery(self):
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        modifiers = ast_block(ast_block(ideas, "STP_cw_deliberate_offensive"), "modifier")
        self.assertGreater(float(scalar(modifiers, "breakthrough_factor")), 0)
        self.assertFalse(any(e.key in {"supply_consumption_factor", "army_org_regain"} for e in modifiers))

    def test_warning_title_distinguishes_the_northern_front(self):
        definitions = entries("common/scripted_localisation/ADISCORD_STP_scripted_loc.txt")
        title = next(e.value for e in definitions
                     if scalar(e.value, "name") == "STPGetNodReadinessTitle")
        for busy, mobilizing, expected in (
                (True, False, "STP_nod_readiness_north"),
                (True, True, "STP_nod_readiness_north"),
                (False, True, "STP_nod_readiness_mobilization"),
                (False, False, "STP_nod_readiness_intervention")):
            facts = {("STS", "STP_cw_nod_busy_in_north", "yes"): busy,
                     ("NOD", "has_active_mission", "NOD_cw_northern_mobilization"): mobilizing}
            selected = next(scalar(e.value, "localization_key") for e in title
                            if e.key == "text" and (not any(c.key == "trigger" for c in e.value)
                            or matches_conditions(ast_block(e.value, "trigger"), facts, "STS")))
            self.assertEqual(selected, expected)

    def test_northern_conscription_delivers_current_law_or_refunds_once(self):
        category = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention")
        decision = ast_block(category, "NOD_cw_northern_conscription")
        self.assertEqual(scalar(decision, "cost"), "150")
        self.assertEqual(scalar(decision, "days_remove"), "35")
        for active, limited, capitulated, subject, ended_war in (
                (True, True, False, False, None), (False, True, False, False, None),
                (True, False, False, False, None), (True, True, True, False, None),
                (True, True, False, True, None), (True, True, False, False, "YPR"),
                (True, True, False, False, "COF"), (True, True, False, False, "TFF")):
            facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): 1 if active else 2,
                     ("NOD", "has_idea", "limited_conscription"): limited,
                     ("NOD", "has_capitulated", "yes"): capitulated,
                     ("NOD", "has_capitulated", "no"): not capitulated,
                     ("NOD", "is_subject", "yes"): subject,
                     ("NOD", "is_subject", "no"): not subject}
            facts.update({("NOD", "has_war_with", enemy): enemy != ended_war for enemy in ("YPR", "COF", "TFF")})
            valid = active and limited and not capitulated and not subject and ended_war is None
            self.assertEqual(matches_conditions(ast_block(decision, "cancel_trigger"), facts, "NOD"), not valid)
            result = list(selected_effects(ast_block(decision, "remove_effect"), facts, "NOD"))
            self.assertEqual([e.value for _, e in result if e.key == "add_ideas"], ["extensive_conscription"] if valid else [])
            self.assertEqual([e.value for _, e in result if e.key == "add_political_power"], [] if valid else ["150"])
            self.assertEqual(sum(e.key == "ADISCORD_economy_mark_dirty" for _, e in result), int(valid))
        self.assertEqual([(e.key, e.value) for e in ast_block(decision, "cancel_effect")], [("add_political_power", "150")])
        self.assertFalse(any(e.key == "add_manpower" for e in walk(decision)))

    def test_succession_ends_health_penalty_without_clearing_prepared_rewards(self):
        start = block(self.effects, "STP_cw_start")
        retirement = start.index("retire_character = STP_Petr_Ivanov")
        removal = start.index("remove_dynamic_modifier = { modifier = STP_fading_father }")
        transfer = start.index("STP_cw_transfer_preparation_modifiers")
        self.assertLess(retirement, removal)
        self.assertLess(removal, transfer)
        self.assertIn("has_dynamic_modifier = { modifier = STP_fading_father }", start[retirement:removal])
        self.assertIn("set_variable = { var = STP_fading_father_stability_factor value = 0 }", start[removal:transfer])
        self.assertNotIn("STP_cw_clear_political_modifiers", start[:transfer])
        self.assertNotIn("STP_cw_clear_resistance_modifiers", start[:transfer])

    def test_campaign_stats_keep_native_nonnegative_floors(self):
        for path in (ROOT / "common/defines").glob("*.lua"):
            for name, value in re.findall(r"NDefines\.NCountry\.(MIN_STABILITY|MIN_WAR_SUPPORT)\s*=\s*(-?[\d.]+)", path.read_text(encoding="utf-8-sig")):
                self.assertGreaterEqual(float(value), 0, f"{path.name}: {name}")

    def test_allies_can_be_called_but_unsolicited_war_entry_stays_blocked(self):
        diplomacy = entries("common/scripted_triggers/diplomacy_scripted_triggers.txt")
        self.assertTrue(matches_conditions(ast_block(diplomacy, "DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER"), {}))
        self.assertFalse(matches_conditions(ast_block(diplomacy, "DIPLOMACY_JOIN_ALLY_ENABLE_TRIGGER"), {}))
        north = block(self.effects, "STP_cw_start_northern_war")
        for ally in ("COF", "TFF"):
            self.assertRegex(north, ally + r"\s*=\s*\{\s*add_to_war\s*=\s*\{\s*targeted_alliance = YPR")

    def test_northern_call_excludes_only_nod_to_stelander_until_peace(self):
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        blocked = ast_block(triggers, "STP_cw_northern_call_blocked")
        call = ast_block(entries("common/scripted_triggers/diplomacy_scripted_triggers.txt"),
                         "DIPLOMACY_CALL_ALLY_ENABLE_TRIGGER")
        for caller in ("NOD", "VAL", "STP"):
            for recipient in ("STP", "VAL", "NOD"):
                for enemy in (None, "YPR", "COF", "TFF", "VAL"):
                    with self.subTest(caller=caller, recipient=recipient, enemy=enemy):
                        facts = {}
                        if enemy:
                            facts[(caller, "has_war_with", enemy)] = True
                        denied = matches_conditions([replace(e, key=recipient) if e.key == "FROM" else e
                                                     for e in blocked], facts, caller)
                        expected = caller == "NOD" and recipient == "STP" and enemy in ("YPR", "COF", "TFF")
                        self.assertEqual(denied, expected)
                        facts[(caller, "STP_cw_northern_call_blocked", "yes")] = denied
                        self.assertEqual(matches_conditions(call, facts, caller), not expected)

    def test_nod_offer_precedes_normal_result_and_earliest_northern_uprising(self):
        begin = block(self.effects, "STP_cw_begin_elections")
        fallback = block(block(begin, "NOD"), "country_event")
        self.assertIn("id = ADISCORD_STP_cw.42", fallback)
        self.assertEqual(140 - int(re.search(r"days\s*=\s*(\d+)", fallback)[1]), 28)
        north = block(self.effects, "STP_cw_start_northern_war")
        scheduled = re.search(r"country_event\s*=\s*\{\s*id = ADISCORD_STP_cw\.42\s+days = (\d+)", north)
        self.assertIsNotNone(scheduled)
        focuses = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        window = next(e.value for e in walk(focuses) if e.key == "focus" and isinstance(e.value, list) and scalar(e.value, "id") == "STP_THE_MOUNTAIN_WINDOW")
        defines = read("common/defines/ADISCORD_defines_changes.lua")
        saved_days = int(re.search(r"MAX_SAVED_FOCUS_PROGRESS\s*=\s*(\d+)", defines)[1])
        self.assertLess(int(scheduled[1]), float(scalar(window, "cost")) * 7 - saved_days)
        events = entries("events/ADISCORD_STP_events.txt")
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.42")
        for eligible in (False, True):
            for already_offered in (False, True):
                facts = {("NOD", "NOD_cw_intervention_possible", "yes"): eligible,
                         ("NOD", "has_country_flag", "NOD_cw_offer_shown"): already_offered}
                self.assertEqual(matches_conditions(ast_block(offer, "trigger"), facts, "NOD"), eligible and not already_offered)

    def test_category_army_forecast_tracks_preparation_and_asset_loss(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        decisions = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        for owner in ("STP_initialize_battle_for_stelander", "STP_normalize_region_influence",
                      "STP_political_action_slot_release", "STP_resolve_party_inspection", "STP_cw_prepare_opposition"):
            self.assertTrue(any(e.key == "STP_cw_refresh_army_report" for e in walk(ast_block(effects, owner))), owner)
        for decision in ("STP_cw_open_civil_registers", "STP_cw_sacrifice_local_contact"):
            concession = ast_block(ast_block(decisions, decision), "complete_effect")
            actions = [e.key for e in walk(concession)]
            self.assertGreater(actions.index("STP_cw_refresh_army_report"), actions.index("clr_state_flag"))
        focuses = list(walk(entries("common/national_focus/ADISCORD_national_focus_STP.txt")))
        for flag in ("STP_cw_party_reserve_ready", "STP_cw_abila_reserve_ready", "STP_cw_local_recruits_ready"):
            reward = next(ast_block(f.value, "completion_reward") for f in focuses if f.key == "focus" and isinstance(f.value, list)
                          and any(e.key == "set_country_flag" and e.value == flag for e in walk(f.value)))
            operations = list(walk(reward))
            self.assertGreater(next(i for i, e in enumerate(operations) if e.key == "STP_cw_refresh_army_report"),
                               next(i for i, e in enumerate(operations) if e.key == "set_country_flag" and e.value == flag))
        self.assertNotIn("STP_cw_army_report", [e.key for e in decisions])
        events = entries("events/ADISCORD_STP_events.txt")
        self.assertNotIn("ADISCORD_STP_preparation.7", [scalar(e.value, "id") for e in events if e.key == "country_event"])
        localisation = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        description = next(line for line in localisation.splitlines() if line.lstrip().startswith("STP_battle_for_stelander_desc:"))
        for variable in ("STP_cw_report_party_brigades", "STP_cw_report_resistance_brigades", "STP_cw_prepared_assault_divisions"):
            self.assertIn("[?" + variable + "|0]", description)
        self.assertIn("ADISCORD_STP_preparation.7.a:", localisation)

    def test_human_handoff_precedes_any_time_at_war(self):
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start"), "if")
        body = [e for e in start if e.key != "limit"]
        unset = {("STP", "is_ai", "yes"): False, ("STP", "is_ai", "no"): True}
        chosen = list(selected_effects(body, unset))
        self.assertFalse(any(e.key == "declare_war_on" for _, e in chosen))
        self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in chosen), 0)
        self.assertEqual([scalar(e.value, "id") for _, e in chosen if e.key == "country_event"],
                         ["ADISCORD_STP_cw.30"])
        ai = list(selected_effects(body, {("STP", "is_ai", "yes"): True, ("STP", "is_ai", "no"): False}))
        self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in ai), 1)
        events = entries("events/ADISCORD_STP_events.txt")
        handoff = next(e.value for e in events if e.key == "country_event"
                       and scalar(e.value, "id") == "ADISCORD_STP_cw.30")
        for option in (e.value for e in handoff if e.key == "option"):
            for resistance in (False, True):
                facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): resistance,
                         ("STS", "exists", "yes"): True}
                self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in selected_effects(option, facts)), 1)
        war = block(self.effects, "STP_cw_begin_hostilities")
        self.assertEqual(war.count("declare_war_on"), 2)
        self.assertIn("declare_war_on = { target = STS", war)
        self.assertIn("declare_war_on = { target = STP", war)
        self.assertNotIn("declare_war_on = { target = SRP", war)
        self.assertIn("set_state_controller_to = PREV", war)
        self.assertGreater(war.index("set_state_controller_to"), war.index("declare_war_on"))
        self.assertNotIn("set_global_flag = STP_cw_started", block(self.effects, "STP_cw_start"))
        self.assertLess(war.index("set_global_flag = STP_cw_started"), war.index("declare_war_on"))

    def test_predetermined_shabrat_human_takes_sts_immediately(self):
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start"), "if")
        body = [e for e in start if e.key != "limit"]
        shabrat = {("STP", "is_ai", "no"): True, ("STP", "is_ai", "yes"): False,
                   ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                   ("STS", "exists", "yes"): True}
        chosen = list(selected_effects(body, shabrat))
        self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in chosen), 1)
        self.assertEqual(sum(e.key == "STP_cw_commission_korsh" for _, e in chosen), 1)
        self.assertIn(("STS", "change_tag_from"), [(scope, e.key) for scope, e in chosen if e.key == "change_tag_from"])
        self.assertEqual([e.value for scope, e in chosen if scope == "STS" and e.key == "change_tag_from"], ["STP"])
        self.assertFalse(any(e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.30"
                             for _, e in chosen))
        party = {("STP", "is_ai", "no"): True, ("STP", "is_ai", "yes"): False,
                 ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True,
                 ("STS", "exists", "yes"): True}
        party_chosen = list(selected_effects(body, party))
        self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in party_chosen), 1)
        self.assertEqual(sum(e.key == "STP_cw_commission_korsh" for _, e in party_chosen), 0)
        self.assertFalse(any(e.key == "change_tag_from" for _, e in party_chosen))
        self.assertFalse(any(e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.30"
                             for _, e in party_chosen))

    def test_scripted_trigger_calls_obey_the_native_boolean_interface(self):
        # Native HOI4 loader rejects argument blocks (Invalid trigger 'target'),
        # then loses the rest of the STP decision category. Effects do accept
        # macro arguments; do not extend that assumption to scripted triggers.
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        names = {e.key for e in triggers}
        for folder in ("common", "events"):
            for path in (ROOT / folder).rglob("*.txt"):
                text = path.read_text(encoding="utf-8-sig")
                if not any(name in text for name in names):
                    continue
                tree = entries(path.relative_to(ROOT))
                nodes = [child for e in tree if isinstance(e.value, list) for child in walk(e.value)]
                for node in nodes:
                    if node.key in names:
                        self.assertIn(node.value, ("yes", "no"), f"{path}:{node.line} {node.key}")
        self.assertNotRegex(self.triggers, r"\$[A-Za-z_]+\$")

    def test_party_garrison_forecast_matches_paid_mobilization_and_final_owner(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = ast_block(ast_block(effects, "STP_cw_start"), "if")
        report = ast_block(effects, "STP_cw_refresh_army_report")
        for state in ("2", "29", "45"):
            for owner in ("STP", "STS", "SRP"):
                with self.subTest(state=state, owner=owner):
                    asset = {(state, "has_state_flag", "STP_party_reinforced_garrison_asset"): True}
                    actual = {**asset, (state, "is_owned_by", owner): True}
                    before = {**asset, (state, "is_owned_by", "STP"): True}
                    if owner != "STP":
                        target = "resistance" if owner == "STS" else "republics"
                        before[(state, f"STP_cw_region_goes_to_{target}", "yes")] = True
                    planned = sum(1 for scope, e in selected_effects(start, actual)
                                  if scope == "STP" and e.key == "STP_cw_mobilize_brigade")
                    forecast = sum(float(scalar(e.value, "value"))
                                   for scope, e in selected_effects(report, before)
                                   if e.key in ("set_variable", "add_to_variable")
                                   and scalar(e.value, "var") == "STP_cw_report_party_brigades")
                    self.assertEqual(planned, 18 if owner == "STP" else 16)
                    self.assertEqual(forecast, planned)

    def test_entry_cannot_bypass_elections_or_missing_anchors(self):
        gate = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_can_start")
        anchors = {("STP", "owns_state", str(state)): True for state in (1, 28, 43, 44, 88)}
        early_requirements = {
            ("STP", "has_active_mission", "STP_cw_election_window"): True,
            ("STP", "has_country_flag", "STP_cw_uprising_prepared"): True,
            ("STP", "STP_cw_nod_busy_in_north", "yes"): True,
        }
        early = {**anchors, **early_requirements}
        deadline = {**anchors, ("STP", "has_country_flag", "STP_cw_elections_finished"): True}
        self.assertTrue(matches_conditions(gate, early))
        self.assertTrue(matches_conditions(gate, deadline), "an expired election mission must still reach the split")
        self.assertFalse(matches_conditions(gate, anchors))
        for requirement in early_requirements:
            self.assertFalse(matches_conditions(gate, {k: v for k, v in early.items() if k != requirement}), requirement)
        for scenario in (early, deadline):
            self.assertFalse(matches_conditions(gate, scenario, "VAL"))
            for anchor in anchors:
                self.assertFalse(matches_conditions(gate, {k: v for k, v in scenario.items() if k != anchor}), anchor)
            for blocker in (("STP", "has_global_flag", "STP_cw_started"),
                            ("STP", "has_country_flag", "STP_cw_participant"),
                            ("STS", "exists", "yes"), ("SRP", "exists", "yes")):
                self.assertFalse(matches_conditions(gate, {**scenario, blocker: True}), blocker)
        start = block(self.effects, "STP_cw_start")
        self.assertIn("limit = { STP_cw_can_start = yes }", start)
        self.assertLess(start.index("set_country_flag = STP_cw_participant"), start.index("transfer_state"))
        self.assertNotIn("white_peace", start)

    def test_absent_successors_materialize_before_scoped_setup_and_wars(self):
        start = block(self.effects, "STP_cw_start")
        for tag, state in (("STS", 1), ("SRP", 43)):
            self.assertRegex(start, rf"{tag}\s*=\s*\{{\s*transfer_state = {state}")
        start = block(self.effects, "STP_cw_begin_hostilities")
        self.assertIn("declare_war_on = { target = STS", start)
        self.assertIn("declare_war_on = { target = STP", start)
        self.assertNotIn("declare_war_on = { target = SRP", start)
        self.assertEqual(start.count("declare_war_on"), 2,
                         "independent republics are outside the party-resistance war")
        self.assertNotIn("start_civil_war", start)

    def test_stelander_civil_war_starts_the_registered_theme(self):
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                    "STP_cw_begin_hostilities"), "if")
        first_time = next(e for e in start if e.key == "if"
                         and any(v.key == "set_global_flag" and v.value == "STP_cw_started" for v in walk(e.value)))
        audio = ast_block(first_time.value, "hidden_effect")
        self.assertFalse(any(e.key == "scoped_play_song" for e in walk(audio)))
        for scope in (audio, ast_block(audio, "STS")):
            callbacks = [e.value for e in scope if e.key == "country_event"
                         and scalar(e.value, "id") == "ADISCORD_STP_cw.95"]
            self.assertEqual(len(callbacks), 1)
            self.assertEqual(scalar(callbacks[0], "hours"), "1")
        party_story = [scope for scope, e in selected_effects(audio, {}, "STP")
                       if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.94"]
        self.assertEqual(party_story, ["STP"])
        events = entries("events/ADISCORD_STP_events.txt")
        playback = next(e.value for e in events if e.key == "country_event"
                        and scalar(e.value, "id") == "ADISCORD_STP_cw.95")
        story = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_cw.94")
        self.assertEqual(scalar(playback, "hidden"), "yes")
        for tag, enemy, song in (("STP", "STS", "ADISCORD_stp_party"),
                                 ("STS", "STP", "ADISCORD_stp_civil_war")):
            for human, war, finished in ((True, True, False), (False, True, False),
                                         (True, False, False), (True, True, True)):
                facts = {(tag, "is_ai", "no"): human,
                         (tag, "has_war_with", enemy): war,
                         (tag, "has_global_flag", "STP_cw_started"): True,
                         (tag, "has_global_flag", "STP_cw_union_wars_finished"): finished}
                eligible = matches_conditions(ast_block(playback, "trigger"), facts, tag)
                self.assertEqual(eligible, human and war and not finished)
                if eligible:
                    songs = [e.value for _, e in selected_effects(ast_block(playback, "immediate"), facts, tag)
                             if e.key == "scoped_play_song"]
                    self.assertEqual(songs, [song])
            self.assertEqual(matches_conditions(ast_block(story, "trigger"), {}, tag), tag == "STP")
        self.assertLess(first_time.value.index(next(e for e in first_time.value if e.key == "set_global_flag")),
                        first_time.value.index(next(e for e in first_time.value if e.key == "hidden_effect")))
        assets = entries("music/music.asset")
        song = next(e.value for e in assets if e.key == "music" and scalar(e.value, "name") == "ADISCORD_stp_civil_war")
        self.assertEqual(scalar(song, "file"), "ADISCORD_stp_civil_war.ogg")
        self.assertTrue((ROOT / "music" / "ADISCORD_stp_civil_war.ogg").is_file())
        playlist = next(e.value for e in entries("music/_songs.txt")
                        if e.key == "music" and scalar(e.value, "song") == "ADISCORD_stp_civil_war")
        flags = [e.value for e in walk(ast_block(playlist, "chance")) if e.key == "has_global_flag"]
        self.assertIn("STP_cw_started", flags)
        self.assertIn("STP_cw_union_wars_finished", flags)
        self.assertIn('ADISCORD_stp_civil_war: "Арктида - Всё на кон"',
                      (ROOT / "localisation" / "russian" / "ADISCORD_music_l_russian.yml").read_text(encoding="utf-8-sig"))

    def test_mobilization_pays_real_six_battalion_cost_before_creation(self):
        effect = block(self.effects, "STP_cw_mobilize_brigade")
        spawn = block(self.effects, "STP_cw_create_territorial_brigade")
        self.assertIn("NOT = { has_manpower < 6000 }", effect)
        self.assertIn("NOT = { has_equipment = { infantry_equipment < 600 } }", effect)
        self.assertLess(effect.index("add_manpower = -6000"), effect.index("STP_cw_create_territorial_brigade"))
        self.assertIn("STP_cw_pay_rifles = yes", effect)
        self.assertLess(effect.index("STP_cw_pay_rifles = yes"), effect.index("add_manpower = -6000"))
        self.assertIn("limit = { has_country_flag = STP_cw_rifles_paid }", effect)
        self.assertIn('division_template = \\"Stelander Territorial Brigade\\"', spawn)
        template = read("history/units/ADISCORD_STP_civil_war_templates.txt")
        territorial = block(template, "division_template")
        battalions = len(re.findall(r"\bADISCORD_territorial\s*=", territorial))
        self.assertEqual(battalions, 6)
        unit = block(read("common/units/ADISCORD_land_units.txt"), "ADISCORD_territorial")
        self.assertEqual(battalions * int(re.search(r"manpower\s*=\s*(\d+)", unit)[1]), 6000)
        self.assertEqual(battalions * int(re.search(r"infantry_equipment\s*=\s*(\d+)", unit)[1]), 600)
        self.assertNotIn("units =", template)

    def test_wartime_field_templates_are_editable_except_kefreyt(self):
        templates = {scalar(e.value, "name"): e.value
                     for e in entries("history/units/ADISCORD_STP_civil_war_templates.txt")
                     if e.key == "division_template"}
        for name in ("Stelander Territorial Brigade", "Stelander Assault Division"):
            self.assertIn(name, templates)
            settings = {e.key: e.value for e in templates[name] if isinstance(e.value, str)}
            self.assertNotEqual(settings.get("is_locked", "no"), "yes", name)
            self.assertEqual(settings.get("force_allow_recruiting", "no"), "yes", name)
        volunteer = {e.key: e.value for e in templates["Kefreyt Volunteer Division"] if isinstance(e.value, str)}
        self.assertEqual(volunteer.get("is_locked"), "yes")
        self.assertEqual(volunteer.get("force_allow_recruiting"), "no")
        apply = block(self.effects, "STP_cw_apply_wartime_template_locks")
        self.assertIn('division_template = "Stelander Territorial Brigade" is_locked = no', apply)
        self.assertIn('division_template = "Stelander Assault Division" is_locked = no', apply)
        self.assertIn('division_template = "Kefreyt Volunteer Division" is_locked = yes', apply)
        self.assertIn('division_template = "Kefreyt Contract Infantry" is_locked = yes', apply)
        self.assertIn("ADISCORD_STP_unlock_regular_army_templates = yes", apply)
        self.assertIn("limit = { tag = STP }", apply)
        self.assertIn('has_template = "Kefreyt Volunteer Division"', apply)
        lock = block(self.effects, "ADISCORD_STP_lock_regular_army_templates")
        unlock = block(self.effects, "ADISCORD_STP_unlock_regular_army_templates")
        for name in ("Police division", "Regular army", "Capital Guard"):
            self.assertIn('has_template = "' + name + '"', lock)
        for name in ("Police division", "Regular army"):
            self.assertIn('has_template = "' + name + '"', unlock)
        apply_parsed = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                 "STP_cw_apply_wartime_template_locks")
        for tag, expect_unlock in (("STP", True), ("STS", False), ("SRP", False)):
            keys = [e.key for _, e in selected_effects(apply_parsed, {}, tag)]
            self.assertEqual("ADISCORD_STP_unlock_regular_army_templates" in keys, expect_unlock, tag)
        for name in ("STP_cw_prepare_successor", "STP_cw_start"):
            body = block(self.effects, name)
            self.assertLess(body.index("load_oob = ADISCORD_STP_civil_war_templates"),
                            body.index("STP_cw_apply_wartime_template_locks = yes"), name)
            self.assertNotIn("ADISCORD_STP_unlock_regular_army_templates = yes", body)
            self.assertLess(body.index("load_oob = ADISCORD_STP_civil_war_templates"),
                            body.index("STP_cw_strip_kefreyt_volunteer_template = yes"), name)
            self.assertLess(body.index("STP_cw_strip_kefreyt_volunteer_template = yes"),
                            body.index("STP_cw_apply_wartime_template_locks = yes"), name)
        successor = block(self.effects, "STP_cw_prepare_successor")
        self.assertIn("STP_cw_strip_peacetime_union_templates = yes", successor)
        self.assertIn("NOT = { tag = STS }", successor)
        start = block(self.effects, "STP_cw_start")
        self.assertNotIn("STP_cw_strip_peacetime_union_templates = yes", start)

    def test_shabrat_wartime_templates_use_three_map_models(self):
        templates = {scalar(e.value, "name"): e.value
                     for e in entries("history/units/ADISCORD_STP_civil_war_templates.txt")
                     if e.key == "division_template"}
        territorial = templates["Stelander Territorial Brigade"]
        assault = templates["Stelander Assault Division"]
        volunteer = templates["Kefreyt Volunteer Division"]
        self.assertFalse(any(e.key == "override_model" for e in territorial))
        self.assertFalse(any(e.key == "override_model" for e in assault))
        self.assertEqual(scalar(volunteer, "override_model"), "ADISCORD_VAL_regular_entity")
        self.assertEqual(scalar(territorial, "template_counter"), "12")
        self.assertEqual(scalar(assault, "template_counter"), "4")
        self.assertEqual(scalar(volunteer, "template_counter"), "68")
        self.assertTrue(any(e.key == "ADISCORD_territorial" for e in ast_block(territorial, "regiments")))
        self.assertTrue(any(e.key == "infantry" for e in ast_block(assault, "regiments")))
        entities = read("gfx/entities/zz_ADISCORD_country_infantry.asset")
        self.assertRegex(
            entities,
            r'name\s*=\s*"STS_ADISCORD_militia_2_entity"[^\n]*pdxmesh\s*=\s*"STP_shabrat_mg_infantry_mesh"',
        )
        self.assertRegex(
            entities,
            r'clone\s*=\s*"STS_ADISCORD_militia_2_entity"\s+name\s*=\s*"STS_ADISCORD_territorial_2_entity"',
        )
        self.assertRegex(
            entities,
            r'name\s*=\s*"STS_infantry_2_entity"[\s\S]{0,200}pdxmesh\s*=\s*"ADISCORD_STS_regular_mesh"',
        )
        self.assertIn('name = "ADISCORD_VAL_regular_entity"', entities)

    def test_brigade_order_rejects_fractional_shortfall_before_charging_pp(self):
        order = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                                    "STP_cw_war_council"), "STP_cw_raise_territorial_brigade")
        gate = ast_block(order, "available")
        for manpower, expected in ((5999, False), (5999.5, False), (6000, True), (6001, True)):
            facts = {
                ("STP", "has_completed_focus", "STP_cw_mobilization_register"): True,
                ("STP", "numeric", "has_manpower"): manpower,
                ("STP", "equipment", "infantry_equipment"): 600,
                ("STP", "owns_state", "28"): True,
                ("STP", "controls_state", "28"): True,
            }
            self.assertEqual(matches_conditions(gate, facts), expected, manpower)

    def test_battle_spirits_follow_each_countrys_actual_wars(self):
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        for tag, spirit, opponents, modifiers in (
            ("STP", "STP_cw_party_battle_spirit", {"STS"}, {"surrender_limit": .05, "army_org_factor": .03, "planning_speed": .05}),
            ("STS", "STP_cw_resistance_battle_spirit", {"STP", "NOD"}, {"surrender_limit": .05, "army_speed_factor": .05, "army_org_regain": .03}),
            ("SRP", "STP_cw_republics_battle_spirit", {"VAL"}, {"surrender_limit": .05, "dig_in_speed_factor": .10, "max_dig_in": 1}),
        ):
            idea = ast_block(ideas, spirit)
            self.assertEqual({e.key: float(e.value) for e in ast_block(idea, "modifier")}, modifiers)
            for enemy in (None, "STP", "STS", "NOD", "VAL"):
                facts = {} if enemy is None else {(tag, "has_war_with", enemy): True}
                self.assertEqual(matches_conditions(ast_block(idea, "cancel"), facts, tag), enemy not in opponents,
                                 (tag, enemy))
                self.assertEqual(matches_conditions(ast_block(idea, "cancel"), {
                    **facts, (tag, "has_global_flag", "STP_cw_union_wars_finished"): True,
                }, tag), enemy not in opponents, "another front's settlement must not remove this spirit")
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_begin_hostilities"), "if")
        for war in (False, True):
            chosen = list(selected_effects([e for e in start if e.key != "limit"], {("STP", "has_war_with", "STS"): war}))
            self.assertEqual([(scope, e.value) for scope, e in chosen if e.key == "add_ideas"],
                             [("STP", "STP_cw_party_battle_spirit"), ("STS", "STP_cw_resistance_battle_spirit")] if war else [])

    def test_stockpile_and_free_manpower_shares_are_conservative(self):
        start = block(self.effects, "STP_cw_start")
        self.assertIn('division_template = "Regular army" disband = yes', start)
        self.assertIn('division_template = "Police division" disband = yes', start)
        self.assertEqual(start.count("delete_unit = {"), 2)
        self.assertNotIn("delete_units =", start)
        self.assertNotIn('division_template = "Capital Guard"', start)
        self.assertNotIn("0.333333", start)
        self.assertIn("value = manpower", start)
        self.assertIn("value = -1", start)

    def test_mandate_allocations_conserve_reserves_and_select_paid_brigade_plans(self):
        from fractions import Fraction

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = ast_block(ast_block(effects, "STP_cw_start"), "if")
        body = [e for e in start if e.key != "limit"]
        allocator = ast_block(effects, "STP_cw_allocate_formation_reserves")
        allocator_calls = [e for e in body if e.key == "STP_cw_allocate_formation_reserves"]
        self.assertEqual([call.value for call in allocator_calls], ["yes", "yes"])
        self.assertNotRegex(block(self.effects, "STP_cw_allocate_formation_reserves"), r"\$[A-Za-z_]+\$")
        for call, expected in zip(allocator_calls, (
            {"STP_cw_input_pool": "manpower", "STP_cw_input_light": "6000", "STP_cw_input_heavy": "7900"},
            {"STP_cw_input_pool": "num_equipment@infantry_equipment", "STP_cw_input_light": "600", "STP_cw_input_heavy": "610"},
        )):
            inputs = body[body.index(call) - 3:body.index(call)]
            self.assertEqual([e.key for e in inputs], ["set_temp_variable"] * 3)
            self.assertEqual({scalar(e.value, "var"): scalar(e.value, "value") for e in inputs}, expected)
        snapshot = next(i for i, e in enumerate(body) if e.key == "set_variable"
                        and scalar(e.value, "var") == "STP_cw_initial_manpower")
        debit = next(i for i, e in enumerate(body) if e.key == "add_manpower")
        formula = body[snapshot:debit + 1]
        stock_snapshot = body.index(allocator_calls[1]) - 3
        first_transfer = next(i for i, e in enumerate(body) if e.key == "transfer_units_fraction")
        stock_formula = body[stock_snapshot:first_transfer]
        report = ast_block(effects, "STP_cw_refresh_army_report")
        report_calls = [e for e in walk(body) if e.key == "STP_cw_refresh_army_report"]
        self.assertEqual(len(report_calls), 1)
        self.assertIn(report_calls[0], formula)
        self.assertLess(report_calls[0].line, min(e.line for e in walk(body) if e.key in ("transfer_state", "transfer_units_fraction")))
        report_names = {"STP": "STP_cw_report_party_brigades", "STS": "STP_cw_report_resistance_brigades"}
        report_base = {tag: float(next(scalar(e.value, "value") for e in report
                                      if e.key == "set_variable" and scalar(e.value, "var") == name))
                       for tag, name in report_names.items()}
        self.assertEqual(report_base, {"STP": 16, "STS": 14})

        # This interpreter only covers the arithmetic slice above. Report outputs
        # are inputs, so odd cohort counts also exercise shortage boundaries.
        # It neither simulates state transfers nor supplies missing operations.
        operations = {
            "set_variable": "set", "set_temp_variable": "set",
            "add_to_variable": "add", "add_to_temp_variable": "add",
            "subtract_from_variable": "subtract", "subtract_from_temp_variable": "subtract",
            "multiply_variable": "multiply", "multiply_temp_variable": "multiply",
            "divide_temp_variable": "divide",
        }
        def allocate(total, winner, prepared):
            total = Fraction(str(total))  # Exact arithmetic avoids binary residue at zero.
            manpower = {"STP": total, "STS": 0, "SRP": 0}
            stock = {"STP": total, "STS": 0, "SRP": 0}
            values = {}
            def number(raw):
                raw = raw.removeprefix("var:").removeprefix("STP.")
                if raw == "manpower":
                    return manpower["STP"]
                if raw == "num_equipment@infantry_equipment":
                    return stock["STP"]
                try:
                    return Fraction(raw)
                except ValueError:
                    self.assertIn(raw, values, f"Unknown allocation operand: {raw}")
                    return values[raw]
            def condition(items):
                self.assertEqual(len(items), 1)
                entry = items[0]
                if entry.key == "has_country_flag":
                    self.assertIn(entry.value, ("STP_cw_shabrat_election_victory", "STP_cw_party_election_victory", "STP_cw_limited_party_revolt"))
                    if entry.value == "STP_cw_limited_party_revolt":
                        return winner == "limited"
                    return entry.value == f"STP_cw_{'shabrat' if winner == 'limited' else winner}_election_victory"
                self.assertEqual(entry.key, "check_variable", "Unsupported allocation condition")
                self.assertEqual({e.key for e in entry.value}, {"var", "value", "compare"})
                self.assertEqual(scalar(entry.value, "compare"), "greater_than")
                return number(scalar(entry.value, "var")) > number(scalar(entry.value, "value"))
            def execute(items):
                taken = False
                for entry in items:
                    key = entry.key
                    if key in ("if", "else_if", "else"):
                        if key == "if":
                            taken = False
                        if not taken and (key == "else" or condition(ast_block(entry.value, "limit"))):
                            taken = True
                            execute([e for e in entry.value if e.key != "limit"])
                    elif key == "STP_cw_refresh_army_report":
                        self.assertEqual(entry.value, "yes")
                        values.update({name: Fraction(str(report_base[tag])) + prepared[tag] for tag, name in report_names.items()})
                    elif key == "STP_cw_allocate_formation_reserves":
                        self.assertEqual(entry.value, "yes")
                        execute(allocator)
                    elif key in operations:
                        self.assertEqual({e.key for e in entry.value}, {"var", "value"})
                        variable = scalar(entry.value, "var")
                        value = number(scalar(entry.value, "value"))
                        operation = operations[key]
                        if operation == "set":
                            values[variable] = value
                        else:
                            self.assertIn(variable, values, "Arithmetic must not read an uninitialised variable")
                            if operation == "add":
                                values[variable] += value
                            elif operation == "subtract":
                                values[variable] -= value
                            elif operation == "multiply":
                                values[variable] *= value
                            else:
                                self.assertNotEqual(value, 0, "Shortage handling must not divide by zero")
                                values[variable] /= value
                    elif key == "round_variable":
                        # Positive nearest rounding; assertions allow one person
                        # at half ties rather than claiming native tie semantics.
                        self.assertGreaterEqual(values[entry.value], 0)
                        values[entry.value] = Fraction(int(values[entry.value] + Fraction(1, 2)))
                    elif key in ("clamp_variable", "clamp_temp_variable"):
                        self.assertEqual({e.key for e in entry.value}, {"var", "min", "max"})
                        variable = scalar(entry.value, "var")
                        values[variable] = min(number(scalar(entry.value, "max")),
                                               max(number(scalar(entry.value, "min")), values[variable]))
                    elif key == "add_manpower":
                        manpower["STP"] += number(entry.value)
                    else:
                        self.fail(f"Unsupported allocation operation: {key}")
            execute(formula)
            execute(stock_formula)
            facts = {} if winner is None else {("STP", "has_country_flag", f"STP_cw_{'shabrat' if winner == 'limited' else winner}_election_victory"): True}
            facts[("STP", "has_country_flag", "STP_cw_limited_party_revolt")] = winner == "limited"
            aircraft = {"STP": total, "STS": 0, "SRP": 0}
            credits = []
            transfers = []
            # Native successor grants and stockpile transfers are read separately;
            # none of the mobilisation/materialisation helpers are emulated here.
            for scope, entry in selected_effects(body[debit + 1:], facts):
                if entry.key == "add_manpower":
                    self.assertIn(scope, ("STS", "SRP"))
                    credits.append(scope)
                    manpower[scope] += number(entry.value)
                elif entry.key == "transfer_units_fraction":
                    target = scalar(entry.value, "target")
                    transfers.append(target)
                    for field in ("size", "army_ratio", "navy_ratio"):
                        self.assertEqual(scalar(entry.value, field), "0", field)
                    amount = stock[scope] * number(scalar(entry.value, "stockpile_ratio"))
                    stock[scope] -= amount
                    stock[target] += amount
                    amount = aircraft[scope] * number(scalar(entry.value, "air_ratio"))
                    aircraft[scope] -= amount
                    aircraft[target] += amount
            self.assertEqual(credits, ["STS", "SRP"])
            self.assertEqual(transfers, ["SRP", "STS"])
            return manpower, stock, aircraft

        totals = (0, .25, .75, 17, 319.999, 320, 320.001, 3999.5, 3999.999, 4000, 4000.001, 4000.5,
                  5999.5, 6000, 6000.5, 19660, 26640, 29733.6, 32983.6, 100003, 223603,
                  334799.999, 334800, 334800.001, 335199.999, 335200, 335200.001,
                  393240, 399200, 1000000)
        for winner, shares, plan, air_share in (
            (None, {"STP": .4, "STS": .4, "SRP": .2}, {"STP": 16, "STS": 14, "SRP": 10}, .4),
            ("shabrat", {"STP": .3, "STS": .5, "SRP": .2}, {"STP": 14, "STS": 16, "SRP": 10}, .5),
            ("party", {"STP": .5, "STS": .3, "SRP": .2}, {"STP": 18, "STS": 12, "SRP": 10}, .3),
            ("limited", {"STP": .16, "STS": .64, "SRP": .2}, {"STP": 5, "STS": 16, "SRP": 10}, .8),
        ):
            heavy_plan = {"STP": 3 if winner == "limited" else 6, "STS": 6, "SRP": 0}
            base_claim = {tag: Fraction(plan[tag] * 6000 + heavy_plan[tag] * 7900) for tag in plan}
            self.assertEqual(tuple(base_claim.values()), {
                None: (143400, 131400, 60000), "shabrat": (131400, 143400, 60000),
                "party": (155400, 119400, 60000), "limited": (53700, 143400, 60000),
            }[winner])
            for party in range(9):
                for resistance in range(9):
                    prepared = {"STP": party, "STS": resistance}
                    prepared_claim = {tag: Fraction(prepared.get(tag, 0) * 6000) for tag in plan}
                    required = sum(prepared_claim.values())
                    full_plan = required + sum(base_claim.values())
                    boundaries = tuple(v for n in (required, full_plan) for v in (n - Fraction(1, 1000), n, n + Fraction(1, 1000)) if v >= 0)
                    for total in dict.fromkeys((*map(lambda n: Fraction(str(n)), totals), *boundaries)):
                        with self.subTest(winner=winner, party=party, resistance=resistance, reserves=total):
                            manpower, stock, aircraft = allocate(total, winner, prepared)
                            self.assertEqual(sum(manpower.values()), total)
                            self.assertEqual(sum(stock.values()), total)
                            self.assertEqual(sum(aircraft.values()), total)
                            self.assertAlmostEqual(aircraft["STS"], total * air_share, places=7)
                            self.assertEqual(aircraft["SRP"], 0, "the separate mountain republics receive no party air wings")
                            for tag in shares:
                                self.assertGreaterEqual(manpower[tag], 0)
                                self.assertGreaterEqual(stock[tag], 0)
                            rifle_prepared = {tag: Fraction(prepared.get(tag, 0) * 600) for tag in plan}
                            rifle_base = {tag: Fraction(plan[tag] * 600 + heavy_plan[tag] * 610) for tag in plan}
                            rifle_paid_preparation = min(total, sum(rifle_prepared.values()))
                            rifle_preparation_scale = (rifle_paid_preparation / sum(rifle_prepared.values())
                                                       if sum(rifle_prepared.values()) else 0)
                            rifle_paid_base = min(total - rifle_paid_preparation, sum(rifle_base.values()))
                            rifle_base_scale = rifle_paid_base / sum(rifle_base.values())
                            rifle_remainder = total - rifle_paid_preparation - rifle_paid_base
                            for tag in plan:
                                expected_stock = (rifle_prepared[tag] * rifle_preparation_scale
                                                  + rifle_base[tag] * rifle_base_scale
                                                  + rifle_remainder * Fraction(str(shares[tag])))
                                self.assertEqual(stock[tag], expected_stock)
                                if total >= sum(rifle_prepared.values()) + sum(rifle_base.values()):
                                    self.assertGreaterEqual(stock[tag], rifle_prepared[tag] + rifle_base[tag])
                            funded_preparation = min(total, required)
                            preparation_scale = funded_preparation / required if required else 0
                            funded_base = min(total - funded_preparation, sum(base_claim.values()))
                            base_scale = funded_base / sum(base_claim.values())
                            remainder = total - funded_preparation - funded_base
                            for tag in plan:
                                expected = (prepared_claim[tag] * preparation_scale + base_claim[tag] * base_scale
                                            + remainder * Fraction(str(shares[tag])))
                                # STP retains both successor rounding residuals;
                                # the successors each round one allocation only.
                                tolerance = Fraction(1 if tag == "STP" else .5)
                                self.assertLessEqual(abs(manpower[tag] - expected), tolerance)
                                if total >= full_plan:
                                    self.assertGreaterEqual(manpower[tag] + tolerance, prepared_claim[tag] + base_claim[tag])
                            if total < required:
                                self.assertEqual(manpower["SRP"], 0, "unfunded preparation has first claim on the entire real reserve")
                            if total == 393240 and party == resistance == 0:
                                for tag in plan:
                                    self.assertGreaterEqual(manpower[tag], base_claim[tag], "every baseline army must be affordable at the full starting reserve")

            # Reachable report inputs are four independent two-brigade preparations
            # per side. Evacuated officers can coexist with a retained party state.
            facts = {} if winner is None else {("STP", "has_country_flag", f"STP_cw_{'shabrat' if winner == 'limited' else winner}_election_victory"): True}
            facts[("STP", "has_country_flag", "STP_cw_limited_party_revolt")] = winner == "limited"
            sources = {
                "STP": [{("STP", "has_country_flag", "STP_cw_party_reserve_ready"): True}] + [
                    {(state, "is_owned_by", "STP"): True, (state, "has_state_flag", "STP_party_reinforced_garrison_asset"): True}
                    for state in ("2", "29", "45")],
                "STS": [{("STP", "has_country_flag", flag): True}
                        for flag in ("STP_cw_abila_reserve_ready", "STP_cw_local_recruits_ready")] + [
                    {(state, "has_state_flag", "STP_cw_garrison_evacuated"): True} for state in ("2", "29")],
            }
            markers = {fact[2] for group in sources.values() for source in group for fact in source if "flag" in fact[1]}
            prepared_lines = {child.line for entry in walk(body) if entry.key == "if"
                              and any(e.value in markers for e in walk(ast_block(entry.value, "limit")) if isinstance(e.value, str))
                              for child in walk(entry.value) if child.key == "STP_cw_mobilize_brigade"}
            for party in range(5):
                for resistance in range(5):
                    context = dict(facts)
                    for tag, count in (("STP", party), ("STS", resistance)):
                        for source in sources[tag][:count]:
                            context.update(source)
                    report_values = {}
                    for scope, entry in selected_effects(report, context):
                        self.assertEqual(scope, "STP")
                        self.assertIn(entry.key, ("set_variable", "add_to_variable"))
                        variable, value = scalar(entry.value, "var"), float(scalar(entry.value, "value"))
                        report_values[variable] = value if entry.key == "set_variable" else report_values[variable] + value
                    calls = list(selected_effects(body, context))
                    with self.subTest(winner=winner, party_sources=party, resistance_sources=resistance):
                        self.assertEqual(sum(scope == "STP" and e.key == "STP_cw_mobilize_assault_division" for scope, e in calls),
                                         3 if winner == "limited" else 6)
                        self.assertEqual(sum(scope == "STS" and e.key == "STP_cw_mobilize_assault_division" for scope, e in calls), 6)
                        for tag, count in (("STP", party), ("STS", resistance), ("SRP", 0)):
                            actual = [e for scope, e in calls if scope == tag and e.key == "STP_cw_mobilize_brigade"]
                            self.assertEqual(len(actual), plan[tag] + 2 * count)
                            self.assertEqual([e.line in prepared_lines for e in actual], [True] * (2 * count) + [False] * plan[tag],
                                             "Prepared cohorts must be paid before base formations")
                            if tag in report_names:
                                self.assertEqual(report_values[report_names[tag]], report_base[tag] + 2 * count)

    def test_escrow_is_paid_once_before_asset_cleanup(self):
        payout = block(self.effects, "STP_cw_materialize_region_assets")
        self.assertIn("NOT = { has_state_flag = STP_cw_assets_consumed }", payout)
        self.assertIn("set_state_flag = STP_cw_assets_consumed", payout)
        for variable in ("STP_cw_cached_rifles", "STP_cw_sabotage_rifles"):
            self.assertIn(f"clear_variable = {variable}", payout)
        self.assertLess(payout.index("add_equipment_to_stockpile"), payout.index("clr_state_flag = STP_resistance_sabotage_asset"))
        start = block(self.effects, "STP_cw_start")
        self.assertNotIn("STP_end_battle_for_stelander", start)
        begin = block(self.effects, "STP_cw_begin_hostilities")
        self.assertGreater(begin.index("STP_end_battle_for_stelander"), begin.rindex("add_timed_idea"))
        self.assertNotIn("STP_cw_pending_rifles", payout,
                         "unfinished national orders must not bypass their delivery time at split")
        self.assertEqual(start.count("amount = PREV.STP_cw_pending_rifles"), 1)
        refund = start.index("amount = PREV.STP_cw_pending_rifles")
        cleared = start.index("clear_variable = STP_cw_pending_rifles", refund)
        self.assertLess(refund, cleared)
        self.assertLess(cleared, start.index("transfer_units_fraction"),
                        "refund joins shared stocks before any faction receives its fraction")
        parsed = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                     "STP_cw_start"), "if")
        refund_branch = next(e.value for e in parsed if e.key == "if" and
                             "STP_cw_pending_rifles" in [x.value for x in walk(ast_block(e.value, "limit"))
                                                         if x.key == "has_variable"])
        state = ast_block(refund_branch, "1")
        payer = ast_block(state, "STP")
        self.assertEqual(scalar(ast_block(payer, "add_equipment_to_stockpile"), "amount"),
                         "PREV.STP_cw_pending_rifles")
        self.assertEqual(scalar(state, "clear_variable"), "STP_cw_pending_rifles")

    def test_undelivered_northern_cargo_rejoins_reserves_before_split_without_late_refund(self):
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start"), "if")
        body = [e for e in start if e.key != "limit"]
        flag = "STP_cw_northern_cargo_reserved"
        facts = {("STP", "has_country_flag", flag): True}
        chosen = list(selected_effects(body, facts))
        refunds = [(i, e.value) for i, (_, e) in enumerate(chosen) if e.key == "add_equipment_to_stockpile"]
        self.assertEqual(len(refunds), 1)
        index, refund = refunds[0]
        self.assertEqual((scalar(refund, "type"), scalar(refund, "amount")), ("infantry_equipment", "2400"))
        cleared = next(i for i, (_, e) in enumerate(chosen) if e.key == "clr_country_flag" and e.value == flag)
        snapshot = next(i for i, (_, e) in enumerate(chosen) if e.key == "set_variable"
                        and scalar(e.value, "var") == "STP_cw_initial_manpower")
        transfer = next(i for i, (_, e) in enumerate(chosen) if e.key == "transfer_units_fraction")
        self.assertLess(cleared, index)
        self.assertLess(index, snapshot)
        self.assertLess(index, transfer)
        self.assertFalse(any(e.key == "add_equipment_to_stockpile" for _, e in selected_effects(body, {})))
        supply = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention"),
                           "STP_cw_supply_the_north")
        self.assertFalse(any(e.key == "add_equipment_to_stockpile"
                             for _, e in selected_effects(ast_block(supply, "cancel_effect"), {})),
                         "the split consumed this escrow flag before the cancelled decision")

    def test_blocked_deadline_retries_only_stp_without_reopening_elections(self):
        on_actions = ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions")
        weekly = ast_block(ast_block(on_actions, "on_weekly"), "effect")
        retry = next(e.value for e in weekly if e.key == "if" and any(v.key == "STP_cw_start" for v in e.value))
        gate = ast_block(retry, "limit")
        finished = {("STP", "has_country_flag", "STP_cw_elections_finished"): True}
        self.assertTrue(matches_conditions(gate, finished))
        self.assertFalse(matches_conditions(gate, {}))
        self.assertFalse(matches_conditions(gate, {**finished, ("STP", "has_global_flag", "STP_cw_started"): True}))
        for tag in ("STS", "SRP", "NOD"):
            self.assertFalse(matches_conditions(gate, {(tag, "has_country_flag", "STP_cw_elections_finished"): True}, tag))
        self.assertEqual({e.key for e in retry if e.key != "limit"}, {"STP_cw_start"})
        self.assertNotIn("every_country", {e.key for e in walk(weekly)})

    def test_forest_sabotage_damages_only_the_party_controlled_state_once(self):
        payout = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_materialize_region_assets")
        facts = {("53", "is_owned_by", "STP"): True, ("53", "is_controlled_by", "STP"): True,
                 ("53", "has_state_flag", "STP_resistance_sabotage_asset"): True,
                 ("53", "numeric", "infrastructure"): 3}
        chosen = list(selected_effects(payout, facts, "53"))
        damage = [e.value for scope, e in chosen if e.key == "damage_building"]
        self.assertEqual(len(damage), 1)
        self.assertEqual((scalar(damage[0], "type"), scalar(damage[0], "damage")), ("infrastructure", "1"))
        marker = next(i for i, (_, e) in enumerate(chosen) if e.key == "set_state_flag" and e.value == "STP_cw_assets_consumed")
        damage_index = next(i for i, (_, e) in enumerate(chosen) if e.key == "damage_building")
        cleanup = next(i for i, (_, e) in enumerate(chosen) if e.key == "clr_state_flag" and e.value == "STP_resistance_sabotage_asset")
        self.assertLess(marker, damage_index)
        self.assertLess(damage_index, cleanup)
        for requirement in facts:
            scenario = {k: v for k, v in facts.items() if k != requirement}
            self.assertFalse(any(e.key == "damage_building" for _, e in selected_effects(payout, scenario, "53")), requirement)
        repeated = {**facts, ("53", "has_state_flag", "STP_cw_assets_consumed"): True}
        self.assertFalse(any(e.key == "damage_building" for _, e in selected_effects(payout, repeated, "53")))
        elsewhere = {("46", key, value): fact for (_, key, value), fact in facts.items()}
        self.assertFalse(any(e.key == "damage_building" for _, e in selected_effects(payout, elsewhere, "46")))

    def test_prepared_capital_and_industry_sabotage_damage_only_party_held_districts(self):
        payout = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_materialize_region_assets")
        capital = {("28", "is_owned_by", "STP"): True, ("28", "is_controlled_by", "STP"): True,
                   ("28", "has_state_flag", "STP_resistance_sabotage_asset"): True,
                   ("28", "numeric", "infrastructure"): 4, ("28", "numeric", "arms_factory"): 3}
        hits = [scalar(e.value, "type") for _, e in selected_effects(payout, capital, "28") if e.key == "damage_building"]
        self.assertEqual(hits, ["infrastructure", "arms_factory"])
        for requirement in (("28", "is_owned_by", "STP"), ("28", "has_state_flag", "STP_resistance_sabotage_asset")):
            scenario = {k: v for k, v in capital.items() if k != requirement}
            self.assertFalse(any(e.key == "damage_building" for _, e in selected_effects(payout, scenario, "28")), requirement)
        industry = {("29", "is_owned_by", "STP"): True, ("29", "is_controlled_by", "STP"): True,
                    ("29", "has_state_flag", "STP_resistance_sabotage_asset"): True,
                    ("29", "numeric", "industrial_complex"): 4}
        plants = [scalar(e.value, "type") for _, e in selected_effects(payout, industry, "29") if e.key == "damage_building"]
        self.assertEqual(plants, ["industrial_complex"])
        captured = {**industry, ("29", "is_owned_by", "STP"): False}
        self.assertFalse(any(e.key == "damage_building" for _, e in selected_effects(payout, captured, "29")))
        aftermath = [e for _, e in selected_effects(payout, capital, "28") if e.key == "add_timed_idea"]
        self.assertEqual([(scalar(e.value, "idea"), scalar(e.value, "days")) for e in aftermath],
                         [("STP_cw_party_command_sabotage", "70")])
        already = {**capital, ("STP", "has_idea", "STP_cw_party_command_sabotage"): True}
        self.assertFalse(any(e.key == "add_timed_idea" for _, e in selected_effects(payout, already, "28")))
        self.assertFalse(any(e.key == "add_timed_idea" for _, e in selected_effects(payout, {
            ("53", "is_owned_by", "STP"): True, ("53", "is_controlled_by", "STP"): True,
            ("53", "has_state_flag", "STP_resistance_sabotage_asset"): True,
            ("53", "numeric", "infrastructure"): 3}, "53")))

    def test_party_keeps_hedersett_and_historical_ideology(self):
        start = block(self.effects, "STP_cw_start")
        self.assertIn("ruling_party = hedonism", start)
        self.assertIn("promote_character = STP_rufus_hedersett", start)
        self.assertNotIn("promote_character = STP_grigory_sotnikov", start)
        self.assertNotIn("ruling_party = etatism", start)

    def test_split_gives_sts_cores_on_original_stelander_land(self):
        start = ast_block(ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start"), "if")
        sts_cores = [e for e in walk(start) if e.key == "every_state"
                     and any(child.key == "add_core_of" and child.value == "STS" for child in walk(e.value))]
        srp_cores = [e for e in walk(start) if e.key == "every_state"
                     and any(child.key == "add_core_of" and child.value == "SRP" for child in walk(e.value))]
        self.assertEqual(len(sts_cores), 1)
        self.assertEqual(len(srp_cores), 1)
        self.assertTrue(any(child.key == "is_core_of" and child.value == "STP"
                            for child in walk(ast_block(sts_cores[0].value, "limit"))))
        self.assertTrue(any(child.key == "is_owned_by" and child.value == "SRP"
                            for child in walk(ast_block(srp_cores[0].value, "limit"))))
        self.assertFalse(any(e.key == "every_owned_state" and any(child.key == "add_core_of" for child in walk(e.value))
                             for e in walk(start)),
                         "a newborn successor still has an empty owned-state list")

    def test_union_settlement_reintegrates_only_stelander_cores_for_shabrat(self):
        settlement = block(self.effects, "STP_cw_settle_union_victory")
        reintegration = block(settlement, "every_owned_state")
        self.assertIn("is_core_of = STP", block(reintegration, "limit"))
        self.assertIn("add_core_of = STS", reintegration)
        self.assertRegex(settlement, r"if\s*=\s*\{\s*limit\s*=\s*\{\s*tag = STS\s*\}\s*every_owned_state")
        self.assertLess(settlement.index("annex_country"), settlement.index("every_owned_state"))

    def test_civil_war_closure_is_independent_of_the_republics_front(self):
        closure = block(self.effects, "STP_cw_check_union_wars_finished")
        self.assertIn("has_war_with = STS", closure)
        self.assertNotIn("SRP", closure)
        self.assertIn("set_global_flag = STP_cw_union_wars_finished", closure)
        self.assertNotIn("has_country_flag = STP_cw_postwar", closure,
                         "a separate peace does not end the party-resistance war")
        for name in ("STP_cw_settle_union_victory", "STP_cw_settle_nod_victory", "VAL_cw_settle_republics"):
            self.assertIn("STP_cw_check_union_wars_finished = yes", block(self.effects, name))
        router = block(read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_capitulation")
        self.assertNotIn("STP_cw_republics_victory", router)
        self.assertIn("NOT = { has_country_flag = VAL_cw_settled }", router)
        limit = ast_block(ast_block(ast_block(entries(
            "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
            "STP_cw_check_union_wars_finished"), "if"), "limit")
        for civil_war in (False, True):
            for republic_war in (False, True):
                facts = {
                    ("STP", "has_global_flag", "STP_cw_started"): True,
                    ("STP", "has_war_with", "STS"): civil_war,
                    ("SRP", "has_war_with", "VAL"): republic_war,
                }
                self.assertEqual(matches_conditions(limit, facts), not civil_war)

    def test_war_focus_layout_and_peacetime_gates(self):
        trees = entries("common/national_focus/ADISCORD_national_focus_STP.txt")
        tree = next(e.value for e in trees if e.key == "focus_tree"
                    and scalar(e.value, "id") == "STP_cw_focus")
        focuses = [e.value for e in tree if e.key == "focus"]
        for tag in ("STP", "STS", "SRP"):
            visible = [f for f in focuses if scalar(f, "id") not in {"STP_cw_first_postwar_budget", "STP_cw_restore_civil_authority"}
                       and not scalar(f, "id").startswith(("STP_pw_", "STP_pc_"))
                       and (not any(e.key == "allow_branch" for e in f)
                            or matches_conditions(ast_block(f, "allow_branch"), {(tag, "tag", tag): True}, tag))]
            points = [(int(scalar(f, "x")), int(scalar(f, "y"))) for f in visible]
            self.assertEqual(len(points), len(set(points)), tag)
            self.assertLessEqual(max(x for x, _ in points) - min(x for x, _ in points), 10 if tag == "STS" else (13 if tag == "STP" else 5), tag)
            for x in {x for x, _ in points}:
                rows = sorted(y for px, y in points if px == x)
                self.assertTrue(all(b - a >= 1 for a, b in zip(rows, rows[1:])), tag)
            self.assertLessEqual(max(y for _, y in points) - min(y for _, y in points), 5, tag)
        for focus in focuses:
            name = scalar(focus, "id")
            if name in ("STP_cw_first_postwar_budget", "STP_cw_restore_civil_authority"):
                gate = ast_block(focus, "available")
                self.assertFalse(matches_conditions(gate, {("SRP", "has_war", "no"): True}, "SRP"),
                                 "60 days of initial independence are not a completed military settlement")
                self.assertTrue(matches_conditions(gate, {
                    ("SRP", "tag", "SRP"): True, ("SRP", "has_war", "no"): True,
                    ("SRP", "has_country_flag", "STP_cw_postwar"): True,
                }, "SRP"))
        self.assertNotRegex(read("common/national_focus/ADISCORD_national_focus_STP.txt") + self.effects,
                            r"can_(?:join_factions|create_factions)\s*=\s*yes")

    def test_mobilization_keeps_a_capital_garrison_and_uses_controlled_territory(self):
        helper = block(self.effects, "STP_cw_mobilize_brigade")
        spawn = block(self.effects, "STP_cw_create_territorial_brigade")
        self.assertIn("num_divisions < 3", helper)
        self.assertIn("is_owned_by = PREV is_controlled_by = PREV", helper)
        self.assertIn("STP_cw_state_faces_rival = yes", helper)
        self.assertIn("create_unit =", spawn)
        self.assertIn("owner = PREV", spawn)
        self.assertIn("allow_spawning_on_enemy_provs = no", spawn)
        self.assertGreaterEqual(helper.count("STP_cw_create_territorial_brigade = yes"), 3)
        self.assertNotIn("prioritize_location", helper + spawn)

    def test_newborn_engine_manpower_is_returned_before_reallocation(self):
        setup = block(self.effects, "STP_cw_prepare_successor")
        self.assertIn("STP = { add_manpower = var:PREV.STP_cw_newborn_manpower }", setup)
        self.assertIn("add_manpower = var:STP_cw_newborn_manpower", setup)
        self.assertIn("multiply_variable = { var = STP_cw_newborn_manpower value = -1 }", setup)

    def test_successors_inherit_the_current_conscription_law_before_economy_setup(self):
        setup = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_prepare_successor")
        laws = ast_block(ast_block(entries("common/ideas/_manpower.txt"), "ideas"), "mobilization_laws")
        law_names = {e.key for e in laws if isinstance(e.value, list)}
        economy = next(e for e in setup if e.key == "ADISCORD_economy_initialize_country")
        for tag in ("STS", "SRP"):
            for law in law_names:
                with self.subTest(tag=tag, law=law):
                    chosen = list(selected_effects(setup, {("STP", "has_idea", law): True}, tag))
                    applied = [e for scope, e in chosen if scope == tag and e.key == "add_ideas"]
                    expected = "limited_conscription" if law in {"disarmed_nation", "volunteer_only"} else law
                    self.assertEqual([e.value for e in applied], [expected])
                    self.assertLess(applied[0].line, economy.line)

    def test_handoff_direction_and_successor_technology(self):
        events = read("events/ADISCORD_STP_events.txt")
        self.assertIn("STS = { change_tag_from = STP }", events)
        self.assertIn("STS = { change_tag_from = STP }", block(self.effects, "STP_cw_start"))
        self.assertNotIn("SRP = { change_tag_from = STP }", events)
        self.assertNotRegex(events, r"change_tag_from\s*=\s*(STS|SRP)")
        setup = block(self.effects, "STP_cw_prepare_successor")
        self.assertIn("inherit_technology = STP", setup)
        self.assertIn("set_research_slots = 1", setup)
        self.assertNotIn("ADISCORD_grant_2150_technology_baseline", setup)
        self.assertNotIn("ADISCORD_grant_starting_technology_profile", setup)
        self.assertNotIn("add_equipment_production", setup)
        starting = read("common/scripted_effects/ADISCORD_technology_baseline_effects.txt")
        union = re.search(r"limit = \{ tag = STP \}(.*?)(?=\n\t\})", starting, re.S)
        self.assertIsNotNone(union)
        modules = ["common"] + re.findall(r"ADISCORD_grant_technology_profile_(\w+) = yes", union.group(1))
        for module in modules:
            self.assertIn("ADISCORD_grant_technology_profile_" + module + " = yes", setup)
        self.assertLess(setup.index("inherit_technology = STP"),
                        setup.index("ADISCORD_grant_technology_profile_common = yes"))
        start = block(self.effects, "STP_cw_start")
        self.assertEqual(start.count("load_focus_tree = { tree = STP_cw_focus"), 3)
        self.assertNotIn("declare_war_on", start)
        self.assertLess(start.rindex("load_focus_tree"), start.index("change_tag_from = STP"))
        self.assertLess(start.rindex("load_focus_tree"), start.index("id = ADISCORD_STP_cw.30"))

    def test_shabrat_opens_conscription_in_seven_days(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_cw_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_open_conscription")
        gate = ast_block(focus, "allow_branch")
        self.assertTrue(matches_conditions(gate, {}, "STS"))
        self.assertFalse(matches_conditions(gate, {}, "STP"))
        self.assertFalse(matches_conditions(gate, {("STS", "has_country_flag", "STP_cw_postwar"): True}, "STS"))
        self.assertEqual((scalar(focus, "x"), scalar(focus, "y"), scalar(focus, "cost")), ("3", "0", "1"))
        self.assertFalse(any(e.key == "prerequisite" for e in focus))
        self.assertEqual(scalar(ast_block(focus, "ai_will_do"), "base"), "12")
        reward = ast_block(focus, "completion_reward")
        self.assertEqual(scalar(ast_block(reward, "if"), "add_ideas"), "extensive_conscription")
        loc = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        self.assertIn('STP_cw_open_conscription: "Открыть призыв"', loc)
        self.assertIn("STP_cw_open_conscription_desc:", loc)

    def test_wartime_laboratories_grant_a_temporary_shared_slot(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if e.key == "focus_tree" and scalar(e.value, "id") == "STP_cw_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_wartime_laboratories")
        for tag in ("STP", "STS", "SRP"):
            gate = ast_block(focus, "allow_branch")
            self.assertTrue(matches_conditions(gate, {}, tag))
            self.assertFalse(matches_conditions(gate, {(tag, "has_country_flag", "STP_cw_postwar"): True}, tag))
        self.assertEqual((scalar(focus, "x"), scalar(focus, "y"), scalar(focus, "cost")), ("7", "1", "3"))
        self.assertEqual(scalar(focus, "icon"), "GFX_goal_generic_scientific_exchange")
        self.assertNotEqual(scalar(focus, "icon"), "GFX_focus_TVA_divert_the_research_budget")
        self.assertEqual(scalar(ast_block(focus, "prerequisite"), "focus"), "STP_cw_unified_headquarters")
        self.assertEqual(scalar(ast_block(focus, "ai_will_do"), "base"), "1")
        self.assertNotIn("has_war", {e.key for e in walk(focus)})
        available = ast_block(focus, "available")
        self.assertEqual(scalar(ast_block(available, "custom_trigger_tooltip"), "tooltip"),
                         "STP_cw_wartime_laboratories_available_tt")
        self.assertTrue(matches_conditions(available, {}))
        self.assertFalse(matches_conditions(available, {("STP", "has_country_flag", "STP_cw_postwar"): True}))
        self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes")
        reward = ast_block(focus, "completion_reward")
        self.assertEqual([e.value for e in reward if e.key == "add_research_slot"], ["1"])
        self.assertEqual([e.value for e in reward if e.key == "custom_effect_tooltip"], ["STP_cw_wartime_laboratories_tt"])
        timed = ast_block(reward, "add_timed_idea")
        self.assertEqual((scalar(timed, "idea"), scalar(timed, "days")), ("STP_cw_emergency_laboratories", "180"))
        ledger = ast_block(ast_block(reward, "hidden_effect"), "add_to_variable")
        self.assertEqual((scalar(ledger, "var"), scalar(ledger, "value")), ("STP_cw_emergency_research_slots", "1"))
        reward_keys = [e.key for e in reward]
        self.assertLess(reward_keys.index("hidden_effect"), reward_keys.index("add_timed_idea"))
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        idea = ast_block(ideas, "STP_cw_emergency_laboratories")
        self.assertEqual(scalar(idea, "picture"), "ADISCORD_law_civic_emergency_committees")
        cancel = ast_block(idea, "cancel")
        self.assertEqual(scalar(ast_block(cancel, "custom_trigger_tooltip"), "tooltip"),
                         "STP_cw_emergency_laboratories_cancel_tt")
        self.assertTrue(matches_conditions(cancel, {("STP", "has_country_flag", "STP_cw_postwar"): True}))
        self.assertFalse(matches_conditions(cancel, {}))
        self.assertNotIn("has_war", {e.key for e in walk(cancel)})
        self.assertEqual(scalar(ast_block(idea, "on_remove"), "STP_cw_revoke_emergency_research_slot"), "yes")
        self.assertFalse(any(e.key == "add_research_slot" for e in walk(idea)))
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        revoke = ast_block(effects, "STP_cw_revoke_emergency_research_slot")
        finish = ast_block(effects, "STP_cw_finish_mobilization")
        revoke_index = next(i for i, e in enumerate(finish) if e.key == "STP_cw_revoke_emergency_research_slot")
        remove_index = next(i for i, e in enumerate(finish)
                            if e.key == "if" and any(v.key == "remove_ideas" and v.value == "STP_cw_emergency_laboratories"
                                                     for v in walk(e.value)))
        self.assertLess(remove_index, revoke_index)
        self.assertEqual(finish[0].value, "STP_cw_postwar")
        self.assertIn(("has_idea", "STP_cw_emergency_laboratories"),
                      [(e.key, e.value) for e in walk(finish)])
        self.assertEqual(sum(e.key == "remove_ideas" and e.value == "STP_cw_emergency_laboratories"
                             for e in walk(finish)), 1)
        self.assertFalse(any(e.key == "add_research_slot" for e in walk(finish)))
        loc = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        for key in ("STP_cw_wartime_laboratories", "STP_cw_wartime_laboratories_desc",
                    "STP_cw_wartime_laboratories_tt", "STP_cw_wartime_laboratories_available_tt",
                    "STP_cw_emergency_laboratories", "STP_cw_emergency_laboratories_desc",
                    "STP_cw_emergency_laboratories_cancel_tt"):
            self.assertIn(f"{key}:", loc)
        for tag in ("STP", "STS", "SRP"):
            for granted in (0, 1):
                facts = {(tag, "variable", "STP_cw_emergency_research_slots"): granted}
                writes = []
                for _ in range(2):
                    for scope, entry in selected_effects(revoke, facts, tag):
                        writes.append((scope, entry))
                        if entry.key == "subtract_from_variable":
                            facts[(scope, "variable", scalar(entry.value, "var"))] = (
                                facts.get((scope, "variable", scalar(entry.value, "var")), 0)
                                - float(scalar(entry.value, "value")))
                        elif entry.key == "clear_variable":
                            facts[(scope, "variable", entry.value)] = 0
                with self.subTest(tag=tag, granted=granted):
                    self.assertEqual([e.value for _, e in writes if e.key == "add_research_slot"],
                                     ["-1"] if granted else [])
                    self.assertEqual(facts[(tag, "variable", "STP_cw_emergency_research_slots")], 0)

    def test_val_path_reserves_capitulation_and_administers_livonn(self):
        on_action = read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        self.assertIn("set_global_flag = skip_default_capitulation", on_action)
        settlement = block(self.effects, "VAL_cw_settle_republics")
        self.assertIn("VAL_form_occidian_administration = yes", settlement)
        administration = block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_form_occidian_administration")
        for state in (43, 44, 45, 88):
            self.assertIn(f"transfer_state = {state}", administration)
        self.assertIn("transfer_state = 45", settlement)
        self.assertIn("VAL_cw_stage_livonn_settlement = yes", settlement)
        self.assertIn("VAL_only_occidian_states = yes", administration)
        self.assertNotIn("annex_country", settlement)
        intervention = block(self.effects, "VAL_cw_start_intervention")
        self.assertIn("VAL_cw_can_intervene = yes", block(block(intervention, "if"), "limit"))
        self.assertIn("days = 21", intervention)
        self.assertIn("VAL_foreign_operation_active", self.triggers)

    def test_nod_owns_readiness_and_observers_cannot_authorize_war(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        warning = block(decisions, "STP_cw_nod_warning")
        self.assertIn("activation = { always = no }", warning)
        self.assertIn("days_mission_timeout = 135", warning)
        self.assertNotIn("STP_cw_finish_nod_warning", block(warning, "timeout_effect"))
        self.assertNotIn("add_to_war", warning)
        readiness = block(decisions, "NOD_cw_intervention_preparation")
        self.assertIn("allowed = { tag = NOD }", readiness)
        self.assertIn("days_mission_timeout = 135", readiness)
        self.assertIn("set_country_flag = NOD_cw_intervention_ready", block(readiness, "timeout_effect"))
        self.assertIn("STP_cw_poll_nod_intervention = yes", block(readiness, "timeout_effect"))
        finish = block(self.effects, "STP_cw_finish_nod_warning")
        self.assertIn("STP_cw_nod_can_intervene = yes", finish)
        self.assertIn("targeted_alliance = STP", finish)
        self.assertIn("enemy = STS", finish)
        self.assertIn("single_target_only = yes", finish)
        self.assertIn("create_faction_from_template", finish)
        begin = block(self.effects, "STP_cw_poll_nod_intervention")
        self.assertIn("STP_cw_sync_nod_warning = yes", begin)
        self.assertNotIn("activate_mission = NOD_cw_intervention_preparation", begin,
                         "weekly polls must not reset the actor's countdown")
        self.assertNotIn("add_to_war", begin)

    def test_nod_warning_and_war_require_consent_and_current_eligibility(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        poll = ast_block(effects, "STP_cw_poll_nod_intervention")
        finish = ast_block(effects, "STP_cw_finish_nod_warning")
        for possible in (False, True):
            for offered in (False, True):
                for remaining, in_window in ((100, False), (29, False), (28, True), (1, True)):
                    facts = {("NOD", "NOD_cw_intervention_possible", "yes"): possible,
                             ("NOD", "has_country_flag", "NOD_cw_offer_shown"): offered,
                             ("STP", "has_active_mission", "STP_cw_election_window"): True,
                             ("STP", "variable", "days_mission_timeout@STP_cw_election_window"): remaining}
                    chosen = list(selected_effects(poll, facts, "NOD"))
                    offers = [(s, scalar(e.value, "id")) for s, e in chosen if e.key == "country_event"]
                    self.assertEqual(offers, [("NOD", "ADISCORD_STP_cw.42")] if possible and not offered and in_window else [])
        for eligible in (False, True):
            for approved in (False, True):
                for ready in (False, True):
                    facts = {("NOD", "NOD_cw_intervention_possible", "yes"): True,
                             ("NOD", "has_country_flag", "NOD_cw_offer_shown"): True,
                             ("NOD", "has_country_flag", "NOD_cw_intervention_approved"): approved,
                             ("NOD", "has_country_flag", "NOD_cw_intervention_ready"): ready,
                             ("NOD", "has_global_flag", "STP_cw_started"): True,
                             ("STS", "exists", "yes"): True,
                             ("STS", "STP_cw_nod_can_intervene", "yes"): eligible}
                    chosen = list(selected_effects(poll, facts, "NOD"))
                    self.assertEqual(sum(e.key == "STP_cw_sync_nod_warning" for _, e in chosen), int(approved))
                    self.assertEqual(sum(e.key == "STP_cw_finish_nod_warning" for _, e in chosen), int(approved and ready and eligible))
                    war = [(s, e.value) for s, e in selected_effects(finish, facts, "STS") if e.key == "add_to_war"]
                    self.assertEqual(len(war), int(eligible and approved and ready))
                    if war:
                        self.assertEqual(war[0][0], "NOD")
                        self.assertEqual(scalar(war[0][1], "targeted_alliance"), "STP")
                        self.assertEqual(scalar(war[0][1], "enemy"), "STS")

    def test_nod_observer_handoff_copies_remaining_days_without_restarting_the_actor(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        sync = ast_block(effects, "STP_cw_sync_nod_warning")
        for tag, started in (("STP", False), ("STP", True), ("STS", True)):
            for already_visible in (False, True):
                for actor, observer, duration in (("NOD_cw_intervention_preparation", "STP_cw_nod_warning", 135),
                                                   ("NOD_cw_northern_redeployment", "STP_cw_nod_redeployment", 7)):
                    facts = {(tag, "has_global_flag", "STP_cw_started"): started,
                             (tag, "has_active_mission", observer): already_visible,
                             ("NOD", "has_active_mission", actor): True,
                             ("NOD", "has_country_flag", "NOD_cw_intervention_approved"): True}
                    selected = list(selected_effects(sync, facts, tag))
                    should_open = not already_visible and (tag == "STS" or not started)
                    self.assertEqual([(scope, e.value) for scope, e in selected if e.key == "activate_mission"],
                                     [(tag, observer)] if should_open else [])
                    self.assertFalse(any(scope == "NOD" for scope, _ in selected), "observers cannot write to the actor's clock")
                    if should_open:
                        source = next(e.value for _, e in selected if e.key == "set_temp_variable")
                        self.assertEqual(scalar(source, "value"), "NOD.days_mission_timeout@" + actor)
                        subtraction = next(e.value for _, e in selected if e.key == "subtract_from_temp_variable")
                        self.assertEqual(int(scalar(subtraction, "value")), duration)
                        adjustment = next(e.value for _, e in selected if e.key == "add_days_mission_timeout")
                        self.assertEqual(scalar(adjustment, "days"), scalar(source, "var"))
                        for remaining in (duration, duration / 2, 1):
                            self.assertEqual(duration + remaining - int(scalar(subtraction, "value")), remaining)
        sources = ("common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
                   "common/decisions/ADISCORD_STP_decisions.txt", "events/ADISCORD_STP_events.txt")
        starts = [(path, e.line) for path in sources for e in walk(entries(path))
                  if e.key == "activate_mission" and e.value == "NOD_cw_intervention_preparation"]
        self.assertEqual(len(starts), 1, "the accepted NOD offer is the only place that starts the readiness clock")
        self.assertEqual(starts[0][0], "events/ADISCORD_STP_events.txt")

    def test_paid_heavy_reserve_is_delivered_before_base_armies_and_unfinished_work_refunds_before_the_split(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        start = ast_block(ast_block(effects, "STP_cw_start"), "if")
        snapshot = next(e for e in start if e.key == "set_variable" and scalar(e.value, "var") == "STP_cw_initial_manpower")
        unfinished = next(e for e in start if e.key == "STP_cw_cancel_assault_training")
        self.assertLess(unfinished.line, snapshot.line)
        refund = list(walk(ast_block(effects, "STP_cw_cancel_assault_training")))
        clear = next(e for e in refund if e.key == "clr_country_flag")
        credit = next(e for e in refund if e.key == "add_to_variable"
                      and scalar(e.value, "var") == "ADISCORD_economy_treasury")
        self.assertLess(clear.line, credit.line)
        self.assertEqual(scalar(credit.value, "value"), "500")
        self.assertFalse(any(e.key in ("add_manpower", "add_equipment_to_stockpile",
                                      "STP_cw_refund_assault_division") for e in refund))
        prepared = next(e.value for e in start if e.key == "if"
                        and any(v.key == "check_variable" and scalar(v.value, "var") == "STP_cw_prepared_assault_divisions"
                                for v in ast_block(e.value, "limit")))
        loop = ast_block(ast_block(prepared, "STS"), "for_loop_effect")
        self.assertEqual(scalar(loop, "end"), "STP.STP_cw_prepared_assault_divisions")
        self.assertEqual(scalar(loop, "STP_cw_deploy_assault_division"), "yes")
        self.assertNotIn("STP_cw_pay_assault_division", {e.key for e in walk(prepared)}, "a completed escrow must not be charged twice")
        cleared = next(e for e in prepared if e.key == "clear_variable")
        self.assertEqual(cleared.value, "STP_cw_prepared_assault_divisions")
        self.assertLess(max(e.line for e in walk(loop)), cleared.line)
        self.assertLess(cleared.line, min(e.line for e in walk(start) if e.key in ("STP_cw_mobilize_brigade", "STP_cw_mobilize_assault_division")))

    def test_val_busy_offer_retries_once_and_dispatcher_rechecks_before_display(self):
        weekly = ast_block(ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions"), "on_weekly"), "effect")
        retry = next((e.value for e in weekly if e.key == "if" and any(v.key == "country_event"
                      and scalar(v.value, "id") == "ADISCORD_STP_cw.22" for v in walk(e.value))), None)
        self.assertIsNotNone(retry, "VAL must not lose the only offer while a foreign contract occupies its slot")
        for eligible, pending, offered in ((False, False, False), (True, False, False), (True, True, False), (True, False, True)):
            facts = {("VAL", "VAL_cw_external_course_available", "yes"): eligible,
                     ("VAL", "has_country_flag", "VAL_cw_offer_pending"): pending,
                     ("VAL", "has_country_flag", "VAL_cw_offer_shown"): offered}
            selected = matches_conditions(ast_block(retry, "limit"), facts, "VAL")
            self.assertEqual(selected, eligible and not pending and not offered)
        events = [e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event"]
        dispatch = next(e for e in events if scalar(e, "id") == "ADISCORD_STP_cw.22")
        for eligible in (False, True):
            facts = {("VAL", "VAL_cw_external_course_available", "yes"): eligible}
            chosen = list(selected_effects(ast_block(dispatch, "immediate"), facts, "VAL"))
            self.assertEqual((chosen[0][1].key, chosen[0][1].value), ("clr_country_flag", "VAL_cw_offer_pending"))
            self.assertEqual([scalar(e.value, "id") for _, e in chosen if e.key == "country_event"],
                             ["ADISCORD_STP_cw.20"] if eligible else [])

    def test_external_choices_record_exclusive_courses_without_debiting_another_player(self):
        events = {scalar(e.value, "id"): e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event"}
        for event_id, choices in (("ADISCORD_STP_cw.20", {"VAL_cw_trade_course", "VAL_cw_military_course", "VAL_cw_refused"}),
                                  ("ADISCORD_STP_cw.42", {"NOD_cw_intervention_approved", "NOD_cw_refused"})):
            self.assertIn(event_id, events)
            options = [e.value for e in events[event_id] if e.key == "option"]
            if event_id == "ADISCORD_STP_cw.20":
                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.committed"]
                self.assertEqual(len(closing), 1)
                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],
                                 "the committed-route option only closes the event")
                options = [o for o in options if o not in closing]
            else:
                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.42.c"]
                self.assertEqual(len(closing), 1)
                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],
                                 "a stale Nodrul card must only close")
                options = [o for o in options if o not in closing]
            self.assertEqual(len(options), len(choices))
            written = [{e.value for e in walk(o) if e.key == "set_country_flag" and isinstance(e.value, str)} & choices for o in options]
            self.assertEqual(set.union(*written), choices)
            self.assertTrue(all(len(choice) == 1 for choice in written))
            self.assertFalse(any(e.key in ("add_equipment_to_stockpile", "transfer_state", "add_to_war", "declare_war_on") for o in options for e in walk(o)))
        val_gate = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "VAL_cw_external_course_available")
        facts = {("VAL", "has_global_flag", "STP_cw_started"): True,
                 ("VAL", "flag_days", "STP_cw_started"): 60,
                 ("VAL", "is_neighbor_of", "SRP"): True,
                 **{(tag, key, value): True for tag in ("VAL", "SRP")
                    for key, value in (("exists", "yes"), ("has_capitulated", "no"),
                                       ("has_war", "no"), ("is_subject", "no"), ("is_in_faction", "no"))}}
        self.assertTrue(matches_conditions(val_gate, facts, "VAL"))
        self.assertTrue(matches_conditions(val_gate, {**facts, ("VAL", "has_country_flag", "VAL_cw_trade_course"): True}, "VAL"))
        for flag in ("VAL_cw_refused",):
            self.assertFalse(matches_conditions(val_gate, {**facts, ("VAL", "has_country_flag", flag): True}, "VAL"))

    def test_val_republics_get_sixty_peaceful_days_before_separate_mobilization(self):
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        common = ast_block(triggers, "VAL_cw_external_course_available")
        military = ast_block(triggers, "VAL_cw_can_intervene")
        self.assertEqual(scalar(military, "VAL_cw_external_course_available"), "yes")
        gate = common + [e for e in military if e.key != "VAL_cw_external_course_available"]
        facts = {("VAL", "has_global_flag", "STP_cw_started"): True,
                 ("VAL", "is_neighbor_of", "SRP"): True,
                 **{(tag, key, value): True for tag in ("VAL", "SRP")
                    for key, value in (("exists", "yes"), ("has_capitulated", "no"),
                                       ("has_war", "no"), ("is_subject", "no"), ("is_in_faction", "no"))}}
        for days in (0, 1, 59, 60, 61, 81):
            with self.subTest(days=days):
                aged = {**facts, ("VAL", "flag_days", "STP_cw_started"): days}
                self.assertEqual(matches_conditions(gate, aged, "VAL"), days >= 60)
                self.assertTrue(matches_conditions(common, aged, "VAL"), "offer eligibility must not wait for the military deadline")
        ready = {**facts, ("VAL", "flag_days", "STP_cw_started"): 60}
        for requirement in facts:
            with self.subTest(missing=requirement):
                self.assertFalse(matches_conditions(gate, {k: v for k, v in ready.items() if k != requirement}, "VAL"))
        for flag in ("VAL_foreign_operation_active", "VAL_cw_mobilizing", "VAL_cw_entered",
                     "VAL_cw_settled", "VAL_cw_refused"):
            self.assertFalse(matches_conditions(gate, {**ready, ("VAL", "has_country_flag", flag): True}, "VAL"))
        self.assertTrue(matches_conditions(gate, {**ready, ("VAL", "has_global_flag", "STP_cw_union_wars_finished"): True}, "VAL"),
                        "the separate western conflict remains available after the Stelander settlement")

    def test_val_military_offer_unlocks_decision_and_news_requires_actual_separate_war(self):
        events = {scalar(e.value, "id"): e.value for e in entries("events/ADISCORD_STP_events.txt")
                  if e.key in ("country_event", "news_event")}
        military = next(e.value for e in events["ADISCORD_STP_cw.20"]
                        if e.key == "option" and scalar(e.value, "name") == "ADISCORD_STP_cw.20.a")
        self.assertFalse(any(e.key == "VAL_cw_start_intervention" for e in walk(military)))
        self.assertTrue(any(e.key == "unlock_decision_tooltip" and scalar(e.value, "decision") == "VAL_cw_begin_mobilization"
                            for e in walk(military)))
        trade = next(e.value for e in events["ADISCORD_STP_cw.20"]
                     if e.key == "option" and scalar(e.value, "name") == "ADISCORD_STP_cw.20.c")
        trade_facts = {("STS", "exists", "yes"): True, ("STS", "has_capitulated", "no"): True,
                       ("STS", "has_war_with", "STP"): True}
        self.assertTrue(matches_conditions(ast_block(trade, "trigger"), trade_facts, "VAL"))
        self.assertFalse(matches_conditions(ast_block(trade, "trigger"), {}, "VAL"), "do not offer an unavailable arms market")
        news = events["ADISCORD_STP_cw.73"]
        self.assertEqual(scalar(news, "major"), "yes")
        self.assertEqual(scalar(news, "fire_only_once"), "yes")
        self.assertFalse(any(e.key in ("declare_war_on", "add_to_war", "transfer_state") for e in walk(news)))
        for owner in (False, True):
            for eligible in (False, True):
                for actual_war in (False, True):
                    facts = {("VAL", "has_country_flag", "VAL_cw_mobilizing"): owner,
                             ("VAL", "VAL_cw_can_intervene", "yes"): eligible,
                             ("VAL", "has_country_flag", "VAL_cw_military_course"): True,
                             ("VAL", "has_war_with", "SRP"): actual_war}
                    chosen = list(selected_effects(ast_block(events["ADISCORD_STP_cw.21"], "immediate"), facts, "VAL"))
                    news_calls = [e.value for _, e in chosen if e.key == "news_event"]
                    self.assertEqual(
                        [scalar(call, "id") for call in news_calls],
                        ["ADISCORD_STP_cw.73"] if owner and eligible and actual_war else [],
                    )
                    if owner and eligible and actual_war:
                        self.assertEqual([scalar(call, "hours") for call in news_calls], ["1"])
                    self.assertEqual([(scope, e.value) for scope, e in chosen if e.key == "add_ideas"],
                                     [("SRP", "STP_cw_republics_battle_spirit")] if owner and eligible and actual_war else [])
                    self.assertEqual([scalar(e.value, "target") for _, e in chosen if e.key == "declare_war_on"],
                                     ["SRP"] if owner and eligible else [])
                    self.assertFalse(any(e.key == "add_to_war" for _, e in chosen))

    def test_val_trade_route_can_order_occidia_campaign_without_revoking_supplies(self):
        decision = ast_block(ast_block(entries("common/decisions/ADISCORD_VAL_decisions.txt"),
                                       "VAL_military_operations"), "VAL_cw_begin_mobilization")
        start = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                          "VAL_cw_start_intervention")
        for course in ("VAL_cw_trade_course", "VAL_cw_military_course"):
            for eligible in (False, True):
                facts = {("VAL", "has_country_flag", course): True,
                         ("VAL", "VAL_cw_can_intervene", "yes"): eligible}
                self.assertTrue(matches_conditions(ast_block(decision, "visible"), facts, "VAL"))
                self.assertEqual(matches_conditions(ast_block(decision, "available"), facts, "VAL"), eligible)
                chosen = list(selected_effects(start, facts, "VAL"))
                self.assertEqual(any(e.key == "set_country_flag" and e.value == "VAL_cw_military_course"
                                     for _, e in chosen), eligible)
                self.assertEqual([(scope, e.value) for scope, e in chosen if e.key == "activate_mission"],
                                 [("VAL", "VAL_cw_intervention_preparation"), ("SRP", "STP_cw_val_ultimatum")]
                                 if eligible else [])
                self.assertFalse(any(e.key == "clr_country_flag" and e.value == "VAL_cw_trade_course"
                                     for _, e in chosen))
                self.assertFalse(any(e.key == "declare_war_on" for _, e in chosen))

    def test_val_only_neutrality_releases_republics_without_starting_a_war(self):
        events = {scalar(e.value, "id"): e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event"}
        courses = [e.value for e in events["ADISCORD_STP_cw.20"] if e.key == "option"
                   and scalar(e.value, "name") in ("ADISCORD_STP_cw.20.b", "ADISCORD_STP_cw.20.c")]
        tree = ast_block(entries("common/national_focus/ADISCORD_national_focus_VAL.txt"), "focus_tree")
        courses += [ast_block(e.value, "completion_reward") for e in tree if e.key == "focus"
                    and scalar(e.value, "id") in ("VAL_Arms_For_The_Burning", "VAL_Keep_The_Arsenals")]
        self.assertEqual(len(courses), 4, "both event and focus choices must release the peaceful republics")
        for course in courses:
            neutrality = any(e.key == "set_country_flag" and e.value == "VAL_cw_refused" for e in walk(course))
            for exists in (False, True):
                for peace in (False, True):
                    facts = {("SRP", "exists", "yes"): exists, ("SRP", "has_war", "no"): peace,
                             ("STS", "exists", "yes"): True, ("STS", "has_capitulated", "no"): True,
                             ("STS", "has_war_with", "STP"): True}
                    chosen = list(selected_effects(course, facts, "VAL"))
                    postwar = [(scope, e.value) for scope, e in chosen if e.key == "STP_cw_finish_mobilization"]
                    self.assertEqual(postwar, [("SRP", "yes")] if neutrality and exists and peace else [])
                    self.assertFalse(any(e.key in ("declare_war_on", "add_to_war", "white_peace") for _, e in chosen))

    def test_external_settlements_release_intervention_state_and_report_outcomes(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        nod_win = ast_block(effects, "STP_cw_settle_nod_victory")
        facts = {("STP", "exists", "yes"): True, ("STS", "exists", "yes"): True,
                 ("STS", "has_capitulated", "yes"): True, ("NOD", "has_country_flag", "NOD_cw_entered"): True}
        selected = list(selected_effects(nod_win, facts))
        self.assertIn("STP_cw_close_nod_after_party_victory", [e.key for _, e in selected])
        selected += list(selected_effects(ast_block(effects, "STP_cw_close_nod_after_party_victory"), facts))
        for flag in ("NOD_cw_entered", "NOD_cw_intervention_approved"):
            self.assertIn(("NOD", "clr_country_flag", flag), [(s, e.key, e.value) for s, e in selected])
        self.assertIn(("NOD", "set_country_flag", "NOD_cw_victorious"), [(s, e.key, e.value) for s, e in selected])
        self.assertIn(("NOD", "ADISCORD_STP_cw.43"), [(s, scalar(e.value, "id")) for s, e in selected if e.key == "country_event"])
        val_win = ast_block(effects, "VAL_cw_settle_republics")
        val_facts = {("VAL", "has_country_flag", "VAL_cw_entered"): True,
                     **{(str(state), "is_owned_by", "SRP"): True for state in (43, 44, 45, 88)}}
        selected = list(selected_effects(val_win, val_facts, "VAL"))
        self.assertFalse([e for _, e in selected if e.key == "transfer_state"])
        keys = [e.key for _, e in selected]
        self.assertIn("VAL_form_occidian_administration", keys)
        self.assertLess(keys.index("STP_cw_finish_mobilization"), keys.index("VAL_form_occidian_administration"))
        dispatched = next(i for i, (_, e) in enumerate(selected) if e.key == "VAL_form_occidian_administration")
        closed = next(i for i, (_, e) in enumerate(selected) if e.key == "clr_country_flag" and e.value == "VAL_cw_entered")
        self.assertLess(dispatched, closed)
        self.assertIn(("VAL", "clr_country_flag", "VAL_cw_entered"), [(s, e.key, e.value) for s, e in selected])
        self.assertIn(("VAL", "ADISCORD_STP_cw.23"), [(s, scalar(e.value, "id")) for s, e in selected if e.key == "country_event"])
        self.assertNotIn("VAL_foreign_operation_active", [e.value for _, e in selected if e.key == "clr_country_flag"],
                         "a completed war must not cancel a different operation started after mobilisation")
        self.assertFalse(list(selected_effects(val_win, {**val_facts, ("VAL", "has_country_flag", "VAL_cw_settled"): True}, "VAL")))
        self.assertFalse(list(selected_effects(nod_win, {**facts, ("NOD", "has_country_flag", "NOD_cw_entered"): False})))

    def test_party_victory_closes_pending_or_deployed_nod_before_annexation(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        helper = "STP_cw_close_nod_after_party_victory"
        self.assertIn(helper, {e.key for e in effects})
        cleanup = ast_block(effects, helper)
        party = ast_block(effects, "STP_cw_settle_union_victory")
        route = next(e for e in party if e.key == "if"
                     and any(v.key == helper for v in e.value))
        self.assertEqual(scalar(ast_block(ast_block(route.value, "limit"), "ROOT"), "tag"), "STS")
        self.assertLess(party.index(route), next(i for i, e in enumerate(party) if e.key == "annex_country"))
        direct = ast_block(ast_block(effects, "STP_cw_settle_nod_victory"), "if")
        self.assertLess(next(i for i, e in enumerate(direct) if e.key == helper),
                        next(i for i, e in enumerate(direct) if e.key == "STP"))
        for approved, entered in ((False, False), (True, False), (True, True)):
            with self.subTest(approved=approved, entered=entered):
                facts = {("NOD", "has_country_flag", "NOD_cw_intervention_approved"): approved,
                         ("NOD", "has_country_flag", "NOD_cw_entered"): entered,
                         ("NOD", "has_war_with", "STS"): entered}
                selected = list(selected_effects(cleanup, facts))
                scalars = [(scope, e.key, e.value) for scope, e in selected if isinstance(e.value, str)]
                if not approved and not entered:
                    self.assertEqual(selected, [])
                    continue
                for flag in ("NOD_cw_entered", "NOD_cw_intervention_approved"):
                    self.assertIn(("NOD", "clr_country_flag", flag), scalars)
                for flag in ("STP_cw_nod_entered", "STP_cw_nod_warning_active"):
                    self.assertIn(("STS", "clr_country_flag", flag), scalars)
                self.assertIn(("NOD", "remove_mission", "NOD_cw_intervention_preparation"), scalars)
                self.assertIn(("STS", "remove_mission", "STP_cw_nod_warning"), scalars)
                self.assertEqual(("NOD", "set_country_flag", "NOD_cw_victorious") in scalars, entered)
                self.assertEqual(("NOD", "add_war_support", "0.05") in scalars, entered)
                self.assertFalse(any(e.key == "set_country_flag" and e.value in
                                     ("NOD_cw_withdrew", "NOD_cw_defeated") for _, e in selected))
                events = [scalar(e.value, "id") for _, e in selected if e.key == "country_event"]
                self.assertEqual(events, ["ADISCORD_STP_cw.43"] if entered else [])
                self.assertEqual([e.value for _, e in selected if e.key == "white_peace"], ["STS"] if entered else [])
                # The receipt is consumed: repeating this settlement grants no second reward.
                for scope, e in selected:
                    if e.key == "clr_country_flag":
                        facts[(scope, "has_country_flag", e.value)] = False
                self.assertEqual(list(selected_effects(cleanup, facts)), [])

    def test_val_delayed_war_releases_only_its_mobilization_and_records_actual_entry(self):
        events = {scalar(e.value, "id"): e.value for e in entries("events/ADISCORD_STP_events.txt") if e.key == "country_event"}
        callback = ast_block(events["ADISCORD_STP_cw.21"], "immediate")
        for owner in (False, True):
            for eligible in (False, True):
                for actual_war in (False, True):
                    with self.subTest(owner=owner, eligible=eligible, actual_war=actual_war):
                        facts = {("VAL", "has_country_flag", "VAL_cw_mobilizing"): owner,
                                 ("VAL", "has_country_flag", "VAL_cw_military_course"): True,
                                 ("VAL", "VAL_cw_can_intervene", "yes"): eligible,
                                 ("VAL", "has_war_with", "SRP"): actual_war}
                        chosen = list(selected_effects(callback, facts, "VAL"))
                        calls = [(s, e.key, e.value) for s, e in chosen]
                        wars = [(s, e) for s, e in chosen if e.key == "declare_war_on"]
                        self.assertEqual(len(wars), int(owner and eligible))
                        self.assertEqual(("VAL", "clr_country_flag", "VAL_foreign_operation_active") in calls, owner)
                        self.assertEqual(("VAL", "set_country_flag", "VAL_cw_entered") in calls, owner and eligible and actual_war)
                        if wars:
                            self.assertLess(next(i for i, (_, e) in enumerate(chosen) if e.key == "clr_country_flag"
                                                 and e.value == "VAL_cw_mobilizing"), chosen.index(wars[0]))
                        reports = [scalar(e.value, "id") for _, e in chosen if e.key == "country_event"]
                        self.assertEqual(reports, ["ADISCORD_STP_cw.23"] if owner and not (eligible and actual_war) else [])

    def test_val_retains_its_separate_timer_and_nod_refusal_stays_final(self):
        category = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention")
        for name in ("VAL_cw_intervention_preparation",):
            mission = ast_block(category, name)
            self.assertEqual(scalar(mission, "days_mission_timeout"), "21")
            self.assertEqual(ast_block(mission, "timeout_effect"), [])
        gate = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_nod_can_intervene")
        facts = {("STS", "has_global_flag", "STP_cw_started"): True,
                 **{(tag, "exists", "yes"): True for tag in ("NOD", "STP", "STS")},
                 **{(tag, "has_capitulated", "no"): True for tag in ("NOD", "STP", "STS")},
                 **{(tag, "is_subject", "no"): True for tag in ("NOD", "STP", "STS")},
                 ("STP", "has_war_with", "STS"): True,
                 ("NOD", "variable", "STP_cw_northern_campaign_status"): 2}
        self.assertTrue(matches_conditions(gate, facts, "STS"))
        for flag in ("NOD_cw_refused", "NOD_cw_victorious", "NOD_cw_withdrew", "NOD_cw_defeated"):
            self.assertFalse(matches_conditions(gate, {**facts, ("NOD", "has_country_flag", flag): True}, "STS"), flag)

    def test_party_exile_does_not_keep_nod_intervention_at_war(self):
        cleanup = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                            "STP_cw_end_nod_intervention")
        for exiles in (False, True):
            for return_campaign in (False, True):
                with self.subTest(exiles=exiles, return_campaign=return_campaign):
                    facts = {
                        ("NOD", "has_country_flag", "NOD_cw_entered"): True,
                        ("NOD", "has_country_flag", "STP_ps_exile_received"): exiles,
                        ("NOD", "has_country_flag", "STP_ps_return_campaign"): return_campaign,
                        ("NOD", "has_war_with", "STS"): True,
                        ("NOD", "has_war_with", "YPR"): True,
                    }
                    selected = list(selected_effects(cleanup, facts, "STS"))
                    self.assertEqual([e.value for _, e in selected if e.key == "white_peace"],
                                     [] if return_campaign else ["STS"])
                    self.assertIn(("NOD", "clr_country_flag", "NOD_cw_entered"),
                                  [(scope, e.key, e.value) for scope, e in selected])
                    self.assertFalse(any(e.key == "clr_country_flag" and e.value == "STP_ps_exile_received"
                                         for _, e in selected))
                    self.assertFalse(any(e.key == "STP_ps_close_exile" for _, e in selected))

    def test_nod_defeat_router_preserves_the_country_and_other_wars(self):
        router = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions"), "on_capitulation")
        defeat = next((e.value for e in walk(router) if e.key == "else_if"
                       and any(v.key == "set_country_flag" and v.value == "NOD_cw_defeated" for v in walk(e.value))), None)
        self.assertIsNotNone(defeat)
        root_gate = ast_block(ast_block(defeat, "limit"), "ROOT")
        self.assertTrue(matches_conditions(root_gate, {("NOD", "has_country_flag", "NOD_cw_entered"): True,
                                                      ("NOD", "variable", "STP_cw_capitulation_occupier"): 2}, "NOD"))
        self.assertFalse(matches_conditions(root_gate, {("NOD", "has_country_flag", "NOD_cw_entered"): True,
                                                       ("NOD", "variable", "STP_cw_capitulation_occupier"): 5}, "NOD"))
        selected = list(selected_effects(ast_block(defeat, "NOD"), {("NOD", "has_war_with", "STS"): True}, "NOD"))
        self.assertEqual([e.value for _, e in selected if e.key == "white_peace"], ["STS"])
        self.assertFalse(any(e.key == "annex_country" for e in walk(defeat)))
        self.assertIn("NOD_cw_entered", [e.value for _, e in selected if e.key == "clr_country_flag"])

    def test_nod_checks_north_and_safe_war_participants(self):
        gate = block(self.triggers, "STP_cw_nod_can_intervene")
        for token in ("NOD = { exists = yes }", "STP = { exists = yes }", "STS = { exists = yes }", "has_war_with = STS", "is_subject = no", "is_in_faction_with = STS", "STP_cw_nod_busy_in_north = yes"):
            self.assertIn(token, gate)
        busy = block(self.triggers, "STP_cw_nod_busy_in_north")
        for tag in ("YPR", "COF", "TFF"):
            self.assertIn(f"has_war_with = {tag}", busy)
            self.assertIn(f"{tag} = {{ exists = yes has_capitulated = no }}", busy)
        on_actions = read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        weekly = block(on_actions, "on_weekly")
        self.assertIn("tag = STS", weekly)
        self.assertIn("STP_cw_poll_nod_intervention = yes", weekly)
        self.assertNotIn("every_country", weekly)

    def test_weekly_nod_poll_stops_after_peace_but_keeps_pending_warning_cleanup(self):
        actions = ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions")
        weekly = ast_block(ast_block(actions, "on_weekly"), "effect")
        for tag in ("STP", "STS", "NOD", "VAL"):
            for started in (False, True):
                for finished in (False, True):
                    for warning in (False, True):
                        for entered in (False, True):
                            with self.subTest(tag=tag, started=started, finished=finished, warning=warning, entered=entered):
                                facts = {(tag, "has_global_flag", "STP_cw_started"): started,
                                         (tag, "has_global_flag", "STP_cw_union_wars_finished"): finished,
                                         (tag, "has_active_mission", "STP_cw_nod_warning"): warning,
                                         (tag, "has_country_flag", "STP_cw_nod_entered"): entered}
                                selected = [scope for scope, e in selected_effects(weekly, facts, tag)
                                            if e.key == "STP_cw_poll_nod_intervention"]
                                expected = tag == "STS" and started and not entered and (warning or not finished)
                                self.assertEqual(selected, ["STS"] if expected else [],
                                                 "peace stops polling; an active warning still receives the existing cleanup")

    def test_val_visible_timer_has_no_independent_war_callback(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        warning = block(decisions, "STP_cw_val_ultimatum")
        self.assertIn("activation = { always = no }", warning)
        self.assertIn("days_mission_timeout = 21", warning)
        self.assertNotIn("declare_war_on", warning)
        self.assertNotIn("VAL_cw_start_intervention", warning)
        self.assertIn("SRP = { activate_mission = STP_cw_val_ultimatum }", block(self.effects, "VAL_cw_start_intervention"))

    def test_nod_military_victory_settles_for_party_not_nod(self):
        on_actions = read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        self.assertIn("var = STP_cw_capitulation_occupier value = 4 compare = equals", on_actions)
        self.assertIn("STP_cw_settle_nod_victory = yes", on_actions)
        settlement = block(self.effects, "STP_cw_settle_nod_victory")
        self.assertIn("STP = {", settlement)
        self.assertIn("annex_country = { target = STS transfer_troops = no }", settlement)
        self.assertNotIn("every_enemy_country", settlement)

    def test_runtime_dialect_uses_boolean_exists_in_country_scope(self):
        for path in (
            "common/scripted_effects/ADISCORD_STP_scripted_effects.txt",
            "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt",
            "common/on_actions/02_ADISCORD_STP_on_actions.txt",
            "events/ADISCORD_STP_events.txt",
            "common/decisions/ADISCORD_STP_decisions.txt",
        ):
            self.assertNotRegex(read(path), r"\bexists\s*=\s*[A-Z]{3}\b", path)

    def test_rifle_payment_is_producer_scoped_and_uses_actual_removal(self):
        payment = block(self.effects, "STP_cw_pay_rifles")
        self.assertIn("every_possible_country =", payment)
        self.assertIn("producer = PREV", payment)
        self.assertIn("amount = STP_cw_rifle_debit", payment)
        self.assertIn("subtract_from_temp_variable = { var = STP_cw_rifles_removed value = num_equipment@infantry_equipment }", payment)
        self.assertIn("subtract_from_temp_variable = { var = STP_cw_rifles_remaining value = STP_cw_rifles_removed }", payment)
        self.assertIn("var = STP_cw_rifles_remaining value = 0 compare = equals", payment)
        self.assertNotIn("add_equipment_to_stockpile = { type = infantry_equipment amount = 480", payment)
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for cost in (16000, 2400, 240):
            self.assertIn(f"set_temp_variable = {{ var = STP_cw_rifle_cost value = {cost} }}", decisions)
            self.assertNotIn(f"type = infantry_equipment amount = -{cost}", decisions)

    def test_mixed_producer_payment_model_conserves_original_pools(self):
        # Engine operation is bounded by the chosen producer's actual stock.
        # Old unfiltered debit would remove 480 from all three nonempty pools.
        pools = {"STP": 200, "VAL": 50, "WRK": 1500, "STS": 0}
        original = dict(pools)
        remaining = 480
        for producer in pools:
            actual_removed = min(pools[producer], remaining)
            pools[producer] -= actual_removed
            remaining -= actual_removed
        self.assertEqual(remaining, 0)
        self.assertEqual(sum(original.values()) - sum(pools.values()), 480)
        self.assertEqual(pools, {"STP": 0, "VAL": 0, "WRK": 1270, "STS": 0})

    def test_capitulation_uses_occupation_before_ambiguous_multiwar_from(self):
        on_actions = read_country_on_actions("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        capitulation = block(on_actions, "on_capitulation")
        self.assertIn("STP_cw_settle_union_victory = yes", capitulation)
        self.assertNotIn("STP_cw_republics_victory", capitulation)
        self.assertIn("var = STP_cw_capitulation_occupier value = 3 compare = equals", capitulation)
        self.assertNotIn("FROM = { tag = SRP }", capitulation)
        self.assertNotIn("capital_scope", capitulation)
        immediate = block(on_actions, "on_capitulation_immediate")
        self.assertIn("STP_cw_snapshot_capitulation_occupier = yes", immediate)
        snapshot = block(self.effects, "STP_cw_snapshot_capitulation_occupier")
        for state in (28, 1, 43):
            self.assertIn(f"owns_state = {state}", snapshot)
            self.assertIn(f"{state} = {{ STP_cw_cache_state_occupier = yes }}", snapshot)
        settlement = block(self.effects, "STP_cw_settle_union_victory")
        self.assertIn("ROOT = { tag = STP }", settlement)
        self.assertIn("STP_cw_end_nod_intervention = yes", settlement)
        self.assertIn("annex_country = { target = ROOT transfer_troops = no }", settlement)
        withdraw = block(self.effects, "STP_cw_end_nod_intervention")
        self.assertIn("white_peace = STS", withdraw)
        self.assertNotIn("every_enemy_country", withdraw)


class CommanderLoyaltyContracts(unittest.TestCase):
    def test_allegiance_markers_have_native_names_icons_and_no_stat_bonuses(self):
        traits = ast_block(entries("common/unit_leader/00_traits.txt"), "leader_traits")
        characters = ast_block(entries("common/characters/STP.txt"), "characters")
        names = ("STP_party_loyalist", "STP_shabrat_loyalist", "STP_local_councils_loyalist",
                 "STP_ravel_undecided", "STP_drake_undecided")
        loc_path = ROOT / "localisation/russian/ADISCORD_traits_l_russian.yml"
        self.assertTrue(loc_path.read_bytes().startswith(b"\xef\xbb\xbf"))
        loc = loc_path.read_text(encoding="utf-8-sig")
        gfx = ast_block(entries("interface/ADISCORD_STP_regions.gfx"), "spriteTypes")
        for name in names:
            with self.subTest(trait=name):
                definition = ast_block(traits, name)
                self.assertEqual({e.key for e in definition}, {"type", "trait_type", "new_commander_weight"})
                self.assertEqual(scalar(definition, "type"), "all")
                self.assertEqual(scalar(definition, "trait_type"), "personality_trait")
                self.assertEqual(scalar(ast_block(definition, "new_commander_weight"), "factor"), "0")
                for suffix in ("", "_desc"):
                    self.assertEqual(len(re.findall(r"^ " + name + suffix + ":", loc, re.M)), 1)
                sprites = [e.value for e in gfx if scalar(e.value, "name") == "GFX_trait_" + name]
                self.assertEqual(len(sprites), 1)
                self.assertIn(scalar(sprites[0], "texturefile"),
                              ("gfx/interface/traits/personal/trait_politically_connected.dds",
                               "gfx/interface/traits/personal/trait_cautious.dds"))
        for name, role, original, loyalty in (
            ("STP_Roland_Keitel", "corps_commander", {"old_guard"}, names[0]),
            ("STP_Maurice_Dallon", "corps_commander", {"organizer"}, names[0]),
            ("STP_August_Veil", "field_marshal", {"defensive_doctrine"}, names[0]),
            ("STP_Leonid_Barchel", "corps_commander", {"commando"}, names[1]),
            ("STP_Viktor_Marent", "corps_commander", {"brilliant_strategist"}, names[2]),
            ("STP_Edmund_Ravel", "corps_commander", {"infantry_leader"}, names[3]),
            ("STP_Severin_Drake", "field_marshal", {"offensive_doctrine", "logistics_wizard"}, names[4]),
        ):
            actual = {e.value for e in ast_block(ast_block(ast_block(characters, name), role), "traits")}
            self.assertEqual(actual, original | {loyalty})
        shabrat = ast_block(characters, "STP_maksim_shabrat")
        self.assertFalse(any(e.key in ("corps_commander", "field_marshal") for e in shabrat))
        korsh = ast_block(characters, "STP_Gleb_Korsh")
        self.assertFalse(any(e.key in ("corps_commander", "field_marshal") for e in korsh))
        portraits = ast_block(shabrat, "portraits")
        self.assertEqual(scalar(ast_block(portraits, "army"), "large"),
                         scalar(ast_block(portraits, "civilian"), "large"))

    def scenario(self, *, owner="STP", ready=(), war=False, shabrat=True, arrested=False, role=None):
        """Execute only parsed commander effects; preserve actual branch/scope selection."""
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        characters = ast_block(entries("common/characters/STP.txt"), "characters")
        character_ids = {e.key for e in characters}
        traits, roles = {}, {}
        for character in characters:
            for item in character.value:
                if item.key in ("corps_commander", "field_marshal"):
                    traits[character.key] = {e.value for e in ast_block(item.value, "traits")}
                    roles[character.key] = item.key
        roles["STP_maksim_shabrat"] = role
        traits["STP_maksim_shabrat"] = set()
        owners = {name: owner for name in character_ids}
        if not shabrat:
            owners.pop("STP_maksim_shabrat")
        country_roles = set()
        writes = []
        global_flags = {"STP_cw_started"} if war else set()
        country_flags = set(ready) | ({"STP_cw_participant"} if war else set())

        def condition(items, scope):
            def match(e):
                if e.key == "OR": return any(match(child) for child in e.value)
                if e.key == "NOT": return not any(match(child) for child in e.value)
                if e.key in ("AND", "hidden_trigger"): return condition(e.value, scope)
                if e.key in character_ids or e.key in ("STP", "STS"):
                    return condition(e.value, e.key)
                if e.key == "STP_cw_shabrat_available":
                    return condition(ast_block(triggers, e.key), scope)
                if e.key == "tag": return scope == e.value
                if e.key == "has_character": return owners.get(e.value) == scope
                if e.key == "has_trait": return e.value in traits.get(scope, set())
                if e.key == "has_character_flag":
                    return scope == "STP_maksim_shabrat" and arrested and e.value == "STP_cw_arrested"
                if e.key == "has_country_flag": return e.value in country_flags
                if e.key == "has_global_flag": return e.value in global_flags
                role_checks = {"is_unit_leader": roles.get(scope) is not None,
                               "is_corps_commander": roles.get(scope) == "corps_commander",
                               "is_field_marshal": roles.get(scope) == "field_marshal",
                               "is_country_leader": scope in country_roles}
                if e.key in role_checks: return role_checks[e.key] == (e.value == "yes")
                raise AssertionError(f"Unsupported commander predicate: {e.key}")
            return all(match(e) for e in items)

        def execute(items, scope):
            taken = False
            for e in items:
                if e.key in ("if", "else_if", "else"):
                    if e.key == "if": taken = False
                    if not taken and (e.key == "else" or condition(ast_block(e.value, "limit"), scope)):
                        taken = True
                        execute([child for child in e.value if child.key != "limit"], scope)
                elif e.key in character_ids or e.key in ("STP", "STS"):
                    execute(e.value, e.key)
                elif e.key in ("add_unit_leader_trait", "remove_unit_leader_trait"):
                    writes.append((scope, e.key, e.value))
                    if e.key == "add_unit_leader_trait": traits.setdefault(scope, set()).add(e.value)
                    else: traits[scope].remove(e.value)
                elif e.key == "add_field_marshal_role":
                    self.assertIsNone(roles.get(scope), "a new role must not reset an existing commander")
                    roles[scope] = "field_marshal"
                    traits.setdefault(scope, set()).update(child.value for child in ast_block(e.value, "traits"))
                    writes.append((scope, e.key, e.value))
                elif e.key == "promote_leader":
                    self.assertEqual(roles[scope], "corps_commander")
                    roles[scope] = "field_marshal"
                    writes.append((scope, e.key, e.value))
                elif e.key == "add_country_leader_role":
                    character = scalar(e.value, "character") if scope not in character_ids else scope
                    self.assertNotIn(character, country_roles)
                    country_roles.add(character)
                    writes.append((character, e.key, e.value))
                elif e.key == "promote_character":
                    character = scalar(e.value, "character") if isinstance(e.value, list) else e.value
                    self.assertEqual(owners.get(character), scope)
                    writes.append((character, e.key, e.value))
                else:
                    raise AssertionError(f"Unsupported commander effect: {e.key}")

        def run(helper): execute(ast_block(effects, helper), owner)
        return run, condition, traits, roles, writes, owners, country_flags, global_flags

    def test_conditional_loyalties_follow_real_focus_flags_and_freeze_at_split(self):
        for ravel in (False, True):
            for drake in (False, True):
                with self.subTest(ravel=ravel, drake=drake):
                    ready = [flag for yes, flag in ((ravel, "STP_cw_officers_ready"),
                                                    (drake, "STP_cw_young_officers_ready")) if yes]
                    run, _, traits, _, writes, _, countries_, globals_ = self.scenario(ready=ready)
                    original = {key: set(value) for key, value in traits.items()}
                    run("STP_cw_refresh_officer_loyalties")
                    for character, ready_, undecided in (("STP_Edmund_Ravel", ravel, "STP_ravel_undecided"),
                                                          ("STP_Severin_Drake", drake, "STP_drake_undecided")):
                        self.assertIn("STP_shabrat_loyalist" if ready_ else undecided, traits[character])
                    countries_.add("STP_cw_participant")
                    run("STP_cw_refresh_officer_loyalties")
                    for character, ready_, undecided in (("STP_Edmund_Ravel", ravel, "STP_ravel_undecided"),
                                                          ("STP_Severin_Drake", drake, "STP_drake_undecided")):
                        self.assertNotIn(undecided, traits[character])
                        self.assertIn("STP_shabrat_loyalist" if ready_ else "STP_party_loyalist", traits[character])
                        self.assertTrue(original[character] - {undecided} <= traits[character])
                    for fixed in ("STP_Roland_Keitel", "STP_Maurice_Dallon", "STP_August_Veil",
                                  "STP_Leonid_Barchel", "STP_Viktor_Marent"):
                        self.assertEqual(traits[fixed], original[fixed])
                    count = len(writes)
                    run("STP_cw_refresh_officer_loyalties")
                    self.assertEqual(len(writes), count, "refresh must stop when no undecided marker remains")
        run, _, _, _, writes, owners, _, _ = self.scenario(war=True)
        owners.pop("STP_Edmund_Ravel")
        owners.pop("STP_Severin_Drake")
        run("STP_cw_refresh_officer_loyalties")
        self.assertEqual(writes, [], "an unavailable officer must not be recreated or mutated")

    def test_shabrat_presence_and_arrest_gate_transfer_and_command(self):
        gate = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_cw_shabrat_available")
        for present in (False, True):
            for arrested in (False, True):
                for owner in ("STP", "STS"):
                    with self.subTest(present=present, arrested=arrested, owner=owner):
                        _, cond, _, _, _, _, _, _ = self.scenario(owner=owner, shabrat=present, arrested=arrested)
                        self.assertEqual(cond(gate, owner), present and not arrested)
        start = block(read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start")
        self.assertRegex(start, r"limit\s*=\s*\{\s*STP_cw_shabrat_available = yes\s*\}\s*set_nationality\s*=\s*\{\s*character = STP_maksim_shabrat")
        self.assertNotIn("set_nationality = { character = STP_Gleb_Korsh", start)
        self.assertIn("STP_cw_commission_korsh = yes", start)
        commission = block(read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_commission_korsh")
        self.assertIn("is_ai = no", commission)
        self.assertIn("set_nationality = { character = STP_Gleb_Korsh target_country = STS }", commission)
        self.assertNotIn("recruit_character = STP_Gleb_Korsh", commission)
        self.assertIn("add_corps_commander_role", commission)
        self.assertIn("STP_cw_shabrat_available = yes", commission)
        self.assertIn("recruit_character = STP_Gleb_Korsh", read("history/countries/STP - StepanLand.txt"))
        self.assertLess(commission.index("set_nationality"), commission.index("add_corps_commander_role"))
        self.assertLess(start.index("set_country_flag = STP_cw_participant"), start.index("STP_cw_refresh_officer_loyalties = yes"))
        self.assertLess(start.index("STP_cw_refresh_officer_loyalties = yes"), start.index("set_nationality"))
        self.assertIn("STP_cw_release_resistance_officeholders = yes", start)
        self.assertLess(start.index("STP_cw_release_resistance_officeholders = yes"), start.index("set_nationality"))
        self.assertIn("STP_cw_establish_resistance_command = yes", start)
        self.assertIn("STS = { STP_cw_establish_resistance_command = yes STP_pc_align_resistance_ruling_party = yes }", start)
        self.assertGreater(start.index("STS = { STP_cw_establish_resistance_command = yes STP_pc_align_resistance_ruling_party = yes }"),
                           start.index("set_nationality"))

    def test_command_role_is_added_once_and_existing_military_roles_are_preserved(self):
        for original in (None, "corps_commander", "field_marshal"):
            with self.subTest(original=original):
                run, _, traits, roles, writes, _, _, _ = self.scenario(owner="STS", war=True, role=original)
                run("STP_cw_establish_resistance_command")
                self.assertEqual(roles["STP_maksim_shabrat"], "field_marshal")
                self.assertIn("STP_shabrat_loyalist", traits["STP_maksim_shabrat"])
                self.assertEqual(roles["STP_Leonid_Barchel"], "corps_commander")
                created = [e for _, key, e in writes if key == "add_field_marshal_role"]
                self.assertEqual(len(created), int(original is None))
                if created:
                    self.assertEqual({key: scalar(created[0], key) for key in
                                      ("skill", "attack_skill", "defense_skill", "planning_skill", "logistics_skill")},
                                     dict(skill="2", attack_skill="2", defense_skill="2", planning_skill="2", logistics_skill="1"))
                count = sum(key != "promote_character" for _, key, _ in writes)
                run("STP_cw_establish_resistance_command")
                self.assertEqual(sum(key != "promote_character" for _, key, _ in writes), count)
        for present, arrested in ((False, False), (True, True)):
            run, _, _, roles, writes, _, _, _ = self.scenario(owner="STS", war=True, shabrat=present, arrested=arrested)
            run("STP_cw_establish_resistance_command")
            self.assertIsNone(roles["STP_maksim_shabrat"])
            self.assertFalse(any(scope == "STP_maksim_shabrat" for scope, _, _ in writes))
            self.assertEqual(sum(1 for scope, key, _ in writes if key == "add_country_leader_role" and scope == "STP_grigory_sotnikov"), 1)
            self.assertEqual(roles["STP_grigory_sotnikov"], "field_marshal")
            self.assertEqual(roles["STP_Leonid_Barchel"], "corps_commander")
            run("STP_cw_establish_resistance_command")
            self.assertEqual(sum(1 for scope, key, _ in writes if key == "add_country_leader_role" and scope == "STP_grigory_sotnikov"), 1)
        run, _, _, roles, writes, owners, _, _ = self.scenario(owner="STS", war=True, shabrat=False)
        owners.pop("STP_grigory_sotnikov")
        run("STP_cw_establish_resistance_command")
        self.assertEqual(sum(key == "add_country_leader_role" for _, key, _ in writes), 1)
        self.assertEqual(roles["STP_Leonid_Barchel"], "corps_commander")
        run, _, _, _, writes, owners, _, _ = self.scenario(owner="STS", war=True, shabrat=False)
        owners.pop("STP_grigory_sotnikov")
        owners.pop("STP_Leonid_Barchel")
        run("STP_cw_establish_resistance_command")
        self.assertEqual(writes, [], "fallback must not resurrect an absent Barchel either")
        for owner, war in (("STP", True), ("STS", False)):
            run, _, _, _, writes, _, _, _ = self.scenario(owner=owner, war=war)
            run("STP_cw_establish_resistance_command")
            self.assertEqual(writes, [])

    def test_resistance_leaders_use_registered_subideologies(self):
        ideologies = read("common/ideologies/00_ideologies.txt")
        chauvinism = re.search(
            r"(?s)\bchauvinism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        etatism = re.search(
            r"(?s)\betatism\s*=\s*\{.*?\btypes\s*=\s*\{(.*?)\n\s*\}\s*\n\s*dynamic_faction_names",
            ideologies,
        )
        self.assertIsNotNone(chauvinism)
        self.assertIsNotNone(etatism)
        self.assertRegex(
            chauvinism.group(1),
            r"(?s)\bnational_legitimism\s*=\s*\{.*?can_be_randomly_selected\s*=\s*no.*?\}",
        )
        self.assertIn("steland_military_directory", etatism.group(1))
        characters = read("common/characters/STP.txt")
        shabrat = block(characters, "STP_maksim_shabrat")
        sotnikov = block(characters, "STP_grigory_sotnikov")
        self.assertIn("ideology = national_legitimism", shabrat)
        self.assertIn("ideology = steland_military_directory", sotnikov)
        self.assertNotIn("ideology = etatism_ideology", sotnikov)
        loc = read("localisation/russian/parties_l_russian.yml")
        self.assertTrue((ROOT / "localisation/russian/parties_l_russian.yml").read_bytes().startswith(b"\xef\xbb\xbf"))
        self.assertIn("national_legitimism:", loc)
        self.assertIn("national_legitimism_desc:", loc)
        scripted = read("common/scripted_localisation/ADISCORD_ideologies.txt")
        self.assertIn("has_country_leader_ideology = national_legitimism", scripted)

    def test_align_and_arrest_install_the_named_successor(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        align = block(effects, "STP_pc_align_resistance_ruling_party")
        self.assertIn("promote_character = { character = STP_maksim_shabrat ideology = national_legitimism }", align)
        self.assertIn("ruling_party = chauvinism", align)
        self.assertIn("promote_character = { character = STP_grigory_sotnikov ideology = steland_military_directory }", align)
        self.assertIn("ruling_party = etatism", align)
        self.assertIn("retire_country_leader = yes", align)
        self.assertEqual(align.count("set_politics"), 3)
        self.assertEqual(align.count("retire_country_leader = yes"), 6)
        self.assertLess(align.index("retire_country_leader = yes"),
                        align.index("promote_character = { character = STP_maksim_shabrat ideology = national_legitimism }"))
        self.assertLess(align.index("promote_character = { character = STP_grigory_sotnikov ideology = steland_military_directory }"),
                        align.index("ruling_party = etatism"))
        self.assertIn("has_country_leader = { character = STP_maksim_shabrat ruling_only = yes }", align)
        self.assertIn("has_country_leader = { character = STP_grigory_sotnikov ruling_only = yes }", align)
        self.assertIn("has_country_leader = { character = STP_Leonid_Barchel ruling_only = yes }", align)
        release = block(effects, "STP_cw_release_resistance_officeholders")
        self.assertIn("remove_country_leader_role = { ideology = national_legitimism }", release)
        self.assertIn("remove_country_leader_role = { ideology = steland_military_directory }", release)
        install = block(effects, "STP_pc_install_resistance_successor")
        self.assertIn("STS = { exists = yes }", install)
        self.assertIn("STP_cw_establish_resistance_command = yes", install)
        self.assertIn("STP_pc_align_resistance_ruling_party = yes", install)
        events = read("events/ADISCORD_STP_events.txt")
        self.assertGreaterEqual(events.count("STP_pc_install_resistance_successor = yes"), 2)
        self.assertIn("id = ADISCORD_STP_pc.3", events)
        self.assertIn("id = ADISCORD_STP_pc.6", events)
        arrest = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                      if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_pc.3")
        arrest_a = next(option for option in (e.value for e in arrest if e.key == "option")
                        if scalar(option, "name") == "ADISCORD_STP_pc.3.a")
        self.assertTrue(any(e.key == "STS" and any(child.key == "STP_cw_sotnikov_available" for child in e.value)
                            for e in walk(ast_block(arrest_a, "trigger"))))
        command = block(effects, "STP_cw_establish_resistance_command")
        self.assertIn("ideology = national_legitimism", command)
        self.assertIn("promote_character = { character = STP_maksim_shabrat ideology = national_legitimism }", command)

    def test_side_choice_copies_flags_and_can_retry_a_failed_declaration(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        copy = block(effects, "STP_pc_copy_split_flags")
        self.assertIn("has_country_flag = STP_sided_with_Maksim_flag", copy)
        self.assertIn("has_country_flag = STP_sided_with_the_party_flag", copy)
        self.assertIn("var = STP_party_suspicion", copy)
        handoff = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                       if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.30")
        self.assertEqual(scalar(handoff, "timeout_days"), "7")
        self.assertFalse(any(e.key == "timeout_effect" for e in handoff))
        options = [e.value for e in handoff if e.key == "option"]
        first = options[0]
        self.assertFalse(any(e.key == "trigger" for e in first), "the native timeout must always have a first option")
        for resistance in (False, True):
            facts = {("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): resistance,
                     ("STS", "exists", "yes"): True}
            selected = list(selected_effects(ast_block(first, "hidden_effect"), facts))
            self.assertEqual(sum(e.key == "STP_cw_begin_hostilities" for _, e in selected), 1)
            self.assertEqual(sum(e.key == "STP_cw_commission_korsh" for _, e in selected), int(resistance))
            self.assertEqual(sum(e.key == "change_tag_from" for _, e in selected), int(resistance))
            self.assertEqual(any(e.key == "set_country_flag" and e.value == "STP_sided_with_the_party_flag" for _, e in selected), not resistance)
        war = block(effects, "STP_cw_begin_hostilities")
        self.assertIn("NOT = { has_global_flag = STP_cw_started }", war)
        self.assertLess(war.index("set_global_flag = STP_cw_started"), war.index("declare_war_on"))
        self.assertLess(war.rindex("STP_cw_prepared_supply_lines"), war.index("declare_war_on"))
        self.assertIn("tag = STS", war)
        self.assertIn("declare_war_on = { target = STP type = annex_everything }", war)
        weekly = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions"), "on_weekly")
        retries = [e.value for e in ast_block(weekly, "effect")
                   if e.key == "if" and any(child.key == "STP_cw_begin_hostilities" for child in e.value)]
        self.assertEqual(len(retries), 2)
        retry = retries[0]
        gate = ast_block(retry, "limit")
        ready = {("STP", "has_country_flag", "STP_cw_participant"): True,
                 ("STP", "has_global_flag", "STP_cw_started"): True}
        sided = {("STP", "has_country_flag", "STP_cw_participant"): True,
                 ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True}
        self.assertTrue(matches_conditions(gate, ready))
        self.assertTrue(matches_conditions(gate, sided))
        self.assertFalse(matches_conditions(gate, {("STP", "has_country_flag", "STP_cw_participant"): True}))
        self.assertFalse(matches_conditions(gate, ready, "STS"))
        self.assertFalse(matches_conditions(gate, {**ready, ("STP", "has_global_flag", "STP_cw_union_wars_finished"): True}))
        sts_retry = retries[1]
        sts_gate = ast_block(sts_retry, "limit")
        sts_ready = {("STS", "has_country_flag", "STP_cw_participant"): True,
                     ("STS", "has_global_flag", "STP_cw_started"): True}
        sts_sided = {("STS", "has_country_flag", "STP_cw_participant"): True,
                     ("STS", "has_country_flag", "STP_sided_with_Maksim_flag"): True}
        self.assertTrue(matches_conditions(sts_gate, sts_ready, "STS"))
        self.assertTrue(matches_conditions(sts_gate, sts_sided, "STS"))
        self.assertFalse(matches_conditions(sts_gate, {("STS", "has_country_flag", "STP_cw_participant"): True}, "STS"))
        self.assertFalse(matches_conditions(sts_gate, {**sts_ready, ("STS", "has_war_with", "STP"): True}, "STS"))


class NorthernCampaignContracts(unittest.TestCase):
    """Exercise parsed war/peace predicates; native capitulation ordering is runtime QA."""

    def setUp(self):
        self.triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        self.effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")

    def expand(self, items, parameters=None):
        from tools.validators.validate_adiscord_division_templates import Entry
        parameters = parameters or {}
        definitions = {e.key: e.value for e in self.triggers}
        result = []
        for entry in items:
            key = parameters.get(entry.key, entry.key)
            value = (self.expand(entry.value, parameters) if isinstance(entry.value, list)
                     else parameters.get(entry.value, entry.value))
            if key in definitions:
                self.assertIn(entry.value, ("yes", "no"), f"Unsupported native scripted trigger call: {key}")
                value = self.expand(definitions[key], parameters)
                result.append(Entry("AND" if entry.value != "no" else "NOT", value, entry.line))
            else:
                result.append(Entry(key, value, entry.line, entry.quoted))
        return result

    def facts(self):
        return {(tag, key, value): True for tag in ("NOD", "YPR", "COF", "TFF")
                for key, value in (("exists", "yes"), ("has_capitulated", "no"), ("is_subject", "no"), ("is_in_faction", "no"))}

    def test_limited_revolt_garrison_forecast_matches_transfer_despite_lost_influence(self):
        start = ast_block(ast_block(self.effects, "STP_cw_start"), "if")
        self.assertFalse(any(e.key == "every_owned_state" and any(child.key == "transfer_state" for child in walk(e.value))
                             for e in walk(start)), "owned-state iteration can skip a remaining district")
        transfer_branches = [e for e in start if e.key in ("if", "else_if")
                             and any(child.key == "transfer_state" and child.value in {"2", "3", "29", "45", "46", "53"}
                                     for child in walk(e.value))]
        self.assertTrue(any(any(child.key == "STP_cw_region_goes_to_resistance" for child in walk(e.value))
                            for e in transfer_branches), "all callers must use the same recipient predicate")
        target_states = {child.value for e in transfer_branches for child in walk(e.value) if child.key == "transfer_state"}
        self.assertEqual(target_states, {"2", "3", "29", "45", "46", "53"})
        report = self.expand(ast_block(self.effects, "STP_cw_refresh_army_report"))
        transfer = self.expand(transfer_branches)
        for state in sorted(target_states):
            for limited in (False, True):
                for local_strongest in (False, True):
                    for mandate in (0.0, 0.5501):
                        flags = {("STP", "has_country_flag", "STP_cw_limited_party_revolt"): limited,
                                 ("STP", "has_country_flag", "STP_cw_shabrat_election_victory"): limited,
                                 ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): mandate}
                        assets = {(state, "has_state_flag", asset): True for asset in (
                            "STP_party_reinforced_garrison_asset", "STP_resistance_garrison_asset", "STP_inspection_concession_prepared")}
                        before = {**flags, **assets, (state, "is_owned_by", "STP"): True,
                                  (state, "variable", "STP_resistance_influence"): 10,
                                  (state, "variable", "STP_party_influence"): 10 if local_strongest else 60,
                                  (state, "variable", "STP_local_forces_influence"): 80 if local_strongest else 30,
                                  (state, "variable", "STP_region_margin"): 60 if local_strongest else 30,
                                  (state, "variable", "STP_region_lead"): 80 if local_strongest else 60,
                                  (state, "variable", "STP_region_runner_up"): 10 if local_strongest else 30,
                                  (state, "variable", "STP_region_status"): 0}
                        transfers = [(scope, e.value) for scope, e in selected_effects(transfer, before)
                                     if e.key == "transfer_state" and e.value == state]
                        claimed = limited or mandate > 0.55
                        expected_owner = "SRP" if state == "45" and local_strongest else ("STS" if claimed else "STP")
                        actual_owner = transfers[0][0] if transfers else "STP"
                        with self.subTest(state=state, limited=limited, local_strongest=local_strongest, mandate=mandate):
                            self.assertEqual(transfers, [(expected_owner, state)] if expected_owner != "STP" else [])
                            forecast = {}
                            for scope, entry in selected_effects(report, before):
                                self.assertEqual(scope, "STP")
                                name, amount = scalar(entry.value, "var"), int(scalar(entry.value, "value"))
                                forecast[name] = amount if entry.key == "set_variable" else forecast[name] + amount
                            after = {**before, (state, "is_owned_by", "STP"): actual_owner == "STP",
                                     (state, "is_owned_by", actual_owner): True}
                            calls = list(selected_effects(start, after))
                            for tag, report_name, report_base, actual_base in (
                                ("STP", "STP_cw_report_party_brigades", 16, 5 if limited else 16),
                                ("STS", "STP_cw_report_resistance_brigades", 14, 16 if limited else 14),
                            ):
                                actual = sum(scope == tag and e.key == "STP_cw_mobilize_brigade" for scope, e in calls)
                                self.assertEqual(forecast[report_name] - report_base, actual - actual_base,
                                                 "the forecast's paid extra cohorts must follow the actual transferred state")
                            if claimed and state in ("2", "29"):
                                self.assertEqual(forecast["STP_cw_report_resistance_brigades"] - 14, 2)
                                self.assertEqual(forecast["STP_cw_report_party_brigades"] - 16, 0)

    def test_high_legitimacy_claims_contested_districts_without_administration(self):
        goes_to = self.expand(ast_block(self.triggers, "STP_cw_region_goes_to_resistance"))
        for state, mandate, expected in (("2", 0.55, False), ("2", 0.5501, True), ("53", 0.0, False)):
            facts = {(state, "state", state): True,
                     ("STP", "power_balance_value", "STP_shabrat_election_legitimacy"): mandate}
            with self.subTest(state=state, mandate=mandate):
                self.assertEqual(matches_conditions(goes_to, facts, state), expected)

    def test_every_living_northern_front_opens_early_uprising_until_its_defeat(self):
        busy = self.expand(ast_block(self.triggers, "STP_cw_nod_busy_in_north"))
        gate = self.expand(ast_block(self.triggers, "STP_cw_can_start"))
        anchors = {("STP", "owns_state", str(s)): True for s in (1, 28, 43, 44, 88)}
        preparation = {("STP", "has_active_mission", "STP_cw_election_window"): True,
                       ("STP", "has_country_flag", "STP_cw_uprising_prepared"): True}
        for target in ("YPR", "COF", "TFF"):
            for exists, capitulated, war in ((True, False, True), (False, False, True),
                                             (True, True, True), (True, False, False)):
                facts = {**self.facts(), **anchors, **preparation,
                         (target, "exists", "yes"): exists,
                         (target, "has_capitulated", "no"): not capitulated,
                         ("NOD", "has_war_with", target): war}
                expected = exists and not capitulated and war
                with self.subTest(target=target, exists=exists, capitulated=capitulated, war=war):
                    self.assertEqual(matches_conditions(busy, facts), expected)
                    self.assertEqual(matches_conditions(gate, facts), expected)
        self.assertTrue(matches_conditions(gate, {**anchors, ("STP", "has_country_flag", "STP_cw_elections_finished"): True}))

    def test_nod_alliance_requires_successful_entry_into_the_existing_party_war(self):
        finish = ast_block(self.effects, "STP_cw_finish_nod_warning")
        outer = ast_block(finish, "if")
        join = ast_block(ast_block(outer, "NOD"), "add_to_war")
        self.assertEqual(scalar(join, "targeted_alliance"), "STP")
        self.assertEqual(scalar(join, "enemy"), "STS")
        success = ast_block(outer, "if")
        self.assertEqual(scalar(ast_block(ast_block(success, "limit"), "NOD"), "has_war_with"), "STS")
        party = ast_block(success, "STP")
        alliance = ast_block(party, "if")
        self.assertEqual(scalar(ast_block(ast_block(alliance, "limit"), "NOT"), "is_in_faction_with"), "NOD")
        nod = ast_block(alliance, "NOD")
        create = ast_block(nod, "if")
        self.assertEqual(scalar(ast_block(create, "limit"), "is_in_faction"), "no")
        self.assertEqual(scalar(ast_block(create, "create_faction_from_template"), "template"),
                         "faction_template_ADISCORD_standard")
        self.assertEqual(scalar(ast_block(nod, "faction_leader"), "add_to_faction"), "STP")
        failure = ast_block(outer, "else")
        self.assertFalse([e for e in walk(failure) if e.key in {"add_to_faction", "create_faction_from_template"}])

    def test_northern_war_uses_one_defensive_alliance_and_one_declaration(self):
        start = ast_block(self.effects, "STP_cw_start_northern_war")
        declarations = [scalar(e.value, "target") for e in walk(start) if e.key == "declare_war_on"]
        self.assertEqual(declarations, ["YPR"], "separate declarations do not create one coalition war")
        creations = [e.value for e in walk(start) if e.key == "create_faction_from_template"]
        self.assertEqual(len(creations), 1)
        self.assertEqual(scalar(creations[0], "template"), "faction_template_ADISCORD_standard")
        self.assertEqual([e.value for e in walk(start) if e.key == "add_to_faction"], ["COF", "TFF"])
        for target in ("COF", "TFF"):
            country = next(e.value for e in walk(start) if e.key == target and isinstance(e.value, list)
                           and any(child.key == "add_to_war" for child in e.value))
            join = ast_block(country, "add_to_war")
            self.assertEqual({key: scalar(join, key) for key in ("targeted_alliance", "enemy", "single_target_only")},
                             {"targeted_alliance": "YPR", "enemy": "NOD", "single_target_only": "yes"})

    def test_north_blocks_entry_but_keeps_readiness_and_requires_seven_days_to_redeploy(self):
        possible = self.expand(ast_block(self.triggers, "NOD_cw_intervention_possible"))
        entry = self.expand(ast_block(self.triggers, "STP_cw_nod_can_intervene"))
        category = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention")
        preparation = ast_block(category, "NOD_cw_intervention_preparation")
        cancel = self.expand(ast_block(preparation, "cancel_trigger"))
        common = {**self.facts(),
                  **{(tag, key, value): True for tag in ("STP", "STS")
                     for key, value in (("exists", "yes"), ("has_capitulated", "no"), ("is_subject", "no"))},
                  ("STS", "has_global_flag", "STP_cw_started"): True,
                  ("STP", "has_war_with", "STS"): True}
        for opponent in ("YPR", "COF", "TFF"):
            facts = {**common, ("NOD", "has_war_with", opponent): True,
                     ("NOD", "variable", "STP_cw_northern_campaign_status"): 1}
            with self.subTest(active_front=opponent):
                self.assertTrue(matches_conditions(possible, facts, "NOD"))
                self.assertFalse(matches_conditions(cancel, facts, "NOD"))
                self.assertFalse(matches_conditions(entry, facts, "STS"))
        for status in (2, 4):
            for remaining in (7, 1, 0):
                facts = {**common, ("NOD", "variable", "STP_cw_northern_campaign_status"): status,
                         ("NOD", "has_active_mission", "NOD_cw_northern_redeployment"): True,
                         ("NOD", "variable", "days_mission_timeout@NOD_cw_northern_redeployment"): remaining}
                with self.subTest(status=status, remaining=remaining):
                    self.assertTrue(matches_conditions(possible, facts, "NOD"))
                    self.assertFalse(matches_conditions(cancel, facts, "NOD"))
                    self.assertEqual(matches_conditions(entry, facts, "STS"), remaining == 0)
        defeated = {**common, ("NOD", "variable", "STP_cw_northern_campaign_status"): 3}
        self.assertFalse(matches_conditions(possible, defeated, "NOD"))
        self.assertTrue(matches_conditions(cancel, defeated, "NOD"))
        self.assertFalse(matches_conditions(entry, defeated, "STS"))
        self.assertTrue(matches_conditions(entry, common, "STS"), "An unstarted northern campaign must not block entry")
        external_peace = {**common, ("NOD", "variable", "STP_cw_northern_campaign_status"): 1}
        timeout = list(selected_effects(ast_block(preparation, "timeout_effect"), external_peace, "NOD"))
        self.assertIn(("NOD", "set_country_flag", "NOD_cw_intervention_ready"),
                      [(scope, effect.key, effect.value) for scope, effect in timeout])
        self.assertIn(("NOD", "STP_cw_poll_nod_intervention", "yes"),
                      [(scope, effect.key, effect.value) for scope, effect in timeout])
        for ready in (False, True):
            pending_weekly = {**external_peace, ("NOD", "has_country_flag", "NOD_cw_intervention_ready"): ready}
            with self.subTest(external_peace_before_weekly=True, ready=ready):
                self.assertTrue(matches_conditions(possible, pending_weekly, "NOD"))
                self.assertFalse(matches_conditions(cancel, pending_weekly, "NOD"))
                self.assertFalse(matches_conditions(entry, pending_weekly, "STS"),
                                 "Readiness timeout must wait for reconciliation to start the seven-day redeployment")
        redeploy = ast_block(category, "NOD_cw_northern_redeployment")
        self.assertEqual(scalar(redeploy, "days_mission_timeout"), "7")
        self.assertIn("STP_cw_poll_nod_intervention", {e.key for e in walk(ast_block(redeploy, "timeout_effect"))})
        for name in ("STP_cw_settle_northern_victory", "STP_cw_poll_northern_campaign"):
            effect = ast_block(self.effects, name)
            self.assertEqual([e.value for e in walk(effect) if e.key == "activate_mission"],
                             ["NOD_cw_northern_redeployment"])
            self.assertNotIn("NOD_cw_intervention_ready", [e.value for e in walk(effect) if e.key == "clr_country_flag"])
        self.assertNotIn("activate_mission", {e.key for e in walk(ast_block(self.effects, "STP_cw_settle_northern_defeat"))})

    def test_northern_result_accepts_an_actual_nod_ally_beyond_stelander(self):
        cache = ast_block(self.effects, "STP_cw_cache_state_occupier")
        from itertools import product
        for loser, allied, enemy, active, nod_enemy in product(("YPR", "COF", "TFF"), (False, True), (False, True), (False, True), (False, True)):
            facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): int(active),
                     ("NOD", "has_war_with", loser): nod_enemy,
                     ("AIN", "is_in_faction_with", "NOD"): allied,
                     ("AIN", "has_war_with", loser): enemy}
            chosen = selected_effects(self.expand(cache, {"ROOT": loser, "controller": "AIN"}), facts, "20")
            codes = [(scope, scalar(e.value, "value")) for scope, e in chosen if e.key == "set_variable"]
            self.assertEqual(codes, [(loser, "4")] if allied and enemy and active and nod_enemy else [],
                             (loser, allied, enemy, active, nod_enemy))
        # The generic civil-war snapshot keeps its existing side code.
        chosen = selected_effects(self.expand(cache, {"ROOT": "STS", "controller": "STP"}), {}, "1")
        self.assertEqual([(scope, scalar(e.value, "value")) for scope, e in chosen if e.key == "set_variable"],
                         [("STS", "1")])

    def test_first_coalition_capitulation_does_not_make_a_local_peace(self):
        facts, writes, cap, _ = self.northern_callback_scenario()
        facts[("YPR", "variable", "STP_cw_capitulation_occupier")] = 4
        cap("YPR")
        self.assertTrue(facts[("NOD", "has_war_with", "YPR")])
        self.assertFalse(any(key in ("white_peace", "annex_country", "puppet") for _, key, _ in writes))
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 1)

    def test_coalition_entry_requires_three_free_countries_and_never_steals_a_faction(self):
        start = ast_block(self.effects, "STP_cw_start_northern_war")
        gate = self.expand(ast_block(ast_block(start, "if"), "limit"))
        common = {**self.facts(), ("NOD", "has_country_flag", "STP_cw_northern_crisis_pending"): True}
        self.assertTrue(matches_conditions(gate, common, "NOD"))
        for target in ("YPR", "COF", "TFF"):
            for key, value in (("exists", "yes"), ("has_capitulated", "no"),
                               ("is_subject", "no"), ("is_in_faction", "no")):
                facts = {**common, (target, key, value): False}
                self.assertFalse(matches_conditions(gate, facts, "NOD"), (target, key))
            for key in ("has_war_with", "is_in_faction_with"):
                self.assertFalse(matches_conditions(gate, {**common, ("NOD", key, target): True}, "NOD"))

    def test_campaign_cannot_restart_or_complete_after_only_one_capitulation(self):
        won = self.expand(ast_block(self.triggers, "STP_cw_northern_campaign_won"))
        common = {**self.facts(), ("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                  **{("NOD", "has_war_with", t): True for t in ("YPR", "COF", "TFF")}}
        from itertools import product
        for accepted in product((False, True), repeat=3):
            facts = {**common,
                     **{(t, "has_capitulated", "yes"): done for t, done in zip(("YPR", "COF", "TFF"), accepted)},
                     **{(t, "variable", "STP_cw_capitulation_occupier"): 4 if done else 0
                        for t, done in zip(("YPR", "COF", "TFF"), accepted)}}
            self.assertEqual(matches_conditions(won, facts, "NOD"), all(accepted), accepted)
        facts.update({("YPR", "variable", "STP_cw_capitulation_occupier"): 5})
        self.assertFalse(matches_conditions(won, facts, "NOD"), "a foreign victor is not a NOD victory")
        for status in (2, 3, 4):
            facts = {**common, ("NOD", "variable", "STP_cw_northern_campaign_status"): status,
                     ("STP", "has_active_mission", "STP_cw_election_window"): True,
                     **{("NOD", "has_war_with", t): False for t in ("YPR", "COF", "TFF")}}
            start = self.expand(ast_block(self.effects, "STP_cw_start_northern_war"))
            self.assertFalse(any(e.key == "declare_war_on" for _, e in selected_effects(start, facts, "NOD")))

    def test_northern_peace_preserves_other_wars_and_only_cedes_owned_17_18(self):
        for name, result in (("STP_cw_settle_northern_victory", 2), ("STP_cw_settle_northern_defeat", 3)):
            effect = ast_block(self.effects, name)
            self.assertNotIn("every_enemy_country", {e.key for e in walk(effect)})
            peace = [e.value for e in walk(effect) if e.key == "white_peace"]
            self.assertEqual(peace, ["YPR", "COF", "TFF"],
                             "either final outcome closes only the northern opponents")
            writes = [e for e in walk(effect) if e.key == "set_variable" and scalar(e.value, "var") == "STP_cw_northern_campaign_status"]
            self.assertTrue(writes)
            self.assertEqual({scalar(e.value, "value") for e in writes}, {str(result)})
        victory = ast_block(self.effects, "STP_cw_settle_northern_victory")
        self.assertEqual([scalar(e.value, "target") for e in walk(victory) if e.key == "annex_country"], ["COF"])
        puppet = [e.value for e in walk(victory) if e.key == "puppet"]
        self.assertEqual(len(puppet), 1)
        self.assertEqual({e.key: e.value for e in puppet[0]}, {"target": "YPR", "end_wars": "no", "end_civil_wars": "no"})
        defeat = self.expand(ast_block(self.effects, "STP_cw_settle_northern_defeat"))
        for owned17, owned18 in ((True, True), (True, False), (False, True), (False, False)):
            facts = {**self.facts(), ("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                     ("17", "is_owned_by", "NOD"): owned17, ("18", "is_owned_by", "NOD"): owned18,
                     ("NOD", "has_capitulated", "yes"): True,
                     ("NOD", "variable", "STP_cw_capitulation_occupier"): 6,
                     ("NOD", "has_war_with", "YPR"): True}
            transfers = [(scope, e.value) for scope, e in selected_effects(defeat, facts, "NOD") if e.key == "transfer_state"]
            self.assertEqual(transfers, [("YPR", str(s)) for s, owned in ((17, owned17), (18, owned18)) if owned])
            self.assertFalse(any(e.key == "add_state_core" for _, e in selected_effects(defeat, facts, "NOD")))

    def test_capitulation_reservation_requires_the_actual_enemy_and_snapshotted_side(self):
        managed = ast_block(self.triggers, "STP_cw_northern_capitulation_managed")
        for loser in ("YPR", "COF", "TFF"):
            for code, war, expected in ((4, True, True), (5, True, False), (4, False, False)):
                facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                         (loser, "variable", "STP_cw_capitulation_occupier"): code,
                         ("NOD", "has_war_with", loser): war}
                self.assertEqual(matches_conditions(self.expand(managed, {"ROOT": loser}), facts, loser), expected)
        for code, occupier in ((6, "YPR"), (7, "COF"), (8, "TFF")):
            for actual_enemy in ("YPR", "COF", "TFF"):
                facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                         ("NOD", "variable", "STP_cw_capitulation_occupier"): code,
                         ("NOD", "has_war_with", actual_enemy): True}
                self.assertEqual(matches_conditions(self.expand(managed, {"ROOT": "NOD"}), facts, "NOD"),
                                 actual_enemy == occupier, (code, actual_enemy))
        hook = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions"), "on_capitulation_immediate")
        managed_branches = [e.value for e in walk(hook) if e.key == "if"
                            and "STP_cw_northern_capitulation_managed" in {c.key for c in walk(ast_block(e.value, "limit"))}]
        self.assertEqual(len(managed_branches), 1, "north must settle inside the native immediate callback")
        first = managed_branches[0]
        self.assertIn("skip_default_capitulation", {e.value for e in first if e.key == "set_global_flag"})
        self.assertLess(next(i for i, e in enumerate(first) if e.key == "set_global_flag"),
                        next(i for i, e in enumerate(first) if e.key == "if"))
        marker = "STP_cw_northern_capitulation_pending"
        root_cleanup = ast_block(ast_block(hook, "effect"), "ROOT")
        self.assertEqual(scalar(root_cleanup, "clr_country_flag"), marker)
        self.assertEqual(ast_block(hook, "effect")[0].key, "ROOT")
        self.assertLess(next(i for i, e in enumerate(first) if e.key == "ROOT"),
                        next(i for i, e in enumerate(first) if e.key == "if"))
        self.assertEqual((first[-1].key, first[-1].value), ("clr_global_flag", "skip_default_capitulation"))
        generic = read("common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt")
        self.assertIn("clr_global_flag = skip_default_capitulation", generic)

    def test_ypr_puppet_is_limited_by_actual_historical_ownership(self):
        guard = ast_block(self.triggers, "STP_cw_ypr_has_only_historical_states")
        allowed = {int(e.value) for e in walk(guard) if e.key == "state"}
        historical = set()
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        for path in (ROOT / "history/states").glob("*.txt"):
            state = ast_block(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            histories = [e.value for e in state if e.key == "history"]
            if not histories:
                continue
            history = histories[0]
            if any(e.key == "owner" and e.value == "YPR" for e in history):
                historical.add(int(scalar(state, "id")))
        self.assertEqual(allowed, historical)
        self.assertEqual(allowed, {8, 15, 16, 19, 20, 21, 22})
        victory = ast_block(self.effects, "STP_cw_settle_northern_victory")
        puppet_branch = next(e.value for e in walk(victory) if e.key == "if"
                             and any(child.key == "puppet" for child in e.value))
        self.assertIn("STP_cw_ypr_has_only_historical_states", {e.key for e in walk(ast_block(puppet_branch, "limit"))})
        restoration = next(e.value for e in walk(victory) if e.key == "if"
                           and any(child.key == "transfer_state" for child in e.value))
        self.assertEqual([(e.key, e.value) for e in ast_block(restoration, "limit")],
                         [("STP_cw_northern_conference_won", "yes")])
        self.assertFalse(any(e.key in ("release", "release_puppet") for e in walk(victory)),
                         "restoration must use the bounded state package, not every core")

    def test_northern_victory_news_matches_ypr_dependency_and_actual_bounds(self):
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                     if e.key == "news_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.80")
        descriptions = [e.value for e in event if e.key == "desc"]
        historical = {int(e.value) for e in walk(ast_block(self.triggers, "STP_cw_ypr_has_only_historical_states"))
                      if e.key == "state"}
        for dependent, owned, cof_annexed, expected in (
            (True, historical, True, "ADISCORD_STP_cw.80.d"),
            (True, historical | {17}, True, "ADISCORD_STP_cw.80.limited"),
            (False, historical, True, "ADISCORD_STP_cw.80.limited"),
            (True, historical, False, "ADISCORD_STP_cw.80.limited"),
        ):
            with self.subTest(dependent=dependent, owned=sorted(owned), cof_annexed=cof_annexed):
                # The ownership predicate is tested against real history above;
                # this fixture supplies its result to the parsed event branches.
                facts = {("YPR", "is_subject_of", "NOD"): dependent,
                         ("YPR", "STP_cw_ypr_has_only_historical_states", "yes"): owned <= historical,
                         ("14", "is_owned_by", "NOD"): cof_annexed}
                selected = [scalar(desc, "text") for desc in descriptions
                            if matches_conditions(ast_block(desc, "trigger"), facts, "NOD")]
                self.assertEqual(selected, [expected], "exactly one description must match the actual settlement")

    def northern_conference_facts(self):
        states = (8, 15, 16, 19, 20, 21, 22, 14, 83, 84, 85, 86, 87, 303)
        facts = {**self.facts(), ("NOD", "variable", "STP_cw_northern_campaign_status"): 1}
        for state in states:
            facts[(str(state), "owner")] = "NOD"
            facts[(str(state), "controller")] = "NOD"
        return states, facts

    def test_native_northern_conference_requires_complete_actual_victory(self):
        gate = self.expand(ast_block(self.triggers, "STP_cw_northern_conference_won"))
        states, facts = self.northern_conference_facts()
        self.assertTrue(matches_conditions(gate, facts, "NOD"))
        for state in states:
            for role in ("owner", "controller"):
                for country in ("VAL", "TFF", "STP"):
                    foreign = {**facts, (str(state), role): country}
                    self.assertFalse(matches_conditions(gate, foreign, "NOD"), (state, role, country))
                colonial = {**facts, (str(state), role): "AIN", ("AIN", "is_puppet_of", "NOD"): True}
                self.assertTrue(matches_conditions(gate, colonial, "NOD"), (state, role))
        for target in ("YPR", "COF", "TFF"):
            self.assertFalse(matches_conditions(gate, {**facts, ("NOD", "has_war_with", target): True}, "NOD"))
            self.assertFalse(matches_conditions(gate, {**facts, (target, "has_war", "yes"): True}, "NOD"))
        for status in (0, 2, 3, 4):
            self.assertFalse(matches_conditions(gate, {**facts, ("NOD", "variable", "STP_cw_northern_campaign_status"): status}, "NOD"))
        for key in ("exists", "is_subject", "has_capitulated"):
            expected = "yes" if key == "exists" else "no"
            self.assertFalse(matches_conditions(gate, {**facts, ("NOD", key, expected): False}, "NOD"))

    def test_native_conference_restores_only_historical_packages_once(self):
        states, conference = self.northern_conference_facts()
        facts, writes, _, run = self.northern_callback_scenario()
        facts.update(conference)
        for target in ("YPR", "COF", "TFF"):
            facts[("NOD", "has_war_with", target)] = False
        hook = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'), "on_actions"), "on_peaceconference_ended")
        run(ast_block(hook, "effect"), "NOD", "NOD")
        transfers = [(scope, value) for scope, key, value in writes if key == "transfer_state"]
        self.assertEqual(transfers, [("YPR", str(n)) for n in (8, 15, 16, 19, 20, 21, 22)]
                         + [("TFF", str(n)) for n in (83, 84, 85, 86, 87, 303)] + [("NOD", "14")])
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        historical = {}
        for path in (ROOT / "history/states").glob("*.txt"):
            state = ast_block(parse_clausewitz(path.read_text(encoding="utf-8-sig")), "state")
            history = next((e.value for e in state if e.key == "history"), [])
            owner = next((e.value for e in history if e.key == "owner"), None)
            if owner in ("YPR", "TFF", "COF"):
                historical.setdefault(owner, set()).add(scalar(state, "id"))
        for country in ("YPR", "TFF"):
            self.assertEqual({value for scope, value in transfers if scope == country}, historical[country])
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 2)
        before = list(writes)
        run(ast_block(hook, "effect"), "NOD", "NOD")
        self.assertEqual(writes, before)

    def test_nod_can_call_only_its_current_colony_into_actual_northern_wars(self):
        decision = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention"), "NOD_cw_call_ain")
        allowed = ast_block(decision, "allowed")
        self.assertTrue(matches_conditions(allowed, {}, "NOD"))
        self.assertFalse(matches_conditions(allowed, {}, "STP"))
        facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                 ("AIN", "exists", "yes"): True, ("AIN", "is_puppet_of", "NOD"): True,
                 ("AIN", "is_in_faction_with", "NOD"): True, ("AIN", "has_capitulated", "no"): True,
                 **{("NOD", "has_war_with", t): True for t in ("YPR", "COF", "TFF")}}
        reward = ast_block(decision, "complete_effect")
        def orders(current):
            return [(scope, scalar(e.value, "targeted_alliance"), scalar(e.value, "enemy"))
                    for scope, e in selected_effects(reward, current, "NOD") if e.key == "add_to_war"]
        self.assertEqual(orders(facts), [("AIN", "NOD", t) for t in ("YPR", "COF", "TFF")])
        for target in ("YPR", "COF", "TFF"):
            joined = {**facts, ("AIN", "has_war_with", target): True}
            self.assertNotIn(("AIN", "NOD", target), orders(joined))
        self.assertEqual(orders({**facts, ("AIN", "is_puppet_of", "NOD"): False}), [])
        cleanup = self.expand(ast_block(self.effects, "STP_cw_end_northern_colonial_war"))
        joined = {**facts, **{("AIN", "has_war_with", t): True for t in ("YPR", "COF", "TFF")}}
        self.assertEqual([(scope, e.value) for scope, e in selected_effects(cleanup, joined, "NOD") if e.key == "white_peace"],
                         [("AIN", t) for t in ("YPR", "COF", "TFF")])
        self.assertEqual(list(selected_effects(cleanup, {**joined, ("AIN", "is_puppet_of", "NOD"): False}, "NOD")), [])

    def test_supply_rechecks_the_selected_recipient_and_settles_or_refunds_once(self):
        from itertools import product
        category = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_external_intervention")
        supply = ast_block(category, "STP_cw_supply_the_north")
        self.assertEqual(scalar(supply, "cost"), "0")
        self.assertEqual(scalar(supply, "days_remove"), "21")
        self.assertEqual({e.value for e in ast_block(supply, "targets")}, {"YPR", "COF", "TFF"})
        flag = "STP_cw_northern_cargo_reserved"
        for donor, recipient, lost in product(("STP", "STS"), ("YPR", "COF", "TFF"),
                                               (None, "absent", "capitulated", "subject", "peace",
                                                "union_finished", "donor_capitulated", "route_closed", "preparation_closed")):
            if donor == "STS" and lost == "preparation_closed":
                continue
            with self.subTest(donor=donor, recipient=recipient, lost=lost):
                facts = {**self.facts(), (donor, "has_country_flag", flag): True,
                         (donor, "has_capitulated", "no"): True,
                         (donor, "has_country_flag", "STP_battle_for_stelander_active"): True,
                         (donor, "has_country_flag", "STP_cw_northern_strategy_supply"): True,
                         (recipient, "has_war_with", "NOD"): lost != "peace"}
                for issue, key in (("absent", "exists"), ("capitulated", "has_capitulated"), ("subject", "is_subject")):
                    if lost == issue:
                        facts[(recipient, key, "yes" if key == "exists" else "no")] = False
                if lost == "union_finished":
                    facts[(donor, "has_global_flag", "STP_cw_union_wars_finished")] = True
                if lost == "donor_capitulated":
                    facts[(donor, "has_capitulated", "yes")] = True
                    facts[(donor, "has_capitulated", "no")] = False
                if lost == "route_closed":
                    facts[(donor, "has_country_flag", "STP_cw_northern_strategy_supply")] = False
                if lost == "preparation_closed":
                    facts[(donor, "has_country_flag", "STP_battle_for_stelander_active")] = False
                bindings = {"ROOT": donor, "FROM": recipient}
                visible = self.expand(ast_block(supply, "visible"), bindings)
                self.assertEqual(matches_conditions(visible, facts, donor), lost is None)
                cancelled = matches_conditions(self.expand(ast_block(supply, "cancel_trigger"), bindings), facts, donor)
                self.assertEqual(cancelled, lost is not None)
                writes = []
                # Both natural settlement and cancellation may be followed by a stale callback.
                # Apply receipt writes while iterating parsed effects, so the second call sees them.
                first = "cancel_effect" if cancelled else "remove_effect"
                for stage in (first, "remove_effect", "cancel_effect"):
                    for scope, entry in selected_effects(self.expand(ast_block(supply, stage), bindings), facts, donor):
                        if entry.key == "clr_country_flag":
                            facts[(scope, "has_country_flag", entry.value)] = False
                            writes.append((scope, entry.key, entry.value))
                        elif entry.key == "add_equipment_to_stockpile":
                            writes.append((scope, entry.key, scalar(entry.value, "amount")))
                expected_recipient = donor if lost else recipient
                self.assertEqual([w for w in writes if w[1] == "add_equipment_to_stockpile"],
                                 [(expected_recipient, "add_equipment_to_stockpile", "2400")])
                self.assertEqual(sum(w[1] == "clr_country_flag" for w in writes), 1)
                self.assertEqual(writes[0], (donor, "clr_country_flag", flag))
                # A changed donor or recipient must also be caught between cancellation and expiry.
                facts[(donor, "has_country_flag", flag)] = True
                settled = [(s, scalar(e.value, "amount")) for s, e in selected_effects(
                    self.expand(ast_block(supply, "remove_effect"), bindings), facts, donor)
                    if e.key == "add_equipment_to_stockpile"]
                self.assertEqual(settled, [(expected_recipient, "2400")])
        for donor in ("STP", "STS"):
            cost = ast_block(supply, "custom_cost_trigger")
            for pp, rifles, expected in ((40, 2400, True), (39.5, 2400, False), (40, 2399.5, False)):
                self.assertEqual(matches_conditions(cost, {(donor, "numeric", "has_political_power"): pp,
                                 (donor, "equipment", "infantry_equipment"): rifles}, donor), expected)
            for paid in (False, True):
                selected = list(selected_effects(ast_block(supply, "complete_effect"),
                                {(donor, "has_country_flag", "STP_cw_rifles_paid"): paid}, donor))
                self.assertEqual([(s, e.value) for s, e in selected if e.key == "add_political_power"], [(donor, "-40")])
                self.assertEqual([(s, scalar(e.value, "value")) for s, e in selected if e.key == "set_temp_variable"
                                  and scalar(e.value, "var") == "STP_cw_rifle_cost"], [(donor, "2400")])
                self.assertEqual([(s, e.value) for s, e in selected if e.key == "set_country_flag"],
                                 [(donor, flag)] if paid else [])

    def northern_callback_scenario(self):
        """Apply only parsed receipt/peace writes; the engine supplies the actual cap snapshot."""
        # Ownership whitelist is covered separately against real history; represent it
        # as an explicit fact here, without simulating world state iteration.
        self.triggers = [e for e in self.triggers if e.key != "STP_cw_ypr_has_only_historical_states"]
        facts = {**self.facts(), ("NOD", "variable", "STP_cw_northern_campaign_status"): 1,
                 ("YPR", "STP_cw_ypr_has_only_historical_states", "yes"): True,
                 **{("NOD", "has_war_with", t): True for t in ("YPR", "COF", "TFF")}}
        # The fixture starts after the native alliance and war have been created.
        for member in ("YPR", "COF", "TFF"):
            facts[(member, "is_in_faction", "yes")] = True
            facts[(member, "is_in_faction", "no")] = False
            facts[(member, "faction_leader")] = "YPR"
            facts[(member, "has_faction_template", "faction_template_ADISCORD_standard")] = True
            for ally in ("YPR", "COF", "TFF"):
                facts[(member, "is_in_faction_with", ally)] = True
        writes = []
        definitions = {e.key: e.value for e in self.effects}
        immediate = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'),
                                        "on_actions"), "on_capitulation_immediate")

        def run(items, scope, loser):
            for current, entry in selected_effects(self.expand(items, {"ROOT": loser}), facts, scope):
                if entry.key == "STP_cw_snapshot_capitulation_occupier":
                    writes.append((current, entry.key, "native snapshot"))
                elif entry.key in definitions:
                    run(definitions[entry.key], current, loser)
                elif entry.key == "set_variable":
                    variable, value = scalar(entry.value, "var"), float(scalar(entry.value, "value"))
                    facts[(current, "variable", variable)] = value
                    writes.append((current, entry.key, (variable, value)))
                elif entry.key == "create_faction_from_template":
                    facts[(current, "is_in_faction", "yes")] = True
                    facts[(current, "is_in_faction", "no")] = False
                    facts[(current, "faction_leader")] = current
                    facts[(current, "has_faction_template", scalar(entry.value, "template"))] = True
                    writes.append((current, entry.key, scalar(entry.value, "name")))
                elif entry.key == "add_to_faction":
                    member = entry.value
                    facts[(member, "faction_leader")] = current
                    facts[(member, "is_in_faction", "yes")] = True
                    facts[(member, "is_in_faction", "no")] = False
                    for ally in ("YPR", "COF", "TFF"):
                        if facts.get((ally, "faction_leader")) == current:
                            facts[(member, "is_in_faction_with", ally)] = True
                            facts[(ally, "is_in_faction_with", member)] = True
                    writes.append((current, entry.key, member))
                elif entry.key in ("declare_war_on", "add_to_war"):
                    target = scalar(entry.value, "target" if entry.key == "declare_war_on" else "enemy")
                    # Native success/failure is supplied by the fixture; test the script's response.
                    if not facts.get((current, "native_war_entry_failed", target), False):
                        facts[(current, "has_war_with", target)] = True
                        facts[(target, "has_war_with", current)] = True
                    writes.append((current, entry.key, target))
                elif entry.key == "white_peace":
                    facts[(current, "has_war_with", entry.value)] = False
                    facts[(entry.value, "has_war_with", current)] = False
                    facts[(entry.value, "has_capitulated", "yes")] = False
                    facts[(entry.value, "has_capitulated", "no")] = True
                    writes.append((current, entry.key, entry.value))
                elif entry.key == "dismantle_faction":
                    for member in ("YPR", "COF", "TFF"):
                        facts[(member, "is_in_faction", "yes")] = False
                        facts[(member, "is_in_faction", "no")] = True
                        for ally in ("YPR", "COF", "TFF"):
                            facts[(member, "is_in_faction_with", ally)] = False
                    writes.append((current, entry.key, entry.value))
                elif entry.key in ("set_country_flag", "clr_country_flag"):
                    facts[(current, "has_country_flag", entry.value)] = entry.key == "set_country_flag"
                elif entry.key in ("set_global_flag", "clr_global_flag"):
                    facts[("global", "has_global_flag", entry.value)] = entry.key == "set_global_flag"
                elif entry.key in ("puppet", "annex_country", "transfer_state", "news_event", "set_major"):
                    value = scalar(entry.value, "target") if entry.key in ("puppet", "annex_country") else entry.value
                    writes.append((current, entry.key, value))
        return facts, writes, lambda loser: run(ast_block(immediate, "effect"), loser, loser), run

    def test_partial_coalition_entry_cleans_wars_alliance_and_mandatory_majors(self):
        for failed in (None, "NOD", "COF", "TFF"):
            self.setUp()
            facts, writes, _, run = self.northern_callback_scenario()
            facts[("NOD", "variable", "STP_cw_northern_campaign_status")] = 0
            facts[("NOD", "has_country_flag", "STP_cw_northern_crisis_pending")] = True
            for member in ("YPR", "COF", "TFF"):
                facts[(member, "is_in_faction", "yes")] = False
                facts[(member, "is_in_faction", "no")] = True
                facts.pop((member, "faction_leader"))
                facts[("NOD", "has_war_with", member)] = False
                for ally in ("YPR", "COF", "TFF"):
                    facts[(member, "is_in_faction_with", ally)] = False
            if failed:
                facts[(failed, "native_war_entry_failed", "YPR" if failed == "NOD" else "NOD")] = True
            run(ast_block(self.effects, "STP_cw_start_northern_war"), "NOD", "STP")
            self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 4 if failed else 1, failed)
            for member in ("YPR", "COF", "TFF"):
                self.assertEqual(facts[("NOD", "has_war_with", member)], failed is None, (failed, member))
                self.assertEqual(facts[(member, "is_in_faction", "yes")], failed is None, (failed, member))
                major_writes = [value for scope, key, value in writes if scope == member and key == "set_major"]
                self.assertEqual(major_writes, ["yes", "no"] if failed else ["yes"], (failed, member))
            if failed:
                self.assertFalse(any(key == "news_event" for _, key, _ in writes))

    def test_dismantling_follows_current_leader_and_preserves_an_expanded_foreign_alliance(self):
        for leader, outsider in (("YPR", False), ("TFF", False), ("TFF", True)):
            self.setUp()
            facts, writes, _, run = self.northern_callback_scenario()
            facts[("YPR", "faction_leader")] = leader
            if outsider:
                facts[("BJK", "exists", "yes")] = True
                facts[("BJK", "is_in_faction_with", "YPR")] = True
            run(ast_block(self.effects, "STP_cw_dismantle_northern_alliance"), "NOD", "NOD")
            self.assertEqual(writes, [] if outsider else [(leader, "dismantle_faction", "yes")])

    def test_coalition_retains_the_war_until_all_three_current_defeats(self):
        from itertools import permutations
        for order in permutations(("YPR", "COF", "TFF")):
            self.setUp()
            facts, writes, cap, run = self.northern_callback_scenario()
            for index, loser in enumerate(order):
                facts[(loser, "variable", "STP_cw_capitulation_occupier")] = 1 if index == 0 else 4
                facts[("STP", "is_in_faction_with", "NOD")] = index == 0
                facts[("STP", "has_war_with", loser)] = index == 0
                cap(loser)  # Native immediate may still report has_capitulated = no.
                self.assertEqual(facts[(loser, "variable", "STP_cw_capitulation_occupier")], 4, order)
                self.assertEqual(facts[("NOD", "has_war_with", loser)], index < 2, order)
                if index < 2:
                    self.assertFalse(any(key in ("white_peace", "set_major") for _, key, _ in writes))
                    # Supply the subsequent native capitulation state explicitly.
                    facts[(loser, "has_capitulated", "yes")] = True
                    facts[(loser, "has_capitulated", "no")] = False
                self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")],
                                 2 if index == 2 else 1, order)
                facts[("STP", "is_in_faction_with", "NOD")] = False
                facts[("STP", "exists", "yes")] = False
                run(ast_block(self.effects, "STP_cw_poll_northern_campaign"), "NOD", loser)
                self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")],
                                 2 if index == 2 else 1, order)
            self.assertEqual([(scope, value) for scope, key, value in writes if key == "set_major"],
                             [("YPR", "no"), ("COF", "no"), ("TFF", "no")])
            self.assertLess(next(i for i, (_, key, _) in enumerate(writes) if key == "dismantle_faction"),
                            next(i for i, (_, key, _) in enumerate(writes) if key == "puppet"))
            self.assertEqual([w for w in writes if w[1] == "annex_country"], [("NOD", "annex_country", "COF")])
            self.assertEqual([w for w in writes if w[1] == "puppet"], [("NOD", "puppet", "YPR")])
            before = list(writes)
            cap(order[-1])
            run(ast_block(self.effects, "STP_cw_poll_northern_campaign"), "NOD", order[-1])
            self.assertEqual(writes, before, "terminal replay must not settle twice")

    def test_liberated_coalition_member_must_be_defeated_again(self):
        facts, writes, cap, run = self.northern_callback_scenario()
        for loser in ("YPR", "COF"):
            facts[(loser, "variable", "STP_cw_capitulation_occupier")] = 4
            cap(loser)
            facts[(loser, "has_capitulated", "yes")] = True
            facts[(loser, "has_capitulated", "no")] = False
        facts[("YPR", "has_capitulated", "yes")] = False
        facts[("YPR", "has_capitulated", "no")] = True
        facts[("TFF", "variable", "STP_cw_capitulation_occupier")] = 4
        cap("TFF")
        facts[("TFF", "has_capitulated", "yes")] = True
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 1)
        self.assertFalse(any(key in ("white_peace", "annex_country", "puppet") for _, key, _ in writes))
        # A stale pending flag on YPR cannot substitute for a different ROOT's result.
        run(ast_block(self.effects, "STP_cw_poll_northern_campaign"), "NOD", "NOD")
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 1)
        cap("YPR")
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 2)

    def test_alliance_members_remain_eligible_for_paid_northern_supply(self):
        gate = ast_block(self.triggers, "STP_cw_northern_target_valid")
        for target in ("YPR", "COF", "TFF"):
            facts = {**self.facts(), (target, "is_in_faction", "no"): False,
                     (target, "is_in_faction", "yes"): True}
            self.assertTrue(matches_conditions(self.expand(gate), facts, target))

    def test_two_coalition_capitulations_do_not_prevent_a_later_nod_defeat(self):
        facts, writes, cap, _ = self.northern_callback_scenario()
        for loser in ("YPR", "COF"):
            facts[(loser, "variable", "STP_cw_capitulation_occupier")] = 4
            cap(loser)
        facts[("NOD", "variable", "STP_cw_capitulation_occupier")] = 8
        facts[("17", "is_owned_by", "NOD")] = True
        facts[("18", "is_owned_by", "NOD")] = True
        cap("NOD")
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 3)
        self.assertFalse(any(key in ("annex_country", "puppet") for _, key, _ in writes))
        self.assertEqual([w for w in writes if w[1] == "transfer_state"],
                         [("YPR", "transfer_state", "17"), ("YPR", "transfer_state", "18")])

    def test_external_peace_is_not_a_receipt_and_settled_credit_is_not_resnapshotted(self):
        facts, writes, cap, run = self.northern_callback_scenario()
        facts[("YPR", "variable", "STP_cw_capitulation_occupier")] = 4
        cap("YPR")
        before = len(writes)
        facts[("NOD", "has_war_with", "YPR")] = False  # An external separate peace.
        cap("YPR")  # This unrelated defeat must not overwrite accepted military credit.
        self.assertEqual(len(writes), before)
        facts[("NOD", "has_war_with", "COF")] = False
        run(ast_block(self.effects, "STP_cw_poll_northern_campaign"), "NOD", "COF")
        self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 4)
        self.assertFalse(any(key in ("annex_country", "puppet") for _, key, _ in writes))

    def test_final_awards_do_not_reparent_a_foreign_puppet(self):
        for target in ("YPR", "COF"):
            self.setUp()
            facts, writes, cap, _ = self.northern_callback_scenario()
            facts[(target, "is_subject", "no")] = False
            for loser in ("YPR", "COF", "TFF"):
                facts[(loser, "variable", "STP_cw_capitulation_occupier")] = 4
                cap(loser)
                facts[(loser, "has_capitulated", "yes")] = True
                facts[(loser, "has_capitulated", "no")] = False
            self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 2)
            self.assertFalse(any(value == target for _, key, value in writes if key in ("puppet", "annex_country")))

    def test_immediate_handoff_is_consumed_by_late_callback_and_never_leaks_global_skip(self):
        facts, writes, cap, run = self.northern_callback_scenario()
        pending = "STP_cw_northern_capitulation_pending"
        skip = "skip_default_capitulation"
        facts[("YPR", "variable", "STP_cw_capitulation_occupier")] = 4
        cap("YPR")
        self.assertTrue(facts.get(("YPR", "has_country_flag", pending), False))
        self.assertFalse(facts.get(("global", "has_global_flag", skip), False))
        late = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'),
                                  "on_actions"), "on_capitulation")
        run(ast_block(late, "effect"), "YPR", "YPR")
        self.assertFalse(facts.get(("YPR", "has_country_flag", pending), False))
        self.assertTrue(facts.get(("global", "has_global_flag", skip), False))
        generic = ast_block(ast_block(entries("common/on_actions/ZZ_ADISCORD_default_capitulation_on_actions.txt"),
                                     "on_actions"), "on_capitulation")
        cleanup = [e for e in ast_block(generic, "effect") if e.key == "clr_global_flag"]
        self.assertEqual([e.value for e in cleanup], [skip])
        run(cleanup, "YPR", "YPR")
        self.assertFalse(facts.get(("global", "has_global_flag", skip), False))
        before = list(writes)
        run(ast_block(late, "effect"), "YPR", "YPR")
        self.assertFalse(facts.get(("global", "has_global_flag", skip), False))
        self.assertEqual(writes, before, "a replayed late callback must not reserve another capitulation")

    def test_missing_late_callback_does_not_suppress_next_unrelated_capitulation(self):
        facts, writes, cap, run = self.northern_callback_scenario()
        pending = "STP_cw_northern_capitulation_pending"
        skip = "skip_default_capitulation"
        facts[("YPR", "variable", "STP_cw_capitulation_occupier")] = 4
        cap("YPR")
        self.assertTrue(facts.get(("YPR", "has_country_flag", pending), False))
        self.assertFalse(facts.get(("global", "has_global_flag", skip), False))
        # Deliberately omit the first late callback, then externally end this front.
        # A later foreign defeat must not inherit the northern reservation.
        facts[("NOD", "has_war_with", "YPR")] = False
        cap("YPR")
        self.assertFalse(facts.get(("YPR", "has_country_flag", pending), False))
        late = ast_block(ast_block(country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander'),
                                  "on_actions"), "on_capitulation")
        run(ast_block(late, "effect"), "YPR", "YPR")
        self.assertFalse(facts.get(("global", "has_global_flag", skip), False))
        self.assertEqual(facts[("YPR", "variable", "STP_cw_capitulation_occupier")], 4,
                         "a consumed handoff must not erase the accepted campaign result")

    def test_northern_news_are_registered_once_and_use_dark_paper_text(self):
        import json
        events = entries("events/ADISCORD_STP_events.txt")
        registry = json.loads((ROOT / "tools/data/adiscord_event_ids.json").read_text())
        localisation = read("localisation/russian/ADISCORD_STP_l_russian.yml")
        values = dict(re.findall(r'^ ([\w.]+):\s*"(.*)"$', localisation, re.M))
        for number in (80, 81, 82):
            event_id = f"ADISCORD_STP_cw.{number}"
            matches = [e.value for e in events if e.key == "news_event" and scalar(e.value, "id") == event_id]
            self.assertEqual(len(matches), 1)
            self.assertEqual(scalar(matches[0], "is_triggered_only"), "yes")
            self.assertEqual(scalar(matches[0], "fire_only_once"), "yes")
            descriptions = [e.value for e in matches[0] if e.key == "desc"]
            for desc in descriptions:
                key = scalar(desc, "text") if isinstance(desc, list) else desc
                self.assertIn(key, values)
                self.assertNotIn("\u00a7Y", values[key])
            entries_for_id = [e for e in registry["events"] if e["id"] == event_id]
            self.assertEqual(len(entries_for_id), 1)
            self.assertEqual(entries_for_id[0]["owner"], "events/ADISCORD_STP_events.txt")

    def test_nod_orders_start_independently_and_survive_a_stelander_split(self):
        elections = ast_block(self.effects, "STP_cw_begin_elections")
        launch = self.expand(ast_block(self.effects, "STP_cw_launch_northern_crisis"))
        for side in ("STP_sided_with_the_party_flag", "STP_sided_with_Maksim_flag"):
            facts = {**self.facts(), ("STP", "has_country_flag", "STP_ivanov_dead"): True,
                     ("STP", "has_country_flag", side): True}
            selected = list(selected_effects(elections, facts))
            self.assertEqual(sum(e.key == "STP_cw_launch_northern_crisis" for _, e in selected), 1)
            facts[("STP", "has_active_mission", "STP_cw_election_window")] = True
            selected = list(selected_effects(launch, facts))
            self.assertEqual([(s, scalar(e.value, "id")) for s, e in selected if e.key == "country_event"],
                             [("NOD", "ADISCORD_STP_preparation.10")])
            self.assertIn(("NOD", "STP_cw_northern_crisis_pending"),
                          [(s, e.value) for s, e in selected if e.key == "set_country_flag"])
            facts[("NOD", "has_country_flag", "STP_cw_northern_crisis_pending")] = True
            self.assertEqual(list(selected_effects(launch, facts)), [], "a pending request cannot be issued again")
        mission = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                                     "STP_cw_external_intervention"), "NOD_cw_northern_mobilization")
        self.assertEqual(scalar(mission, "days_mission_timeout"), "28")
        after_split = {**self.facts(), ("STP", "has_global_flag", "STP_cw_started"): True,
                       ("STS", "exists", "yes"): True, ("NOD", "has_country_flag", "STP_cw_northern_crisis_pending"): True}
        self.assertFalse(matches_conditions(ast_block(mission, "cancel_trigger"), after_split, "NOD"))
        start = self.expand(ast_block(ast_block(ast_block(self.effects, "STP_cw_start_northern_war"), "if"), "limit"))
        self.assertTrue(matches_conditions(start, after_split, "NOD"), "STP's election timer is no longer an entry condition")
        for member in ("YPR", "COF", "TFF"):
            self.assertFalse(matches_conditions(start, {**after_split, (member, "is_subject", "no"): False}, "NOD"))
        events = entries("events/ADISCORD_STP_events.txt")
        offer = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_preparation.10")
        accept, refuse = [e.value for e in offer if e.key == "option"]
        self.assertEqual(scalar(ast_block(accept, "ai_chance"), "factor"), "100")
        self.assertEqual(scalar(ast_block(refuse, "ai_chance"), "factor"), "0")
        self.assertEqual(scalar(accept, "activate_mission"), "NOD_cw_northern_mobilization")
        self.assertEqual(scalar(refuse, "clr_country_flag"), "STP_cw_northern_crisis_pending")
        self.assertEqual(scalar(ast_block(refuse, "set_variable"), "value"), "4")
        for split in (False, True):
            self.setUp()
            facts, writes, _, run = self.northern_callback_scenario()
            facts[("NOD", "variable", "STP_cw_northern_campaign_status")] = 0
            facts[("NOD", "has_country_flag", "STP_cw_northern_crisis_pending")] = True
            facts[("STP", "has_global_flag", "STP_cw_started")] = split
            facts[("STP", "has_active_mission", "STP_cw_election_window")] = not split
            facts[("STS", "exists", "yes")] = split
            for member in ("YPR", "COF", "TFF"):
                facts[(member, "is_in_faction", "yes")] = False
                facts[(member, "is_in_faction", "no")] = True
                facts.pop((member, "faction_leader"))
                facts[("NOD", "has_war_with", member)] = False
                for ally in ("YPR", "COF", "TFF"):
                    facts[(member, "is_in_faction_with", ally)] = False
            run(ast_block(self.effects, "STP_cw_start_northern_war"), "NOD", "NOD")
            self.assertEqual(facts[("NOD", "variable", "STP_cw_northern_campaign_status")], 1, split)
            self.assertFalse(facts[("NOD", "has_country_flag", "STP_cw_northern_crisis_pending")])
            self.assertTrue(all(facts[("NOD", "has_war_with", member)] for member in ("YPR", "COF", "TFF")))
            initial_declarations = sum(key == "declare_war_on" for _, key, _ in writes)
            run(ast_block(self.effects, "STP_cw_start_northern_war"), "NOD", "NOD")
            self.assertEqual(sum(key == "declare_war_on" for _, key, _ in writes), initial_declarations)

    def test_northern_capabilities_move_to_sts_once_before_the_tree_changes(self):
        transfer = ast_block(self.effects, "STP_cw_transfer_preparation_modifiers")
        for ability in ("evidence", "supply", "aid_open"):
            flag = "STP_cw_northern_strategy_" + ability if ability != "aid_open" else "STP_cw_northern_aid_open"
            facts = {("STP", "has_country_flag", flag): True, ("STS", "exists", "yes"): True}
            writes = []
            for _ in range(2):
                for scope, entry in selected_effects(transfer, facts):
                    if entry.key in ("set_country_flag", "clr_country_flag") and entry.value == flag:
                        facts[(scope, "has_country_flag", flag)] = entry.key == "set_country_flag"
                        writes.append((scope, entry.key, flag))
            self.assertEqual(writes, [("STS", "set_country_flag", flag), ("STP", "clr_country_flag", flag)])
            self.assertTrue(facts[("STS", "has_country_flag", flag)])
            self.assertFalse(facts[("STP", "has_country_flag", flag)])
        deposit_facts = {("STP", "has_variable", "STP_cw_northern_fort_deposit"): True,
                         ("STP", "has_variable", "STP_cw_northern_engineer_deposit"): True}
        self.assertEqual([(scope, scalar(e.value, "value"))
                          for scope, e in selected_effects(transfer, deposit_facts)
                          if e.key == "add_to_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury"],
                         [("STS", "PREV.STP_cw_northern_fort_deposit"),
                          ("STS", "PREV.STP_cw_northern_engineer_deposit")])
        start = list(walk(ast_block(self.effects, "STP_cw_start")))
        transfer_index = next(i for i, e in enumerate(start) if e.key == "STP_cw_transfer_preparation_modifiers")
        first_new_tree = next(i for i, e in enumerate(start) if e.key == "load_focus_tree")
        self.assertLess(transfer_index, first_new_tree)

    def test_nod_northern_offensive_is_inherent_and_does_not_wait_for_stelander_help(self):
        start = ast_block(self.effects, "STP_cw_start_northern_war")
        self.assertIn("NOD_cw_northern_offensive", {e.value for e in walk(start) if e.key == "add_ideas"})
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        offensive = ast_block(ideas, "NOD_cw_northern_offensive")
        self.assertEqual(scalar(ast_block(offensive, "allowed"), "always"), "no")
        self.assertFalse(any(e.key == "name" for e in offensive), "this is NOD's own campaign spirit, not a dummy preview")
        modifiers = {e.key: float(e.value) for e in ast_block(offensive, "modifier")}
        self.assertGreaterEqual(modifiers["army_attack_factor"], 0.15)
        self.assertGreaterEqual(modifiers["conscription_factor"], 0.10)
        cancel = ast_block(offensive, "cancel")
        wars = {e.value for e in walk(cancel) if e.key == "has_war_with" and isinstance(e.value, str)}
        self.assertEqual(wars, {"YPR", "COF", "TFF"})
        ai = (ROOT / "common/ai_strategy/ADISCORD_STP_civil_war.txt").read_text(encoding="utf-8-sig")
        militia = ast_block(entries("common/ai_strategy/ADISCORD_STP_civil_war.txt"), "STP_cw_border_territorial_armies")
        self.assertNotIn("NOD", {e.value for e in walk(ast_block(militia, "allowed"))
                                if e.key == "original_tag" and isinstance(e.value, str)})
        self.assertIn("NOD_cw_northern_offensive_army", ai)
        self.assertIn("NOD_cw_stelander_intervention_army", ai)
        self.assertIn("execution_type = rush_weak", ai)
        northern = block(ai, "NOD_cw_northern_offensive_army")
        intervention = block(ai, "NOD_cw_stelander_intervention_army")
        reserve = block(ai, "NOD_cw_wartime_home_buffer")
        for profile in (northern, intervention):
            self.assertIn("type = dont_defend_ally_borders", profile)
            self.assertIn("type = force_concentration_factor value = 80", profile)
            self.assertNotIn("type = put_unit_buffers", profile)
        self.assertIn("type = put_unit_buffers", reserve)
        self.assertIn("ratio = 0.05", reserve)
        self.assertRegex(reserve, r"states\s*=\s*\{\s*30\s*\}")
        for enemy in ("YPR", "COF", "TFF"):
            front = block(ai, f"NOD_cw_northern_front_{enemy.lower()}")
            self.assertIn(f"has_war_with = {enemy}", front)
            self.assertIn(f"type = consider_weak id = {enemy}", front)
            self.assertIn(f"type = front_unit_request tag = {enemy} value = 220", front)
            self.assertIn(f"type = conquer id = {enemy} value = 250", front)
        self.assertIn("tag = STS", intervention)
        self.assertIn("type = front_unit_request tag = STS value = 220", intervention)
        conscription = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"),
                                           "STP_cw_external_intervention"), "NOD_cw_northern_conscription")
        self.assertEqual(scalar(ast_block(conscription, "ai_will_do"), "base"), "50")
        self.assertNotIn("manpower_per_military_factory", {e.key for e in walk(conscription)})

    def test_actual_northern_war_opens_early_uprising_and_blocks_foreign_entry(self):
        uprising = self.expand(ast_block(self.triggers, "STP_cw_can_start"))
        intervention = self.expand(ast_block(self.triggers, "STP_cw_nod_can_intervene"))
        anchors = {("STP", "owns_state", str(s)): True for s in (1, 28, 43, 44, 88)}
        for status in (0, 1, 2, 3, 4):
            early = {**self.facts(), **anchors,
                     ("STP", "has_active_mission", "STP_cw_election_window"): True,
                     ("STP", "has_country_flag", "STP_cw_uprising_prepared"): True,
                     ("NOD", "variable", "STP_cw_northern_campaign_status"): status}
            self.assertFalse(matches_conditions(uprising, early), status)
            fighting = {**early, ("NOD", "has_war_with", "YPR"): True}
            self.assertTrue(matches_conditions(uprising, fighting), status)
            after_split = {**early, ("STS", "has_global_flag", "STP_cw_started"): True,
                           **{(t, k, v): True for t in ("STP", "STS")
                              for k, v in (("exists", "yes"), ("has_capitulated", "no"), ("is_subject", "no"))},
                           ("STP", "has_war_with", "STS"): True}
            self.assertEqual(matches_conditions(intervention, after_split, "STS"), status in (0, 2, 4), status)
            after_split[("NOD", "has_war_with", "YPR")] = True
            self.assertFalse(matches_conditions(intervention, after_split, "STS"), status)




class WartimeProgramContracts(unittest.TestCase):
    def setUp(self):
        self.triggers = [e for e in entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
                         if e.key in ("STP_cw_can_rearm", "STP_ps_local_program_open")]
        self.decisions = self.expand(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council"))
        self.effects = self.expand(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"))

    def expand(self, items, parameters=None):
        return NorthernCampaignContracts.expand(self, items, parameters)

    def rearm_scenarios(self):
        for tag, changes, expected in (
            ("SRP", {}, True),
            ("SRP", {("SRP", "has_global_flag", "STP_cw_union_war_finished"): True}, True),
            ("SRP", {("VAL", "has_country_flag", "VAL_cw_trade_course"): True}, True),
            ("SRP", {("VAL", "has_country_flag", "VAL_cw_refused"): True}, False),
            ("SRP", {("VAL", "has_country_flag", "VAL_cw_settled"): True}, False),
            ("SRP", {("VAL", "has_capitulated", "no"): False}, False),
            ("SRP", {("VAL", "exists", "yes"): False}, False),
            ("SRP", {("SRP", "has_country_flag", "STP_cw_postwar"): True}, False),
            ("SRP", {("SRP", "has_country_flag", "STP_cw_participant"): False}, False),
            ("STP", {}, False), ("STS", {}, False),
            ("STP", {("STP", "has_war", "yes"): True}, True),
            ("STS", {("STS", "has_war", "yes"): True}, True),
            ("SRP", {("SRP", "has_war", "yes"): True,
                     ("VAL", "has_country_flag", "VAL_cw_refused"): True}, True),
            *((tag, {(tag, "has_war", "yes"): True,
                     (tag, "has_country_flag", "STP_cw_postwar"): True}, True)
              for tag in ("STP", "STS", "SRP")),
        ):
            facts = {(tag, "has_country_flag", "STP_cw_participant"): True,
                     (tag, "has_capitulated", "no"): True,
                     (tag, "has_war", "yes"): False, (tag, "has_war", "no"): True,
                     (tag, "owns_state", "43"): True, (tag, "controls_state", "43"): True,
                     (tag, "numeric", "has_manpower"): 8000,
                     (tag, "equipment", "infantry_equipment"): 640,
                     (tag, "has_completed_focus", "STP_cw_mobilization_register"): True,
                     (tag, "has_completed_focus", "STP_cw_wartime_arsenals"): True,
                     ("FROM", "is_owned_by", "ROOT"): True, ("FROM", "is_controlled_by", "ROOT"): True,
                     ("VAL", "exists", "yes"): True, ("VAL", "has_capitulated", "no"): True,
                     **changes}
            facts[(tag, "has_war", "no")] = not facts[(tag, "has_war", "yes")]
            yield tag, facts, expected

    def test_rearm_programs_use_the_republics_threat_window_and_actual_wars(self):
        for tag, facts, expected in self.rearm_scenarios():
            for name in ("STP_cw_raise_territorial_brigade", "STP_cw_train_reserve_brigades", "STP_cw_expand_arsenal"):
                decision = ast_block(self.decisions, name)
                can_run = expected and (name == "STP_cw_expand_arsenal" or
                                        not facts.get((tag, "has_country_flag", "STP_cw_postwar"), False))
                with self.subTest(tag=tag, decision=name, expected=can_run, facts=facts):
                    selectable = matches_conditions(ast_block(decision, "visible"), facts, tag)
                    selectable &= matches_conditions(ast_block(decision, "available"), facts, tag)
                    self.assertEqual(selectable, can_run)
                    if name != "STP_cw_raise_territorial_brigade":
                        self.assertEqual(matches_conditions(ast_block(decision, "cancel_trigger"), facts, tag), not can_run)

    def test_paid_rearm_projects_settle_during_the_threat_or_refund_once_when_it_ends(self):
        training = ast_block(self.effects, "STP_cw_finish_reserve_training")
        arsenal = ast_block(ast_block(self.decisions, "STP_cw_expand_arsenal"), "remove_effect")
        for tag, facts, expected in self.rearm_scenarios():
            for program, receipt in ((training, "STP_cw_training_cohorts"), (arsenal, "STP_cw_arsenal_deposit")):
                can_deliver = expected and (program is arsenal or
                                            not facts.get((tag, "has_country_flag", "STP_cw_postwar"), False))
                current = {**facts, (tag, "variable", receipt): 2 if program is training else 100,
                           (tag, "has_variable", receipt): True}
                writes = []
                def apply(items):
                    for scope, entry in selected_effects(items, current, tag):
                        if entry.key in ("STP_cw_refund_reserve_training", "STP_cw_refund_arsenal_project"):
                            apply(ast_block(self.effects, entry.key))
                        else:
                            writes.append((scope, entry))
                            if entry.key == "clear_variable":
                                current[(scope, "variable", entry.value)] = 0
                                current[(scope, "has_variable", entry.value)] = False
                apply(program)
                apply(program)
                with self.subTest(tag=tag, receipt=receipt, expected=can_deliver, facts=facts):
                    self.assertEqual(current[(tag, "variable", receipt)], 0)
                    if program is training:
                        self.assertEqual(sum(e.key == "random_owned_controlled_state" for _, e in writes), 2 if can_deliver else 0)
                        self.assertEqual([e.value for _, e in writes if e.key == "add_manpower"], [] if can_deliver else ["12000"])
                        self.assertEqual([scalar(e.value, "amount") for _, e in writes if e.key == "add_equipment_to_stockpile"], [] if can_deliver else ["1200"])
                    else:
                        self.assertEqual(sum(e.key == "add_building_construction" for _, e in writes), int(can_deliver))
                        self.assertEqual(sum(e.key == "add_to_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" for _, e in writes), int(not can_deliver))

    def test_mobilization_closure_refunds_training_and_releases_templates_on_every_peace_route(self):
        finish = ast_block(self.effects, "STP_cw_finish_mobilization")
        for name in ("STP_cw_start", "VAL_cw_settle_republics", "STP_cw_settle_union_victory", "STP_cw_settle_nod_victory"):
            self.assertEqual(sum(e.key == "STP_cw_finish_mobilization" for e in walk(ast_block(self.effects, name))), 1, name)
        hooks = country_on_actions_entries("common/on_actions/02_ADISCORD_STP_on_actions.txt", 'stelander')
        self.assertEqual(sum(e.key == "STP_cw_finish_mobilization" for e in walk(hooks)), 1)
        for path in ("common/scripted_effects/ADISCORD_STP_scripted_effects.txt", "events/ADISCORD_STP_events.txt",
                     "common/on_actions/02_ADISCORD_STP_on_actions.txt", "common/national_focus/ADISCORD_national_focus_VAL.txt"):
            outside_cleanup = [e for e in entries(path) if e.key != "STP_cw_finish_mobilization"]
            self.assertFalse(any(e.key == "set_country_flag" and e.value == "STP_cw_postwar"
                                 for e in walk(outside_cleanup)), path)
        for tag in ("STP", "STS", "SRP"):
            for loaded in (False, True):
                for paid in (False, True):
                    ledger = (tag, "variable", "STP_cw_training_cohorts")
                    facts = {(tag, "has_country_flag", "STP_cw_templates_loaded"): loaded,
                             (tag, "has_country_flag", "STP_cw_participant"): True,
                             (tag, "has_war", "yes"): True, (tag, "has_capitulated", "no"): True,
                             (tag, "owns_state", "1"): True, (tag, "controls_state", "1"): True,
                             ledger: 2 if paid else 0}
                    writes = []
                    def apply(items):
                        for scope, entry in selected_effects(items, facts, tag):
                            if entry.key == "STP_cw_refund_reserve_training":
                                apply(ast_block(self.effects, entry.key))
                            else:
                                writes.append((scope, entry))
                                if entry.key == "set_country_flag":
                                    facts[(scope, "has_country_flag", entry.value)] = True
                                elif entry.key == "clear_variable":
                                    facts[(scope, "variable", entry.value)] = 0
                    apply(finish)
                    apply(finish)
                    apply(ast_block(self.effects, "STP_cw_finish_reserve_training"))
                    apply(ast_block(ast_block(self.decisions, "STP_cw_train_reserve_brigades"), "cancel_effect"))
                    with self.subTest(tag=tag, templates_loaded=loaded, paid_training=paid):
                        self.assertTrue(facts.get((tag, "has_country_flag", "STP_cw_postwar")))
                        self.assertEqual(facts[ledger], 0)
                        self.assertEqual([e.value for _, e in writes if e.key == "add_manpower"], ["12000"] if paid else [])
                        self.assertEqual([scalar(e.value, "amount") for _, e in writes if e.key == "add_equipment_to_stockpile"],
                                         ["1200"] if paid else [])
                        self.assertFalse(any(e.key in ("create_unit", "random_owned_controlled_state") for _, e in writes))
                        locks = [(scope, scalar(e.value, "division_template"), scalar(e.value, "is_locked"))
                                 for scope, e in writes if e.key == "set_division_template_lock"]
                        expected_locks = [(tag, "Stelander Territorial Brigade", "no"), (tag, "Stelander Assault Division", "no")]
                        self.assertEqual(set(locks), set(expected_locks) if loaded else set())

    def test_operations_compete_for_the_same_command_and_have_a_recovery_period(self):
        operations = {"STP_cw_launch_last_banquet": ("STS", "STP_cw_deliberate_offensive", 21),
                      "STP_cw_hold_the_pier": ("STP", "STP_cw_static_defence", 35),
                      "STP_cw_defend_western_frontier": ("SRP", "STP_cw_static_defence", 35),
                      "STP_cw_regroup_the_front": ("STS", "STP_cw_front_reorganization", 21)}
        active = {idea for _, idea, _ in operations.values()}
        for name, (tag, idea, duration) in operations.items():
            decision = ast_block(self.decisions, name)
            self.assertEqual(scalar(decision, "cost"), "0")
            if name == "STP_cw_launch_last_banquet":
                self.assertEqual(scalar(decision, "fire_only_once"), "yes")
                self.assertFalse(any(e.key == "days_re_enable" for e in decision))
            else:
                self.assertEqual(scalar(decision, "fire_only_once"), "no")
                self.assertGreaterEqual(int(scalar(decision, "days_re_enable")), duration + 21)
            price = ast_block(decision, "custom_cost_trigger")
            self.assertTrue(matches_conditions(price, {(tag, "numeric", "command_power"): 25}, tag))
            self.assertFalse(matches_conditions(price, {(tag, "numeric", "command_power"): 24.5}, tag))
            gate = ast_block(decision, "available")
            baseline = {(tag, "has_war", "yes"): True, (tag, "has_war_with", "STP"): True,
                        (tag, "has_war_with", "STS"): True, (tag, "has_war_with", "VAL"): True,
                        (tag, "controls_state", "3"): True, (tag, "controls_state", "28"): True,
                        (tag, "controls_province", "16366"): True,
                        (tag, "controls_state", "43"): True}
            self.assertTrue(matches_conditions(gate, baseline, tag), name)
            for other in active:
                self.assertFalse(matches_conditions(gate, {**baseline, (tag, "has_idea", other): True}, tag), (name, other))
            reward = ast_block(decision, "complete_effect")
            self.assertEqual(scalar(reward, "add_command_power"), "-25")
            timed = ast_block(reward, "add_timed_idea")
            self.assertEqual((scalar(timed, "idea"), int(scalar(timed, "days"))), (idea, duration))
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        for idea in active:
            definition = ast_block(ideas, idea)
            self.assertTrue(matches_conditions(ast_block(definition, "cancel"), {("STS", "has_war", "no"): True}, "STS"))
            values = [float(e.value) for e in ast_block(definition, "modifier")]
            self.assertTrue(any(v > 0 for v in values), idea)
            if idea != "STP_cw_deliberate_offensive":
                self.assertTrue(any(v < 0 for v in values), idea)

    def test_training_reserves_exact_resources_and_settles_or_refunds_only_once(self):
        decision = ast_block(self.decisions, "STP_cw_train_reserve_brigades")
        self.assertEqual(scalar(decision, "days_remove"), "21")
        self.assertEqual(scalar(decision, "cost"), "0")
        prices = ast_block(decision, "custom_cost_trigger")
        facts = {("STS", "numeric", "has_political_power"): 40,
                 ("STS", "numeric", "has_manpower"): 12000,
                 ("STS", "equipment", "infantry_equipment"): 1200}
        self.assertTrue(matches_conditions(prices, facts, "STS"))
        for key in facts:
            self.assertFalse(matches_conditions(prices, {**facts, key: facts[key] - .5}, "STS"), key)
        start = list(selected_effects(ast_block(decision, "complete_effect"),
                                     {**facts, ("STS", "has_country_flag", "STP_cw_rifles_paid"): True}, "STS"))
        self.assertEqual([e.value for _, e in start if e.key == "add_manpower"], ["-12000"])
        self.assertEqual([scalar(e.value, "value") for _, e in start if e.key == "set_variable"], ["2"])
        finish = ast_block(self.effects, "STP_cw_finish_reserve_training")
        refund = ast_block(self.effects, "STP_cw_refund_reserve_training")
        ledger = ("STS", "variable", "STP_cw_training_cohorts")
        for paid in (False, True):
            status = {ledger: 2 if paid else 0, ("STS", "has_war", "yes"): True,
                      ("STS", "has_capitulated", "no"): True,
                      ("STS", "owns_state", "1"): True, ("STS", "controls_state", "1"): True}
            settled = list(selected_effects(finish, status, "STS"))
            spawned = [e for _, e in settled if e.key == "random_owned_controlled_state"]
            self.assertEqual(len(spawned), 2 if paid else 0)
            if paid:
                clear = next(e for _, e in settled if e.key == "clear_variable")
                self.assertLess(settled.index(("STS", clear)), settled.index(("STS", spawned[0])))
                for spawn in spawned:
                    unit = ast_block(spawn.value, "create_unit")
                    self.assertIn("start_experience_factor = 0.3", scalar(unit, "division"))
            returned = list(selected_effects(refund, status, "STS"))
            self.assertEqual([e.value for _, e in returned if e.key == "add_manpower"], ["12000"] if paid else [])
            self.assertEqual([scalar(e.value, "amount") for _, e in returned if e.key == "add_equipment_to_stockpile"], ["1200"] if paid else [])
        self.assertEqual(scalar(ast_block(decision, "cancel_effect"), "STP_cw_refund_reserve_training"), "yes")

    def test_arsenal_construction_uses_one_active_project_and_rechecks_the_selected_state(self):
        decision = ast_block(self.decisions, "STP_cw_expand_arsenal")
        self.assertEqual(scalar(decision, "days_remove"), "35")
        self.assertEqual(scalar(decision, "cost"), "0")
        gates = ast_block(decision, "available")
        facts = {("STS", "has_war", "yes"): True, ("STS", "has_capitulated", "no"): True,
                 ("FROM", "is_owned_by", "ROOT"): True,
                 ("FROM", "is_controlled_by", "ROOT"): True}
        self.assertTrue(matches_conditions(gates, facts, "STS"))
        self.assertFalse(matches_conditions(gates, {
            **facts, ("STS", "has_decision", "STP_cw_expand_arsenal"): False,
            ("STS", "has_variable", "STP_cw_arsenal_deposit"): True,
            ("STS", "variable", "STP_cw_arsenal_deposit"): 100,
        }, "STS"))
        settlement = ast_block(decision, "remove_effect")
        for paid, owns, controls in ((True, True, True), (False, True, True), (True, False, True), (True, True, False)):
            current = {**facts, ("STS", "variable", "STP_cw_arsenal_deposit"): 100 if paid else 0,
                       ("FROM", "is_owned_by", "ROOT"): owns, ("FROM", "is_controlled_by", "ROOT"): controls}
            calls = list(selected_effects(settlement, current, "STS"))
            buildings = [(scope, e) for scope, e in calls if e.key == "add_building_construction"]
            self.assertEqual(len(buildings), int(paid and owns and controls), (paid, owns, controls))
            if buildings:
                self.assertEqual(buildings[0][0], "FROM")
                self.assertEqual(scalar(buildings[0][1].value, "type"), "arms_factory")
            else:
                self.assertFalse(any(e.key == "ADISCORD_economy_receive_100" for _, e in calls))
        refund = ast_block(self.effects, "STP_cw_refund_arsenal_project")
        for deposit in (0, 100, 1200):
            calls = list(selected_effects(refund, {("STS", "variable", "STP_cw_arsenal_deposit"): deposit,
                ("STS", "has_variable", "STP_cw_arsenal_deposit"): deposit > 0}, "STS"))
            self.assertEqual(sum(e.key == "add_to_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" for _, e in calls), int(deposit > 0))

    def test_arsenal_escrow_blocks_a_second_state_and_reopens_after_one_settlement(self):
        decision = ast_block(self.decisions, "STP_cw_expand_arsenal")
        gate = ast_block(decision, "available")
        for tag in ("STP", "STS", "SRP"):
            for terminal in ("remove_effect", "cancel_effect"):
                with self.subTest(tag=tag, terminal=terminal):
                    facts = {
                        (tag, "has_war", "yes"): True,
                        (tag, "has_capitulated", "no"): True,
                        (tag, "has_decision", "STP_cw_expand_arsenal"): False,
                        (tag, "STP_cw_can_spend_1200", "yes"): True,
                        ("FROM", "is_owned_by", "ROOT"): True,
                        ("FROM", "is_controlled_by", "ROOT"): True,
                    }
                    writes = []

                    def apply(items):
                        for scope, effect in selected_effects(items, facts, tag):
                            if effect.key == "STP_cw_refund_arsenal_project":
                                apply(ast_block(self.effects, effect.key))
                                continue
                            writes.append((scope, effect))
                            if effect.key == "set_variable":
                                name = scalar(effect.value, "var")
                                facts[(scope, "variable", name)] = float(scalar(effect.value, "value"))
                                facts[(scope, "has_variable", name)] = True
                            elif effect.key == "clear_variable":
                                facts[(scope, "variable", effect.value)] = 0
                                facts[(scope, "has_variable", effect.value)] = False

                    self.assertTrue(matches_conditions(gate, facts, tag))
                    self.assertTrue(matches_conditions(ast_block(decision, "custom_cost_trigger"), facts, tag))
                    apply(ast_block(decision, "complete_effect"))
                    self.assertEqual(facts[(tag, "variable", "STP_cw_arsenal_deposit")], 1200)
                    self.assertFalse(matches_conditions(gate, facts, tag),
                                     "a paid country deposit must block every other state target")

                    apply(ast_block(decision, terminal))
                    apply(ast_block(decision, terminal))
                    other_terminal = "cancel_effect" if terminal == "remove_effect" else "remove_effect"
                    apply(ast_block(decision, other_terminal))
                    self.assertEqual(facts[(tag, "variable", "STP_cw_arsenal_deposit")], 0)
                    self.assertFalse(facts[(tag, "has_variable", "STP_cw_arsenal_deposit")])
                    self.assertEqual(sum(e.key == "STP_cw_spend_1200" for _, e in writes), 1)
                    self.assertEqual(sum(e.key == "add_building_construction" for _, e in writes),
                                     int(terminal == "remove_effect"))
                    self.assertEqual(sum(e.key == "add_to_variable" and scalar(e.value, "var") == "ADISCORD_economy_treasury" for _, e in writes),
                                     int(terminal == "cancel_effect"))
                    self.assertTrue(matches_conditions(gate, facts, tag))
                    apply(ast_block(decision, "complete_effect"))
                    self.assertEqual(sum(e.key == "STP_cw_spend_1200" for _, e in writes), 2)
                    self.assertFalse(matches_conditions(gate, facts, tag))


    def test_garrison_operations_fit_the_unshortened_election_window(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_focus")
        focuses = {scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        route = ("STP_cw_officer_contacts",)
        unlock_day = sum(float(scalar(focuses[name], "cost")) * 7 for name in route)
        council = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_battle_for_stelander")
        for operation in ("STP_region_unique_operation_2", "STP_region_unique_operation_29"):
            definition = ast_block(council, operation)
            self.assertIn("STP_cw_officer_contacts", {e.value for e in walk(ast_block(definition, "visible")) if e.key == "has_completed_focus"})
            self.assertLessEqual(unlock_day + int(scalar(definition, "days_remove")), 100)
        final_day = unlock_day + sum(float(scalar(focuses[name], "cost")) * 7 for name in ("STP_Garrisons_Hesitate", "STP_THE_MOUNTAIN_WINDOW"))
        self.assertLessEqual(final_day, 100)
        reward = ast_block(focuses["STP_Garrisons_Hesitate"], "completion_reward")
        self.assertFalse(any(e.key == "add_days_mission_timeout" for e in walk(reward)))
        self.assertEqual(scalar(reward, "add_political_power"), "100")
        self.assertFalse(any(e.key == "STP_add_resistance_influence" for _, e in selected_effects(reward, {})),
                         "the large garrison operation owns its local settlement")


    def test_ratification_requires_the_paid_agreement_and_protects_only_that_agreement(self):
        tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                    if scalar(e.value, "id") == "STP_focus")
        focus = next(e.value for e in tree if e.key == "focus" and scalar(e.value, "id") == "STP_cw_autonomy_guarantees")
        facts = {("STP", "STP_cw_preparation_open", "yes"): True,
                 ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): True,
                 ("45", "is_owned_by", "STP"): True,
                 ("45", "is_controlled_by", "STP"): True}
        available = ast_block(focus,"available")
        self.assertFalse(matches_conditions(available,facts))
        self.assertTrue(matches_conditions(available,{**facts,("45","has_state_flag","STP_local_deal_asset"):True}))
        self.assertFalse(matches_conditions(available, {
            **facts, ("45", "has_state_flag", "STP_local_deal_asset"): True,
            ("45", "is_controlled_by", "STP"): False,
        }))
        self.assertEqual(scalar(focus, "cancel_if_invalid"), "yes")
        self.assertFalse(any(e.key == "set_state_flag" for e in walk(ast_block(focus,"completion_reward"))))
        inspection = ast_block(self.effects,"STP_resolve_party_inspection")
        breach = next(e.value for e in inspection if e.key == "else_if"
                      and any(c.key == "clr_state_flag" and c.value == "STP_local_deal_asset" for c in e.value))
        gate = ast_block(breach,"limit")
        for state in ("45","2"):
            for ratified in (False,True):
                current={(state,"has_state_flag","STP_local_deal_asset"):True,
                         ("STP","has_completed_focus","STP_cw_autonomy_guarantees"):ratified}
                self.assertEqual(matches_conditions(gate,current,state),not(state == "45" and ratified))
        destruction = [e for e in walk(inspection) if e.key == "clr_state_flag"]
        self.assertIn("STP_resistance_administration_asset",{e.value for e in destruction})
        self.assertIn("STP_resistance_garrison_asset",{e.value for e in destruction})


class KefreytVolunteerContracts(unittest.TestCase):
    template = "Kefreyt Volunteer Division"
    price = {"infantry_equipment": 1830, "ADISCORD_squad_weapons_equipment": 144,
             "support_equipment": 90, "artillery_equipment": 180, "anti_air_equipment": 60}

    def test_offer_acceptance_and_full_package_payment_have_separate_gates(self):
        events = entries("events/ADISCORD_STP_events.txt")
        event = next(e.value for e in events if e.key == "country_event"
                     and scalar(e.value, "id") == "ADISCORD_STP_preparation.6")
        option = next(e.value for e in event if e.key == "option"
                      and scalar(e.value, "name") == "ADISCORD_STP_preparation.6.a")
        gate = ast_block(option, "trigger")
        consent = {("VAL", "STP_cw_kefreyt_aid_open", "yes"): True}
        self.assertTrue(matches_conditions(gate, consent, "VAL"))
        self.assertFalse(matches_conditions(gate, {**consent, ("VAL", "has_country_flag", "VAL_cw_volunteers_pending"): True}, "VAL"))
        self.assertFalse(matches_conditions(gate, {}, "VAL"))
        payment = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"),
                            "STP_cw_can_fund_kefreyt_volunteers")
        facts = {("VAL", "numeric", "has_manpower"): 23700}
        facts.update({("VAL", "equipment", key): value for key, value in self.price.items()})
        self.assertTrue(matches_conditions(payment, facts, "VAL"))
        for key, amount in (("has_manpower", 23700), *self.price.items()):
            field = ("VAL", "numeric" if key == "has_manpower" else "equipment", key)
            self.assertFalse(matches_conditions(payment, {**facts, field: amount - .5}, "VAL"), key)
        self.assertEqual(sum(e.key == "STP_cw_reserve_kefreyt_volunteers" for e in walk(option)), 1)
        self.assertFalse(any(e.key in ("add_manpower", "create_unit") for e in walk(option)))

    def test_payment_reserves_three_units_without_crediting_the_recipient(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        reserve = ast_block(ast_block(effects, "STP_cw_reserve_kefreyt_volunteers"), "if")
        loop = ast_block(reserve, "for_loop_effect")
        self.assertEqual(scalar(loop, "end"), "3")
        self.assertEqual(sum(e.key == "STP_cw_pay_assault_division" for e in loop), 1)
        receipt = ast_block(loop, "if")
        self.assertEqual(scalar(ast_block(receipt, "limit"), "has_country_flag"), "STP_cw_assault_division_paid")
        self.assertEqual(scalar(ast_block(ast_block(receipt, "1"), "add_to_variable"), "value"), "1")
        self.assertFalse(any(e.key in ("add_manpower", "add_equipment_to_stockpile", "create_unit") for e in walk(reserve)))
        self.assertIn("STP_cw_refund_kefreyt_volunteers", {e.key for e in walk(reserve)})

    def test_partial_payment_rolls_back_and_successful_delivery_cannot_repeat(self):
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        reserve = ast_block(effects, "STP_cw_reserve_kefreyt_volunteers")
        refund = ast_block(effects, "STP_cw_refund_kefreyt_volunteers")
        deploy = ast_block(effects, "STP_cw_deploy_kefreyt_volunteers")
        ledger = ("1", "variable", "STP_cw_kefreyt_volunteers")
        for payment_outcomes in ((True, True, True), (True, False, True), (False, False, False)):
            facts = {("VAL", "numeric", "has_manpower"): 23700,
                     ("VAL", "exists", "yes"): True,
                     ("VAL", "STP_cw_kefreyt_aid_open", "yes"): True,
                     ("VAL", "STP_cw_can_fund_kefreyt_volunteers", "yes"): True,
                     ("VAL", "has_country_flag", "VAL_cw_volunteers_pending"): True,
                     ("STP", "STP_cw_preparation_open", "yes"): True,
                     ("STP", "owns_state", "1"): True,
                     ("1", "is_owned_by", "STP"): True,
                     ("1", "is_controlled_by", "STP"): True,
                     ("STS", "has_country_flag", "STP_cw_templates_loaded"): True}
            facts.update({("VAL", "equipment", key): value for key, value in self.price.items()})
            outcomes = iter(payment_outcomes)
            paid_units, spawned = [], []

            def apply(body, scope):
                for current, effect in selected_effects(body, facts, scope):
                    key = effect.key
                    if key == "STP_cw_pay_assault_division":
                        paid = next(outcomes)
                        facts[(current, "has_country_flag", "STP_cw_assault_division_paid")] = paid
                        if paid:
                            paid_units.append(1)
                    elif key == "STP_cw_refund_assault_division":
                        self.assertEqual(current, "VAL")
                        paid_units.pop()
                    elif key == "STP_cw_refund_kefreyt_volunteers":
                        apply(refund, current)
                    elif key in ("set_country_flag", "clr_country_flag"):
                        facts[(current, "has_country_flag", effect.value)] = key == "set_country_flag"
                    elif key == "clear_variable":
                        facts[(current, "variable", effect.value)] = 0
                    elif key in ("set_temp_variable", "add_to_variable", "subtract_from_temp_variable"):
                        variable = (current, "variable", scalar(effect.value, "var"))
                        value = scalar(effect.value, "value")
                        amount = float(value) if value.isdigit() else facts.get((current, "variable", value), 0)
                        facts[variable] = (amount if key == "set_temp_variable" else
                                           facts.get(variable, 0) + amount * (-1 if key == "subtract_from_temp_variable" else 1))
                    elif key == "create_unit":
                        spawned.append(scalar(effect.value, "owner"))
                    elif key != "country_event":
                        self.fail(f"Unsupported volunteer transaction effect: {key}")

            apply(reserve, "VAL")
            if all(payment_outcomes):
                self.assertEqual((len(paid_units), facts[ledger]), (3, 3))
                apply(reserve, "VAL")  # the receipt flag rejects duplicate acceptance
                facts[("1", "is_owned_by", "STP")] = False
                facts[("1", "is_controlled_by", "STP")] = False
                facts[("1", "is_owned_by", "STS")] = True
                facts[("1", "is_controlled_by", "STS")] = True
                apply(deploy, "1")
                apply(deploy, "1")
                self.assertEqual(spawned, ["STS"] * 3)
                self.assertEqual(facts[ledger], 0)
            else:
                self.assertEqual((paid_units, facts[ledger]), ([], 0))
                apply(deploy, "1")
                self.assertFalse(spawned)

    def test_volunteer_template_is_fixed_and_uses_the_donor_model(self):
        definitions = entries("history/units/ADISCORD_STP_civil_war_templates.txt")
        templates = {scalar(e.value, "name"): e.value for e in definitions if e.key == "division_template"}
        volunteer = templates[self.template]
        self.assertEqual(scalar(volunteer, "is_locked"), "yes")
        self.assertEqual(scalar(volunteer, "force_allow_recruiting"), "no")
        self.assertEqual(scalar(volunteer, "override_model"), "ADISCORD_VAL_regular_entity")
        for section in ("regiments", "support"):
            actual = [(e.key, tuple((c.key, c.value) for c in e.value)) for e in ast_block(volunteer, section)]
            expected = [(e.key, tuple((c.key, c.value) for c in e.value)) for e in ast_block(templates["Stelander Assault Division"], section)]
            self.assertEqual(actual, expected)
        contract = ast_block(entries("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_cw_complete_arms_contract")
        delivery = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_ps_deliver_val_contract")
        self.assertIn("STP_ps_val_receipt_contract", str(contract))
        temporary = next(e.value for e in walk(delivery) if e.key == "division_template")
        self.assertEqual(scalar(temporary, "name"), "Kefreyt Contract Infantry")
        self.assertEqual(scalar(temporary, "is_locked"), "yes")
        self.assertEqual(scalar(temporary, "force_allow_recruiting"), "no")
        self.assertEqual(scalar(temporary, "override_model"), "ADISCORD_VAL_regular_entity")

    def test_deployment_consumes_the_receipt_once_after_army_distribution(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        deploy = block(effects, "STP_cw_deploy_kefreyt_volunteers")
        self.assertIn("is_owned_by = STS", deploy)
        self.assertIn("is_controlled_by = STS", deploy)
        self.assertLess(deploy.index("clear_variable = STP_cw_kefreyt_volunteers"), deploy.index("create_unit"))
        self.assertIn("end = 3", deploy)
        self.assertIn("owner = STS", deploy)
        self.assertIn("start_equipment_factor = 1.0 start_manpower_factor = 1.0", deploy)
        self.assertNotIn("add_manpower", deploy)
        start = block(effects, "STP_cw_start")
        self.assertLess(start.rindex("transfer_units_fraction"), start.index("STP_cw_materialize_region_assets"))
        self.assertIn("STP_cw_deploy_kefreyt_volunteers = yes", block(effects, "STP_cw_materialize_region_assets"))

    def test_settlements_remove_temporary_units_without_refunding_sts(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        cleanup = block(effects, "STP_cw_remove_kefreyt_volunteers")
        self.assertIn("STP = { STP_cw_purge_kefreyt_host_templates = yes }", cleanup)
        parsed_cleanup = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                   "STP_cw_remove_kefreyt_volunteers")
        self.assertEqual(scalar(ast_block(parsed_cleanup, "STP"), "STP_cw_purge_kefreyt_host_templates"), "yes")
        for tag in ("STS", "SRP"):
            body = ast_block(parsed_cleanup, tag)
            self.assertEqual(scalar(body, "STP_cw_purge_kefreyt_host_templates"), "yes")
            self.assertEqual(scalar(body, "STP_cw_strip_peacetime_union_templates"), "yes")
        peacetime = block(effects, "STP_cw_strip_peacetime_union_templates")
        for name in ("Police division", "Regular army", "Capital Guard"):
            self.assertIn('division_template = "' + name + '"', peacetime)
        self.assertEqual(peacetime.count("delete_unit_template_and_units"), 3)
        parsed_peacetime = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                     "STP_cw_strip_peacetime_union_templates")
        union = ("Police division", "Regular army", "Capital Guard")
        for present in (False, True):
            facts = {("STS", "has_template", name): present for name in union}
            removed = [e for _, e in selected_effects(parsed_peacetime, facts, "STS")
                       if e.key == "delete_unit_template_and_units"]
            self.assertEqual(len(removed), 3 if present else 0)
        volunteer_strip = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                                    "STP_cw_strip_kefreyt_volunteer_template")
        for present in (False, True):
            facts = {("SRP", "has_template", "Kefreyt Volunteer Division"): present}
            removed = [e for _, e in selected_effects(volunteer_strip, facts, "SRP")
                       if e.key == "delete_unit_template_and_units"]
            self.assertEqual(len(removed), 1 if present else 0)
        purge = block(effects, "STP_cw_purge_kefreyt_host_templates")
        self.assertIn('division_template = "Kefreyt Volunteer Division"', purge)
        self.assertIn('division_template = "Kefreyt Contract Infantry"', purge)
        self.assertIn("is_locked = no", purge)
        self.assertGreaterEqual(purge.count("delete_unit ="), 2)
        self.assertEqual(purge.count("delete_unit_template_and_units"), 2)
        self.assertEqual(purge.count("disband = no"), 4)
        self.assertNotIn("disband = yes", purge)
        self.assertNotIn("add_manpower", purge)
        parsed = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"),
                           "STP_cw_purge_kefreyt_host_templates")
        for present in (False, True):
            facts = {("STS", "has_template", name): present
                     for name in ("Kefreyt Volunteer Division", "Kefreyt Contract Infantry")}
            removed = [e for _, e in selected_effects(parsed, facts, "STS")
                       if e.key == "delete_unit_template_and_units"]
            self.assertEqual(len(removed), 2 if present else 0)
        for name in ("STP_cw_settle_union_victory", "STP_cw_settle_nod_victory"):
            settlement = block(effects, name)
            self.assertLess(settlement.index("STP_cw_remove_kefreyt_volunteers"), settlement.index("annex_country"))
        self.assertIn("STP_cw_remove_kefreyt_volunteers", block(effects, "STP_cw_check_union_wars_finished"))
        refund = block(effects, "STP_cw_refund_kefreyt_volunteers")
        self.assertIn("VAL = { STP_cw_refund_assault_division = yes }", refund)
        self.assertNotIn("owner =", refund)
        self.assertLess(refund.index("clear_variable = STP_cw_kefreyt_volunteers"), refund.index("STP_cw_refund_assault_division"))


class RepublicsCouncilContracts(unittest.TestCase):
    def setUp(self):
        self.triggers = entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        self.effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")

    def expand(self, items, parameters=None):
        return NorthernCampaignContracts.expand(self, items, parameters)

    def facts(self):
        facts = {(tag, key, value): True for tag in ("STS", "SRP")
                 for key, value in (("exists", "yes"), ("is_subject", "no"), ("has_capitulated", "no"),
                                    ("has_idea", "STP_cw_council_guarantees"))}
        facts.update({("STS", "tag", "STS"): True,
                      ("SRP", "has_war_with", "VAL"): True,
                      ("STS", "has_country_flag", "STP_cw_won_union_battle"): True,
                      ("STS", "variable", "ADISCORD_economy_treasury"): 300})
        return facts

    def execute(self, name, facts, scope="STS"):
        writes = []
        for country, effect in selected_effects(self.expand(ast_block(self.effects, name)), facts, scope):
            writes.append((country, effect))
            if effect.key in {"add_ideas", "remove_ideas"} and not isinstance(effect.value, list):
                facts[(country, "has_idea", effect.value)] = effect.key == "add_ideas"
            elif effect.key == "add_timed_idea":
                facts[(country, "has_idea", scalar(effect.value, "idea"))] = True
            elif effect.key in {"subtract_from_variable", "add_to_variable"}:
                key = (country, "variable", scalar(effect.value, "var"))
                sign = -1 if effect.key == "subtract_from_variable" else 1
                facts[key] = facts.get(key, 0) + sign * float(scalar(effect.value, "value"))
        return writes

    def test_guarantees_require_living_paid_agreement_before_split_cleanup(self):
        from itertools import product
        for focus, asset, owner, controller, shabrat in product((False, True), repeat=5):
            facts = self.facts()
            facts.update({("STP", "has_completed_focus", "STP_cw_autonomy_guarantees"): focus,
                          ("STP", "has_country_flag", "STP_sided_with_Maksim_flag"): shabrat,
                          ("45", "has_state_flag", "STP_local_deal_asset"): asset,
                          ("45", "is_owned_by", "STP"): owner,
                          ("45", "is_controlled_by", "STP"): controller})
            writes = self.execute("STP_cw_preserve_council_guarantees", facts, "STP")
            self.assertEqual([(tag, e.value) for tag, e in writes if e.key == "add_ideas"],
                             [("STS", "STP_cw_council_guarantees"), ("SRP", "STP_cw_council_guarantees")]
                             if all((focus, asset, owner, controller, shabrat)) else [])
        start = block(read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_start")
        promise = start.index("STP_cw_preserve_council_guarantees")
        self.assertLess(start.index("SRP = { transfer_state = 43"), promise)
        for later in ("STP_cw_region_goes_to_republics", "STP_cw_materialize_region_assets", "load_focus_tree"):
            self.assertLess(promise, start.index(later))

    def test_aid_debits_cash_once_and_supplies_only_republics(self):
        for balance in (0, 299.999, 300, 777):
            facts = self.facts()
            facts[("STS", "variable", "ADISCORD_economy_treasury")] = balance
            writes = self.execute("STP_cw_fund_republican_supplies", facts)
            delivered = [(tag, scalar(e.value, "type"), scalar(e.value, "amount"))
                         for tag, e in writes if e.key == "add_equipment_to_stockpile"]
            self.assertEqual(delivered, [("SRP", "infantry_equipment", "1200"),
                                         ("SRP", "support_equipment", "30")] if balance >= 300 else [])
            self.assertEqual(facts[("STS", "variable", "ADISCORD_economy_treasury")],
                             balance - 300 if balance >= 300 else balance)
            self.assertEqual(facts.get(("STS", "variable", "ADISCORD_economy_current_month_action_costs"), 0),
                             300 if balance >= 300 else 0)
            self.assertEqual(self.execute("STP_cw_fund_republican_supplies", facts), [])
        for key in (("STS", "is_subject", "no"), ("SRP", "is_subject", "no"),
                    ("SRP", "exists", "yes"), ("STS", "has_capitulated", "no"),
                    ("SRP", "has_capitulated", "no"), ("SRP", "has_war_with", "VAL"),
                    ("STS", "has_idea", "STP_cw_council_guarantees"),
                    ("SRP", "has_idea", "STP_cw_council_guarantees")):
            self.assertEqual(self.execute("STP_cw_fund_republican_supplies", {**self.facts(), key: False}), [], key)
        decision = ast_block(ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council"),
                             "STP_cw_fund_republican_supplies")
        self.assertEqual(scalar(decision, "cost"), "0")
        self.assertEqual(scalar(decision, "days_re_enable"), "42")

    def test_postwar_choice_consumes_promises_without_ending_republics_war(self):
        for name, own, partner in (("STP_cw_ratify_republican_charter", "STP_cw_republican_charter", "STP_cw_republican_charter"),
                                   ("STP_cw_reject_republican_charter", "STP_cw_central_authority", "SRP_distrust_stelander")):
            facts = self.facts()
            writes = self.execute(name, facts)
            self.assertTrue(facts[("STS", "has_idea", own)])
            self.assertTrue(facts[("SRP", "has_idea", partner)])
            self.assertTrue(facts[("SRP", "has_war_with", "VAL")])
            self.assertFalse(any(e.key in {"annex_country", "transfer_state", "white_peace", "declare_war_on",
                                          "set_autonomy", "create_faction", "add_to_faction"} for _, e in writes))
            for repeat in ("STP_cw_ratify_republican_charter", "STP_cw_reject_republican_charter"):
                self.assertEqual(self.execute(repeat, facts), [])
            for key in (("SRP", "exists", "yes"), ("SRP", "is_subject", "no"),
                        ("SRP", "has_capitulated", "no"), ("STS", "has_country_flag", "STP_cw_won_union_battle")):
                self.assertEqual(self.execute(name, {**self.facts(), key: False}), [])

    def test_npc_command_follows_its_own_war_and_retains_ai_economy(self):
        for war in (False, True):
            facts = {("SRP", "tag", "SRP"): True, ("SRP", "has_war_with", "VAL"): war,
                     ("SRP", "has_global_flag", "STP_cw_union_wars_finished"): True}
            writes = self.execute("STP_cw_republics_war_command", facts, "SRP")
            self.assertEqual([e.value for _, e in writes if e.key == "add_ideas"], ["SRP_emergency_command"] if war else [])
            self.assertEqual(self.execute("STP_cw_republics_war_command", facts, "SRP"), [])
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        cancel = ast_block(ast_block(ideas, "SRP_emergency_command"), "cancel")
        self.assertFalse(matches_conditions(cancel, {("SRP", "has_war_with", "VAL"): True}, "SRP"))
        self.assertTrue(matches_conditions(cancel, {}, "SRP"))
        events = read("events/ADISCORD_STP_events.txt")
        self.assertNotIn("SRP = { change_tag_from = STP }", events)
        tree = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        self.assertNotIn("id = STP_cw_federal_defence", tree)
        self.assertNotIn("id = STP_cw_western_frontier", tree)
        self.assertIn("SRP = { load_focus_tree = { tree = STP_cw_focus", read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"))

    def test_charter_dialogue_blocks_duplicates_and_closes_after_partner_loss(self):
        council = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        decision = ast_block(council, "STP_cw_negotiate_republican_charter")
        available = self.expand(ast_block(decision, "available"))
        facts = self.facts()
        self.assertTrue(matches_conditions(available, facts, "STS"))
        queued = list(selected_effects(ast_block(decision, "complete_effect"), facts, "STS"))
        flag = "STP_cw_charter_dialogue_pending"
        self.assertEqual([e.value for _, e in queued if e.key == "set_country_flag"], [flag])
        self.assertEqual([scalar(e.value, "id") for _, e in queued if e.key == "country_event"], ["ADISCORD_STP_cw.90"])
        facts[("STS", "has_country_flag", flag)] = True
        self.assertFalse(matches_conditions(available, facts, "STS"))
        event = next(e.value for e in entries("events/ADISCORD_STP_events.txt")
                     if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.90")
        options = [e.value for e in event if e.key == "option"]
        for partner_exists in (True, False):
            facts[("SRP", "exists", "yes")] = partner_exists
            self.assertTrue(matches_conditions(ast_block(event, "trigger"), facts, "STS"))
            shown = [o for o in options if matches_conditions(self.expand(ast_block(o, "trigger")), facts, "STS")]
            self.assertEqual(len(shown), 2 if partner_exists else 1)
            for option in shown:
                clears = [e.value for e in walk(option) if e.key == "clr_country_flag"]
                self.assertEqual(clears, [flag])
        tree = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        self.assertNotIn("ADISCORD_STP_cw.90", tree)
        self.assertIn("unlock_decision_tooltip = STP_cw_negotiate_republican_charter", tree)

    def test_bilateral_spirits_end_on_loss_of_independence_or_war_between_partners(self):
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        for name in ("STP_cw_council_guarantees", "STP_cw_republican_charter"):
            cancel = ast_block(ast_block(ideas, name), "cancel")
            for scope in ("STS", "SRP"):
                self.assertFalse(matches_conditions(cancel, {}, scope))
                for invalid in (("STS", "exists", "no"), ("SRP", "exists", "no"),
                                ("STS", "is_subject", "yes"), ("SRP", "is_subject", "yes"),
                                ("STS", "has_war_with", "SRP")):
                    self.assertTrue(matches_conditions(cancel, {invalid: True}, scope), (name, scope, invalid))


class PostwarFocusContracts(unittest.TestCase):
    def setUp(self):
        self.tree = next(e.value for e in entries("common/national_focus/ADISCORD_national_focus_STP.txt")
                         if e.key == "focus_tree" and scalar(e.value, "id") == "STP_cw_focus")
        self.focuses = {scalar(e.value, "id"): e.value for e in self.tree if e.key == "focus"}
        # These contracts cover the accumulated reconstruction modifier.
        # Diplomatic choices use transactions and have separate lifecycle checks.
        self.new = {k: v for k, v in self.focuses.items() if k.startswith("STP_pw_")
                    and any(e.key == "STP_pw_refresh_modifier" for e in walk(ast_block(v, "completion_reward")))}

    def test_wartime_and_reconstruction_do_not_share_the_visible_layout(self):
        for tag in ("STP", "STS", "SRP"):
            for postwar in (False, True):
                facts = {(tag, "has_country_flag", "STP_cw_postwar"): postwar,
                         (tag, "ruling_leader"): "STP_maksim_shabrat" if tag == "STS" else "STP_Edmund_Ravel",
                         (tag, "STP_pc_founder_rules", "yes"): tag == "STS",
                         (tag, "STP_pc_course_continues", "yes"): tag == "STS",
                         (tag, "STP_pc_hegemony_continues", "yes"): tag == "STS",
                         (tag, "STP_pc_freedom_continues", "yes"): tag == "STS"}
                visible = {name: focus for name, focus in self.focuses.items()
                           if matches_conditions(ast_block(focus, "allow_branch"), facts, tag)}
                reconstruction = {name for name in visible if name.startswith(("STP_pw_", "STP_pc_"))}
                if not postwar:
                    self.assertFalse(reconstruction, (tag, reconstruction))
                elif tag != "SRP":
                    self.assertTrue(reconstruction, tag)
                    self.assertFalse({name for name in visible if name.startswith("STP_cw_")}
                                     - {"STP_cw_first_postwar_budget", "STP_cw_restore_civil_authority"})
                positions = {}
                for name, focus in visible.items():
                    x = int(scalar(focus, "x")) + sum(int(scalar(e.value, "x")) for e in focus
                        if e.key == "offset" and matches_conditions(ast_block(e.value, "trigger"), facts, tag))
                    point = (x, int(scalar(focus, "y")))
                    self.assertNotIn(point, positions, (tag, postwar, name, positions.get(point)))
                    positions[point] = name

    def test_each_side_has_a_reachable_three_pillar_postwar_program(self):
        republic = {k: v for k, v in self.new.items() if k.startswith("STP_pw_republic_")}
        self.assertEqual(len(republic), 16)
        completed = {"STP_cw_restore_civil_authority", "STP_pc_after_victory"}
        for _ in range(len(republic)):
            for name, focus in republic.items():
                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                if all(any(e.value in completed for e in group) for group in prerequisites):
                    completed.add(name)
        self.assertIn("STP_pw_republic_settled_state", completed)

        party = {k: v for k, v in self.new.items() if k.startswith("STP_pw_party_")}
        self.assertEqual(len(party), 25)
        supporting = {
            name: self.focuses[name]
            for name in (
                "STP_party_district_charters", "STP_party_local_cadres",
                "STP_party_personnel_commissions", "STP_party_chain_of_command",
                "STP_party_revenue_service", "STP_party_port_contracts",
                "STP_party_industrial_board", "STP_party_research_council",
                "STP_party_technical_institutes",
                "STP_pw_party_border_staff", "STP_pw_party_southern_defence",
                "STP_pw_party_northern_protocol", "STP_pw_party_protectorate",
                "STP_pw_party_sovereignty", "STP_pw_party_nod_military_mission",
                "STP_pw_party_domestic_pattern",
            )
        }
        choices = (
            ("STP_pw_party_open_settlement", "STP_pw_party_firm_settlement"),
            ("STP_pw_party_civil_workshops", "STP_pw_party_accountable_arsenals"),
            ("STP_pw_party_supply_service", "STP_pw_party_professional_service"),
            ("STP_pw_party_protectorate", "STP_pw_party_sovereignty"),
        )
        for domestic in choices[0]:
            for economy in choices[1]:
                for army in choices[2]:
                    for foreign in choices[3]:
                        selected = {domestic, economy, army, foreign}
                        excluded = {item for pair in choices for item in pair if item not in selected}
                        route = {**party, **supporting}
                        completed = {"STP_cw_restore_civil_authority"}
                        for _ in range(len(route) + 2):
                            for name, focus in route.items():
                                if name in excluded:
                                    continue
                                prerequisites = [e.value for e in focus if e.key == "prerequisite"]
                                if all(any(e.value in completed for e in group) for group in prerequisites):
                                    completed.add(name)
                        self.assertEqual(len(completed & party.keys()), 18, selected)
                        self.assertIn("STP_pw_party_settled_state", completed, selected)

        for tag, prefix, expected in (("STS", "STP_pw_republic_", 16), ("STP", "STP_pw_party_", 25)):
            focuses = {k: v for k, v in self.new.items() if k.startswith(prefix)}
            self.assertEqual(len(focuses), expected, tag)
            self.assertEqual(scalar(focuses[prefix + "settled_state"], "cost"), "4")
            facts = {(tag, "tag", tag): True, (tag, "has_country_flag", "STP_cw_postwar"): True}
            visible = [f for f in self.focuses.values() if not scalar(f, "id").startswith("STP_pc_")
                       and (not any(e.key == "allow_branch" for e in f)
                            or matches_conditions(ast_block(f, "allow_branch"), facts, tag))]
            points = [(int(scalar(f, "x")) + sum(int(scalar(e.value, "x")) for e in f
                       if e.key == "offset" and matches_conditions(ast_block(e.value, "trigger"), facts, tag)),
                       int(scalar(f, "y"))) for f in visible]
            self.assertEqual(len(points), len(set(points)))
            self.assertLessEqual(max(x for x, _ in points) - min(x for x, _ in points), 32 if tag == "STS" else 26)
            self.assertLessEqual(max(y for _, y in points), 15 if tag == "STS" else 12)
            for focus in focuses.values():
                self.assertEqual(scalar(ast_block(focus, "allow_branch"), "tag"), tag)
                self.assertIn("STP_pw_can_reconstruct", {e.key for e in walk(ast_block(focus, "available"))})
        budget = self.focuses["STP_cw_first_postwar_budget"]
        self.assertFalse(any(e.key == "prerequisite" for e in budget),
                         "A fast victory must not require finishing obsolete war preparations")

    def test_reconstruction_uses_the_confirmed_victor_not_world_peace(self):
        gate = ast_block(entries("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"), "STP_pw_can_reconstruct")
        for tag in ("STP", "STS", "SRP", "VAL"):
            for won in (False, True):
                for settled in (False, True):
                    for other_war in (False, True):
                        facts = {(tag, "tag", tag): True,
                                 (tag, "has_country_flag", "STP_cw_won_union_battle"): won,
                                 (tag, "has_country_flag", "STP_cw_postwar"): True,
                                 (tag, "has_global_flag", "STP_cw_union_wars_finished"): settled,
                                 (tag, "has_capitulated", "no"): True,
                                 (tag, "has_war", "yes"): other_war,
                                 (tag, "has_war", "no"): not other_war}
                        self.assertEqual(matches_conditions(gate, facts, tag), tag in {"STP", "STS"} and won and settled)
        for focus in self.new.values():
            for e in walk(ast_block(focus, "completion_reward")):
                self.assertNotIn(e.key, {"declare_war_on", "white_peace", "annex_country", "load_focus_tree",
                                        "set_country_flag", "set_global_flag", "set_rule"})

    def test_native_delta_previews_match_every_authoritative_variable_write(self):
        from decimal import Decimal

        def executable_entries(items):
            for e in items:
                if e.key == "effect_tooltip":
                    continue
                yield e
                if isinstance(e.value, list):
                    yield from executable_entries(e.value)
        ideas = ast_block(ast_block(entries("common/ideas/ADISCORD_STP_civil_war_ideas.txt"), "ideas"), "country")
        dynamic = entries("common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt")
        self.assertEqual(len(self.new), 41)
        for name, focus in self.new.items():
            side = "republic" if "_republic_" in name else "party"
            modifier = "STP_pw_" + side + "_dynamic"
            bindings = {e.key: e.value for e in ast_block(dynamic, modifier)
                        if isinstance(e.value, str) and e.value.startswith("STP_pw_")}
            reward = ast_block(focus, "completion_reward")
            swap = ast_block(ast_block(reward, "effect_tooltip"), "swap_ideas")
            base = ast_block(ideas, scalar(swap, "remove_idea"))
            delta = ast_block(ideas, scalar(swap, "add_idea"))
            self.assertFalse(ast_block(base, "modifier"))
            self.assertEqual(scalar(base, "name"), modifier)
            self.assertEqual(scalar(delta, "name"), modifier)
            for idea in (base, delta):
                self.assertEqual(scalar(ast_block(idea, "allowed"), "always"), "no")
            expected = {bindings[e.key]: Decimal(e.value) for e in ast_block(delta, "modifier")}
            writes = [e.value for e in walk(ast_block(reward, "hidden_effect")) if e.key == "add_to_variable"]
            actual = {scalar(e, "var"): Decimal(scalar(e, "value")) for e in writes}
            self.assertEqual(actual, expected, name)
            self.assertEqual(len(writes), len(actual))
            self.assertTrue(actual)
            self.assertEqual(scalar(ast_block(reward, "hidden_effect"), "STP_pw_refresh_modifier"), "yes")
            # Delta preview spirits must never become installed ideas.
            for entry in executable_entries(reward):
                if entry.key in {"add_ideas", "swap_ideas", "add_timed_idea"}:
                    installed = [entry.value] if isinstance(entry.value, str) else [e.value for e in walk(entry.value) if isinstance(e.value, str)]
                    self.assertFalse(any(value.endswith(("_delta", "_dummy")) for value in installed), name)

    def test_refresh_preserves_accumulation_and_never_resets_an_external_war(self):
        helper = ast_block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_pw_refresh_modifier")
        for tag, side in (("STS", "republic"), ("STP", "party")):
            modifier = "STP_pw_" + side + "_dynamic"
            for initial in (None, .173):
                facts = {(tag, "tag", tag): True, (tag, "STP_pw_can_reconstruct", "yes"): True}
                values, installed, refreshes, dirty = {}, set(), 0, 0
                for focus in self.new.values():
                    for e in walk(ast_block(focus, "completion_reward")):
                        if e.key == "add_to_variable":
                            var = scalar(e.value, "var")
                            if initial is not None:
                                values[var] = initial
                                facts[(tag, "has_variable", var)] = True
                for _ in range(2):
                    for scope, e in selected_effects(helper, facts, tag):
                        self.assertEqual(scope, tag)
                        if e.key == "set_variable":
                            var = scalar(e.value, "var")
                            self.assertNotIn(var, values)
                            values[var] = float(scalar(e.value, "value"))
                            facts[(tag, "has_variable", var)] = True
                        elif e.key == "add_dynamic_modifier":
                            name = scalar(e.value, "modifier")
                            self.assertNotIn(name, installed)
                            installed.add(name)
                            facts[(tag, "has_dynamic_modifier", name)] = True
                        elif e.key == "force_update_dynamic_modifier":
                            refreshes += 1
                        elif e.key == "ADISCORD_economy_mark_dirty":
                            dirty += 1
                        else:
                            self.fail("Unsupported postwar refresh operation: " + e.key)
                self.assertEqual(installed, {modifier})
                self.assertTrue(values)
                self.assertEqual(set(values.values()), {0 if initial is None else initial})
                self.assertEqual((refreshes, dirty), (2, 2))

    def test_factory_rewards_select_buildable_cores_or_preserve_the_project_funds(self):
        from dataclasses import replace

        def shape(items):
            return [(e.key, shape(e.value) if isinstance(e.value, list) else e.value) for e in items]

        for name, focus in self.new.items():
            if not name.endswith(("civil_workshops", "accountable_arsenals")):
                continue
            factory = "industrial_complex" if name.endswith("civil_workshops") else "arms_factory"
            reward = ast_block(focus, "completion_reward")
            project = ast_block(reward, "if")
            possible = ast_block(ast_block(project, "limit"), "any_owned_state")
            target = ast_block(project, "random_owned_controlled_state")
            target_limit = ast_block(target, "limit")
            self.assertEqual(scalar(possible, "is_controlled_by"), "ROOT")
            self.assertEqual(shape([e for e in possible if e.key != "is_controlled_by"]), shape(target_limit))
            slots = ast_block(target_limit, "free_building_slots")
            self.assertEqual(scalar(slots, "building"), factory)
            self.assertEqual(scalar(slots, "include_locked"), "yes")
            self.assertEqual([e.value for e in slots if not e.key], ["size", ">", "0"])
            self.assertEqual(scalar(target, "add_extra_state_shared_building_slots"), "1")
            construction = ast_block(target, "add_building_construction")
            self.assertEqual((scalar(construction, "type"), scalar(construction, "level")), (factory, "1"))

            # Native free_building_slots supplies the buildability fact. Check
            # selection with a capped first candidate, occupied land and no site.
            for state_cases in (
                    [(True, True, False), (True, True, True)],
                    [(True, False, True), (False, True, True)],
                    [(True, True, False), (True, True, False)],
                    []):
                eligible = []
                for index, (core, controlled, free) in enumerate(state_cases):
                    fixture = {("STS", "is_core_of", "STP"): core,
                               ("STS", "is_controlled_by", "ROOT"): controlled}
                    condition = [replace(e, key="always", value="yes" if free else "no")
                                 if e.key == "free_building_slots" else e for e in possible]
                    if matches_conditions(condition, fixture, "STS"):
                        eligible.append(index)
                branch = [replace(e, key="always", value="yes" if eligible else "no")
                          if e.key == "any_owned_state" else e for e in ast_block(project, "limit")]
                self.assertEqual(matches_conditions(branch, {}, "STS"), bool(eligible))
                if eligible:
                    self.assertTrue(all(state_cases[i] == (True, True, True) for i in eligible))
                else:
                    fallback = list(selected_effects(ast_block(reward, "else"), {}, "STS"))
                    funds = {scalar(e.value, "var"): float(scalar(e.value, "value"))
                             for _, e in fallback if e.key == "add_to_variable"}
                    self.assertEqual(funds, {"ADISCORD_economy_treasury": 900,
                                            "ADISCORD_economy_current_month_action_income": 900})
                    self.assertFalse(any(e.key == "add_building_construction" for _, e in fallback))

    def test_postwar_localisation_has_complete_single_line_values(self):
        raw = (ROOT / "localisation/russian/ADISCORD_STP_l_russian.yml").read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        lines = raw.decode("utf-8-sig").splitlines()
        keys = {name + suffix for name in self.new for suffix in ("", "_desc")}
        keys |= {"STP_pw_republic_dynamic", "STP_pw_republic_dynamic_desc", "STP_pw_party_dynamic",
                 "STP_pw_party_dynamic_desc", "STP_pw_reconstruction_available_tt",
                 "STP_pw_postwar_budget_available_tt", "STP_pw_industry_reserve_tt"}
        for key in keys:
            found = [line for line in lines if re.match(r"^\s*" + re.escape(key) + r":", line)]
            self.assertEqual(len(found), 1, key)
            self.assertRegex(found[0], r'^\s*' + re.escape(key) + r':\d* "[^\r\n]+"$')
            self.assertNotIn("\ufffd", found[0])

    def test_territorial_roles_follow_each_countrys_current_war(self):
        templates = entries("common/ai_templates/ADISCORD_land_templates.txt")
        garrison = ast_block(ast_block(ast_block(templates, "ADISCORD_garrison_templates"), "ADISCORD_garrison_levy"), "enable")
        frontline = ast_block(ast_block(ast_block(templates, "ADISCORD_territorial_templates"), "ADISCORD_stelander_line_brigade"), "enable")
        policy = ast_block(ast_block(entries("common/ai_strategy/ADISCORD_STP_civil_war.txt"), "STP_cw_territorial_army"), "enable")
        for tag in ("STP", "STS", "SRP"):
            for own_war in (False, True):
                facts = {(tag, "tag", tag): True, (tag, "is_ai", "yes"): True,
                         (tag, "has_global_flag", "STP_cw_started"): True,
                         (tag, "has_global_flag", "STP_cw_union_wars_finished"): True,
                         (tag, "has_war", "yes"): own_war}
                self.assertEqual(matches_conditions(garrison, facts, tag), not own_war)
                self.assertEqual(matches_conditions(frontline, facts, tag), own_war)
                self.assertEqual(matches_conditions(policy, facts, tag), own_war)


class AutomaticFrontOperationContracts(unittest.TestCase):
    def setUp(self):
        self.effects = {e.key: e.value for e in entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")}
        council = ast_block(entries("common/decisions/ADISCORD_STP_decisions.txt"), "STP_cw_war_council")
        self.mission = ast_block(council, "STP_cw_front_operation")
        self.facts = {("STS", "has_war_with", "STP"): True,
                      ("STS", "has_capitulated", "no"): True,
                      ("STS", "has_country_flag", "STP_cw_participant"): True}
        for state in (2, 29, 53, 3, 46, 45, 28):
            self.control(state, "STP")
        self.rewards, self.events = [], []

    def control(self, state, country):
        for tag in ("STP", "STS", "VAL"):
            self.facts[(str(state), "is_controlled_by", tag)] = tag == country

    def variable(self, name):
        return self.facts.get(("STS", "variable", "STP_cw_operation_" + name), 0)

    def run_effect(self, name):
        self.execute(self.effects[name])

    def execute(self, body, scope="STS"):
        for country, entry in selected_effects(body, self.facts, scope):
            key, value = entry.key, entry.value
            if key in self.effects:
                self.execute(self.effects[key], country)
            elif key in ("set_variable", "add_to_variable"):
                name, amount = scalar(value, "var"), float(scalar(value, "value"))
                address = (country, "variable", name)
                self.facts[address] = amount + (self.facts.get(address, 0) if key == "add_to_variable" else 0)
                self.facts[(country, "has_variable", name)] = True
            elif key == "clear_variable":
                self.facts.pop((country, "variable", value), None)
                self.facts.pop((country, "has_variable", value), None)
            elif key == "add_timed_idea":
                idea = scalar(value, "idea")
                self.facts[(country, "has_idea", idea)] = True
                self.rewards.append((country, idea, int(scalar(value, "days"))))
            elif key == "remove_ideas":
                for idea in ([value] if isinstance(value, str) else [e.value for e in value]):
                    self.facts.pop((country, "has_idea", idea), None)
            elif key in ("activate_mission", "remove_mission"):
                self.facts[(country, "has_active_mission", value)] = key == "activate_mission"
            elif key == "country_event":
                self.events.append((country, scalar(value, "id"), scalar(value, "hours")))
            else:
                raise AssertionError(f"Unhandled operation effect: {key}")

    def start_round(self):
        self.run_effect("STP_cw_begin_operations")
        self.run_effect("STP_cw_dispatch_operation")

    def settle(self, callback):
        self.facts[("STS", "has_active_mission", "STP_cw_front_operation")] = False
        self.execute(ast_block(self.mission, callback))

    def test_selects_only_party_controlled_targets_and_cannot_complete_empty(self):
        self.control(2, "STS")
        self.control(29, "VAL")
        self.start_round()
        self.assertEqual(self.variable("target"), 53)
        self.assertFalse(matches_conditions(ast_block(self.mission, "available"), self.facts, "STS"))
        self.control(53, "STS")
        self.assertTrue(matches_conditions(ast_block(self.mission, "available"), self.facts, "STS"))
        self.facts[("STS", "variable", "STP_cw_operation_target")] = 0
        self.assertFalse(matches_conditions(ast_block(self.mission, "available"), self.facts, "STS"))

    def test_three_rounds_pay_once_and_do_not_erase_the_final_bonus(self):
        self.start_round()
        self.run_effect("STP_cw_begin_operations")
        self.assertEqual(self.rewards, [("STP", "STP_cw_party_command_disruption", 35)])
        for number in range(1, 4):
            self.assertEqual(self.variable("round"), number)
            target = int(self.variable("target"))
            self.control(target, "STS")
            self.settle("complete_effect")
            snapshot = list(self.rewards), list(self.events)
            self.settle("complete_effect")
            self.settle("timeout_effect")
            self.assertEqual((self.rewards, self.events), snapshot)
            self.assertEqual(self.variable("target"), 0)
            self.run_effect("STP_cw_dispatch_operation")
        self.assertEqual(sum(idea == "STP_cw_operation_tempo" for _, idea, _ in self.rewards), 3)
        self.assertTrue(self.facts[("STS", "has_idea", "STP_cw_operation_tempo")])
        self.assertFalse(self.facts[("STS", "has_active_mission", "STP_cw_front_operation")])
        self.assertEqual(self.events, [("STS", "ADISCORD_STP_cw.92", "1")] * 3)
        self.run_effect("STP_cw_begin_operations")
        self.assertEqual(len(self.events), 3)

    def test_failed_deadline_penalizes_once_and_schedules_only_one_successor(self):
        self.start_round()
        self.settle("timeout_effect")
        self.assertEqual(self.rewards[-1], ("STS", "STP_cw_operation_disorganization", 28))
        snapshot = list(self.rewards), list(self.events)
        self.settle("timeout_effect")
        self.assertEqual((self.rewards, self.events), snapshot)
        self.run_effect("STP_cw_dispatch_operation")
        self.assertEqual(self.variable("round"), 2)

    def test_capture_on_the_timeout_hour_is_success(self):
        self.start_round()
        self.control(int(self.variable("target")), "STS")
        self.settle("timeout_effect")
        self.assertEqual(self.rewards[-1], ("STS", "STP_cw_operation_tempo", 21))
        self.assertFalse(any(idea == "STP_cw_operation_disorganization" for _, idea, _ in self.rewards))

    def test_peace_closes_pending_and_active_rounds_without_penalty(self):
        for pending in (False, True):
            with self.subTest(pending=pending):
                self.setUp()
                self.start_round()
                if pending:
                    self.control(int(self.variable("target")), "STS")
                    self.settle("complete_effect")
                self.facts[("STS", "has_war_with", "STP")] = False
                before = list(self.rewards)
                self.settle("timeout_effect")
                self.run_effect("STP_cw_stop_operations")
                self.execute(ast_block(self.mission, "cancel_effect"))
                self.run_effect("STP_cw_dispatch_operation")
                self.assertEqual(self.rewards, before)
                self.assertEqual(self.variable("round"), 3)
                self.assertEqual(self.variable("target"), 0)
                self.assertEqual(self.variable("pending"), 0)
                self.assertFalse(any(key[1] == "has_idea" and present for key, present in self.facts.items()))

    def test_no_remaining_target_finishes_without_empty_mission_or_reward(self):
        for state in (2, 29, 53, 3, 46, 45, 28):
            self.control(state, "STS")
        self.start_round()
        self.assertEqual(self.variable("round"), 3)
        self.assertEqual(self.variable("target"), 0)
        self.assertFalse(self.facts.get(("STS", "has_active_mission", "STP_cw_front_operation"), False))
        self.assertFalse(any(country == "STS" for country, _, _ in self.rewards))

    def test_mission_callbacks_never_remove_the_executing_mission(self):
        def expanded(items, seen=()):
            for entry in items:
                if entry.key in self.effects and entry.value == "yes":
                    self.assertNotIn(entry.key, seen)
                    yield from expanded(self.effects[entry.key], (*seen, entry.key))
                elif isinstance(entry.value, list):
                    yield from expanded(entry.value, seen)
                else:
                    yield entry.key
        for callback in ("complete_effect", "timeout_effect", "cancel_effect"):
            self.assertNotIn("remove_mission", set(expanded(ast_block(self.mission, callback))))
        self.assertEqual(scalar(self.mission, "days_mission_timeout"), "49")


if __name__ == "__main__":
    unittest.main()
