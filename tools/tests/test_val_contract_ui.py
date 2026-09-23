from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block {name}")
    start = match.start()
    brace = text.find("{", match.start(), match.end())
    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unclosed block {name}")


class TestValContractUi(unittest.TestCase):
    def test_contract_state_is_visible_and_reports_live_authority(self) -> None:
        dynamic = read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt")
        contract_state = named_block(dynamic, "VAL_contract_state")
        self.assertIn("icon = GFX_idea_VAL_contract_state", contract_state)

        on_actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup = named_block(on_actions, "on_startup")
        weekly = named_block(on_actions, "on_weekly_VAL")
        self.assertEqual(startup.count("VAL_initialize_contract_authority = yes"), 1)
        self.assertNotIn("NOT = { has_dynamic_modifier = { modifier = VAL_contract_state } }", startup)
        self.assertIn("has_dynamic_modifier = { modifier = VAL_contract_state }", weekly)
        self.assertIn("VAL_initialize_contract_authority = yes", weekly)

        history = read("history/countries/VAL - ValeraLand.txt")
        self.assertNotIn("VAL_mercenary_state", history)

        english = read("localisation/english/ADISCORD_VAL_decisions_l_english.yml")
        russian = read("localisation/russian/ADISCORD_VAL_decisions_l_russian.yml")
        self.assertIn('VAL_contract_state: "$VAL_mercenary_state$"', english)
        self.assertIn('VAL_contract_state: "$VAL_mercenary_state$"', russian)
        for localisation in (english, russian):
            self.assertIn("[?VAL_contract_authority|0]/100", localisation)
            self.assertIn("[VALGetContractAuthorityBand]", localisation)

    def test_supply_crisis_is_named_in_the_visible_dynamic_spirit(self):
        for language, supply_name in (("russian", "разрыв поставок"), ("english", "Disrupted Supplies")):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            label = re.search(r'^ VAL_economic_collapse:[^\n]*', text, re.M).group()
            self.assertIn(supply_name, label)
            self.assertRegex(text, r'VAL_vorkerland_contract_disruptions_desc:[^\n]*"\$VAL_economic_collapse_desc\$"')
            self.assertIn("[?VAL_economic_recovery_steps|0]/9", text)

    def test_authority_labels_match_modifier_bands(self) -> None:
        scripted = read("common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt")
        band = named_block(scripted, "defined_text")
        marker = scripted.index("name = VALGetContractAuthorityBand")
        start = scripted.rfind("defined_text", 0, marker)
        authority_band = named_block(scripted[start:], "defined_text")

        expected = (
            ("90", "VAL_CONTRACT_AUTHORITY_DOMINANT"),
            ("75", "VAL_CONTRACT_AUTHORITY_CENTRALIZED"),
            ("50", "VAL_CONTRACT_AUTHORITY_COHERENT"),
            ("25", "VAL_CONTRACT_AUTHORITY_BROKERED"),
        )
        for value, key in expected:
            self.assertIn(f"value = {value} compare = greater_than_or_equals", authority_band)
            self.assertIn(f"localization_key = {key}", authority_band)
        self.assertIn("localization_key = VAL_CONTRACT_AUTHORITY_FRAGMENTED", authority_band)

    def test_decision_categories_are_consolidated_without_losing_decisions(self) -> None:
        categories = read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")

        for current in ("VAL_contract_management", "VAL_postwar_administration"):
            self.assertIn(f"{current} = {{", categories)
            self.assertIn(f"{current} = {{", decisions)

        for obsolete in (
            "VAL_propaganda_campaigns",
            "VAL_contract_obligations",
            "VAL_regional_integration",
            "VAL_commonwealth_formation",
        ):
            self.assertNotRegex(categories, rf"(?m)^\s*{obsolete}\s*=\s*\{{")
            self.assertNotRegex(decisions, rf"(?m)^\s*{obsolete}\s*=\s*\{{")

        contract = named_block(decisions, "VAL_contract_management")
        for decision in (
            "VAL_campaign_rifles_and_bread",
            "VAL_campaign_contracts_feed_families",
            "VAL_campaign_no_promise_without_payment",
            "VAL_campaign_the_mine_was_stolen",
            "VAL_quarterly_contract_deadline",
            "VAL_pay_quarterly_contract_norm",
        ):
            self.assertIn(f"{decision} = {{", contract)

        postwar = named_block(decisions, "VAL_postwar_administration")
        for decision in ("VAL_nationalise_region", "VAL_proclaim_commonwealth"):
            self.assertIn(f"{decision} = {{", postwar)
        self.assertNotIn("VAL_establish_regional_administration =", postwar)

    def test_sparse_contract_unlock_focuses_are_short_or_have_immediate_value(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for focus_id in (
            "VAL_Foreign_Broker_Licences",
            "VAL_Northern_Clearing_House",
            "VAL_Contingency_Ledgers",
            "VAL_econ_automation",
            "VAL_econ_logistics",
            "VAL_econ_computing",
            "VAL_Resource_War_Contracts",
            "VAL_frontier_return_irem",
        ):
            block = named_block(focuses[focuses.index(f"id = {focus_id}") - 80:], "focus")
            cost = re.search(r"(?m)^\s*cost\s*=\s*([0-9.]+)", block)
            self.assertIsNotNone(cost, focus_id)
            self.assertLessEqual(float(cost.group(1)), 3, focus_id)

        licences = focuses[focuses.index("id = VAL_Foreign_Broker_Licences"):]
        self.assertIn("add_political_power = 25", licences[:1800])
        self.assertIn("VAL_change_contract_authority = yes", licences[:1800])

        clearing = focuses[focuses.index("id = VAL_Northern_Clearing_House"):]
        self.assertIn("ADISCORD_economy_receive_15 = yes", clearing[:1200])

        advisers = focuses[focuses.index("id = VAL_Contingency_Ledgers"):]
        self.assertIn("add_command_power = 15", advisers[:1200])

    def test_contract_authority_improves_political_cashflow(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = named_block(effects, "VAL_refresh_contract_modifier")
        base_assignments = re.findall(r"set_variable = \{ var = VAL_contract_pp_gain value = (-?\d+(?:\.\d+)?) \}", refresh)
        self.assertGreaterEqual(len(base_assignments), 5)
        self.assertEqual(base_assignments[:5], ["-0.05", "0.05", "0.10", "0.15", "0.20"])

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        chancery = named_block(decisions, "VAL_fund_contract_chancery")
        self.assertIn("ADISCORD_economy_can_spend_100 = yes", chancery)
        self.assertIn("ADISCORD_economy_spend_100 = yes", chancery)
        self.assertIn("add_political_power = 75", chancery)
        self.assertIn("days_re_enable = 90", chancery)

    def test_nationalisation_is_a_repeatable_adjacent_core_chain(self) -> None:
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        nationalise = named_block(decisions, "VAL_nationalise_region")
        for token in (
            "state_target = yes",
            "any_neighbor_state = {",
            "is_core_of = ROOT",
            "is_owned_by = ROOT",
            "is_controlled_by = ROOT",
            "NOT = { is_core_of = ROOT }",
            "set_country_flag = VAL_regional_integration_active",
            "add_core_of = ROOT",
            "fire_only_once = no",
        ):
            self.assertIn(token, nationalise)
        self.assertNotIn("compliance", nationalise)
        self.assertNotIn("resistance", nationalise)


class TestValPropagandaRewards(unittest.TestCase):
    campaigns = (
        "VAL_campaign_rifles_and_bread",
        "VAL_campaign_contracts_feed_families",
        "VAL_campaign_no_promise_without_payment",
        "VAL_campaign_the_mine_was_stolen",
    )

    def focus(self, focus_id: str) -> str:
        text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        matches = list(re.finditer(rf"\bid\s*=\s*{re.escape(focus_id)}\b", text))
        self.assertEqual(len(matches), 1, focus_id)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", text[:matches[0].start()]))
        self.assertTrue(starts, focus_id)
        return named_block(text[starts[-1].start():], "focus")

    def decision(self, decision_id: str) -> str:
        category = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_contract_management")
        return named_block(category, decision_id)

    def number(self, text: str, key: str) -> float:
        values = re.findall(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)\s*$", text)
        self.assertEqual(len(values), 1, key)
        return float(values[0])

    def test_ministry_funds_any_initial_campaign_and_lists_its_unlocks(self) -> None:
        reward = named_block(self.focus("VAL_Ministry_Of_Contract_Memory"), "completion_reward")
        self.assertRegex(reward, r"(?m)^\t{3}add_political_power = 50$")
        funds = self.number(reward, "add_political_power")
        for decision_id in self.campaigns[:3]:
            with self.subTest(decision=decision_id):
                from tools.validators.validate_adiscord_division_templates import parse_clausewitz
                rewards = parse_clausewitz(reward)[0].value
                unlocked = [entry.value if isinstance(entry.value, str)
                            else next(child.value for child in entry.value if child.key == "decision")
                            for entry in rewards if entry.key == "unlock_decision_tooltip"]
                self.assertEqual(unlocked.count(decision_id), 1)
                self.assertGreaterEqual(funds, self.number(self.decision(decision_id), "cost"))
        self.assertIn("custom_effect_tooltip = VAL_campaign_mine_unlock_tt", reward)
        self.assertNotIn("unlock_decision_tooltip = VAL_campaign_the_mine_was_stolen", reward)

    def test_slot_rewards_hide_bookkeeping_and_preserve_one_time_grants(self) -> None:
        for focus_id, flag, tooltip in (
            ("VAL_Ministry_Of_Contract_Memory", "VAL_propaganda_slot_granted", "VAL_campaign_slot_granted_tt"),
            ("VAL_Two_Concurrent_Narratives", "VAL_second_propaganda_slot_granted", "VAL_campaign_second_slot_tt"),
        ):
            with self.subTest(focus=focus_id):
                reward = named_block(self.focus(focus_id), "completion_reward")
                self.assertIn(f"custom_effect_tooltip = {tooltip}", reward)
                hidden = named_block(reward, "hidden_effect")
                guarded = named_block(hidden, "if")
                self.assertIn(f"NOT = {{ has_country_flag = {flag} }}", named_block(guarded, "limit"))
                self.assertEqual(guarded.count("ADISCORD_campaign_slot_grant = yes"), 1)
                self.assertEqual(guarded.count(f"set_country_flag = {flag}"), 1)
                visible = reward.replace(hidden, "")
                self.assertNotIn("ADISCORD_campaign_slot_grant", visible)
                self.assertNotIn("set_country_flag", visible)
        self.assertLessEqual(self.number(self.focus("VAL_Two_Concurrent_Narratives"), "cost"), self.number(self.focus("VAL_Ministry_Of_Contract_Memory"), "cost"))

    def test_campaign_unlock_is_independent_of_quarterly_category_visibility(self) -> None:
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_contract_management")
        alternatives = named_block(named_block(category, "visible"), "OR")
        self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", alternatives)
        self.assertIn("has_completed_focus = VAL_Quarterly_Contract_Norm", alternatives)
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                visible = named_block(decision, "visible")
                self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", visible)
                self.assertNotIn("OR =", visible)
                self.assertNotIn("ADISCORD_has_campaign_slot", visible)
                available = named_block(decision, "available")
                self.assertIn("tooltip = VAL_campaign_slot_available_tt", available)
                self.assertIn("ADISCORD_has_campaign_slot = yes", available)
        mine = named_block(self.decision(self.campaigns[-1]), "visible")
        self.assertIn("has_country_flag = VAL_westerholm_metal_lost", mine)

    def test_political_campaign_has_a_positive_base_return_and_refreshes_income(self) -> None:
        decision = self.decision("VAL_campaign_no_promise_without_payment")
        cost = self.number(decision, "cost")
        days = self.number(decision, "days_remove")
        modifier = named_block(decision, "modifier")
        gain = self.number(modifier, "political_power_gain")
        self.assertGreater(cost, 0)
        self.assertGreater(days * gain, cost)
        self.assertLessEqual(days * gain - cost, 15)
        self.assertGreaterEqual(self.number(decision, "days_re_enable"), days)
        self.assertEqual(self.number(modifier, "ADISCORD_economy_trade_income_factor"), 0.08)
        for effect in ("complete_effect", "remove_effect"):
            self.assertEqual(named_block(decision, effect).count("ADISCORD_economy_mark_dirty = yes"), 1)

    def test_every_campaign_uses_and_returns_one_shared_slot(self) -> None:
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                self.assertEqual(named_block(decision, "complete_effect").count("ADISCORD_campaign_slot_consume = yes"), 1)
                self.assertEqual(named_block(decision, "remove_effect").count("ADISCORD_campaign_slot_release = yes"), 1)
                self.assertNotIn("ADISCORD_campaign_slot_grant", decision)
                self.assertGreater(self.number(decision, "days_remove"), 0)

    def test_campaign_tooltips_and_free_slot_display_exist_in_both_languages(self) -> None:
        keys = ("VAL_campaign_slot_granted_tt", "VAL_campaign_second_slot_tt", "VAL_campaign_mine_unlock_tt", "VAL_campaign_slot_available_tt", "VAL_contract_management_desc", "VAL_Ministry_Of_Contract_Memory_desc", "VAL_Two_Concurrent_Narratives_desc", "VAL_campaign_no_promise_without_payment_desc")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in keys:
                with self.subTest(language=language, key=key):
                    entries = re.findall(rf'(?m)^\s*{re.escape(key)}:(?:\d+)?\s+"([^"\r\n]*)"\s*$', text)
                    self.assertEqual(len(entries), 1, key)
                    self.assertTrue(entries[0])
                    if key in ("VAL_contract_management_desc", "VAL_campaign_slot_available_tt"):
                        self.assertIn("[?ADISCORD_available_campaign_slots|0]", entries[0])

    def test_campaign_files_have_no_merge_markers_or_duplicate_definitions(self) -> None:
        for path in ("common/national_focus/ADISCORD_national_focus_VAL.txt", "common/decisions/ADISCORD_VAL_decisions.txt", "common/decisions/categories/ADISCORD_VAL_rework_categories.txt"):
            text = read(path)
            self.assertNotRegex(text, r"(?m)^(?:<{7}|={7}(?:\r?$)|>{7})(?: |$)")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for decision_id in self.campaigns:
            self.assertEqual(len(re.findall(rf"(?m)^\s*{re.escape(decision_id)}\s*=\s*\{{", decisions)), 1)



class TestValMergedContractFlows(unittest.TestCase):
    def test_quarterly_payment_debits_pp_only_after_the_val_rifle_receipt(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        decision = named_block(named_block(decisions, "VAL_contract_management"), "VAL_pay_quarterly_contract_norm")
        self.assertNotIn("add_political_power", named_block(decision, "complete_effect"))
        effect = named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_pay_quarterly_contract_norm")
        self.assertNotIn("STP_cw_rifles_paid", effect)
        self.assertEqual(effect.count("add_political_power = -10"), 1)
        receipt = effect.index("has_country_flag = VAL_contract_rifles_paid")
        self.assertLess(receipt, effect.index("add_political_power = -10"))
        self.assertLess(effect.index("add_political_power = -10"), effect.index("set_country_flag = VAL_quarterly_contract_paid"))

    def test_export_capacity_is_defined_once_and_is_not_a_second_payment(self):
        ideas = read("common/ideas/ADISCORD_VAL_rework_ideas.txt")
        for name in ("VAL_export_income_1", "VAL_export_income_2", "VAL_advisors_income", "VAL_paid_military_advisors"):
            with self.subTest(idea=name):
                self.assertEqual(len(re.findall(r"(?m)^\s*" + name + r"\s*=\s*\{", ideas)), 1)
                self.assertNotIn("ADISCORD_economy_weekly_income", named_block(ideas, name))

    def test_reclamation_state_and_industry_use_distinct_stage_gates(self):
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        state = named_block(text, "VAL_reclamation_state_project_valid")
        for name in ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier", "VAL_reclamation_stage_2_modifier"):
            self.assertIn("modifier = " + name, state)
        self.assertNotIn("ROOT", state)
        industry = named_block(text, "VAL_reclamation_industry_target_valid")
        self.assertIn("value = 3 compare = equals", industry)
        self.assertIn("industrial_complex < 19", industry)
        self.assertNotIn("VAL_reclamation_clean_water", industry)
        self.assertNotIn("ADISCORD_vorkerland_dirty_state", industry)

    def test_reclamation_refresh_preserves_untreated_states_and_is_idempotent(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        text = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        raw = named_block(text, "VAL_reclamation_refresh_state")
        self.assertNotIn("<<<<<<<", raw)
        body = parse_clausewitz(raw)[0].value
        def field(entry, key):
            return next(e.value for e in entry.value if e.key == key)
        for stage in (0, 1, 2, 3, 4):
            modifiers = {"ADISCORD_vorkerland_dirty_state"}
            values = {"VAL_reclamation_stage": stage}
            def condition(e):
                if e.key == "check_variable":
                    actual = values.get(field(e, "var"), 0)
                    target = float(field(e, "value"))
                    return actual >= target
                if e.key == "has_dynamic_modifier":
                    return field(e, "modifier") in modifiers
                raise AssertionError(e.key)
            def execute(entries):
                matched = False
                for e in entries:
                    if e.key in ("if", "else_if", "else"):
                        if e.key == "if": matched = False
                        limit = next((v.value for v in e.value if v.key == "limit"), [])
                        if not matched and all(condition(v) for v in limit):
                            execute([v for v in e.value if v.key != "limit"])
                            matched = True
                    elif e.key == "remove_dynamic_modifier": modifiers.discard(field(e, "modifier"))
                    elif e.key == "add_dynamic_modifier": modifiers.add(field(e, "modifier"))
                    elif e.key == "clear_variable": values.pop(e.value, None)
                    else: raise AssertionError(e.key)
            for repeat in range(2):
                execute(body)
                expected = {"ADISCORD_vorkerland_dirty_state"} if stage == 0 else {f"VAL_reclamation_stage_{min(stage, 3)}_modifier"}
                with self.subTest(stage=stage, repeat=repeat): self.assertEqual(modifiers, expected)

    def test_merge_preserves_corridor_ui_and_native_paid_program_previews(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            self.assertIn("$VAL_trade_corridors_desc$", text)
            self.assertIn("VAL_focus_paid_program_authorization_tt", text)
            self.assertNotRegex(text, r"(?m)^(?:<<<<<<<|=======|>>>>>>>)")
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        for decision in ("ADISCORD_economy_automated_industry", "ADISCORD_economy_logistics_contract", "ADISCORD_economy_national_computing"):
            self.assertIn("unlock_decision_tooltip = { decision = " + decision + " show_effect_tooltip = yes }", focuses)


class TestValReclamationCompletion(unittest.TestCase):
    states = (24, 42, 48, 54, 55, 56, 57)

    def test_paid_reclamation_matches_the_actual_starting_contamination(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = parse_clausewitz(named_block(text, "VAL_reclamation_complete"))[0].value
        self.assertEqual({e.key for e in gate if e.key.isdigit()}, {str(n) for n in self.states})
        pollution = named_block(read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
                                "ADISCORD_vorkerland_apply_dirty_modifiers")
        initially_dirty = {int(e.key) for e in parse_clausewitz(pollution)[0].value if e.key.isdigit()} & set(self.states)
        self.assertEqual(initially_dirty, {24, 57}, "Review the paid objective when starting contamination changes")
        complete = {("VAL", "has_completed_focus", "VAL_reclamation_return_home"): True}
        for state in self.states:
            complete.update({
                (str(state), "variable", "VAL_reclamation_stage"): 3 if state in initially_dirty else 0,
                (str(state), "is_owned_by", "VAL"): True,
                (str(state), "is_controlled_by", "VAL"): True,
            })
        self.assertTrue(matches_conditions(gate, complete, "VAL"), "Clean home regions have no paid reclamation decision")
        self.assertFalse(matches_conditions(gate, {}, "VAL"), "No completion before paid reclamation")
        self.assertFalse(matches_conditions(gate, complete | {("VAL", "has_variable", "VAL_reclamation_deposit"): True}, "VAL"))
        for state in self.states:
            for stage in (0, 1, 2, 3, 4):
                expected = stage >= 3 or (stage == 0 and state not in initially_dirty)
                with self.subTest(state=state, stage=stage):
                    self.assertEqual(matches_conditions(gate, complete | {(str(state), "variable", "VAL_reclamation_stage"): stage}, "VAL"), expected)
            for key in ("is_owned_by", "is_controlled_by"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), key, "VAL"): False}, "VAL"))
            for modifier in ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier", "VAL_reclamation_stage_2_modifier"):
                self.assertFalse(matches_conditions(gate, complete | {(str(state), "has_dynamic_modifier", modifier): True}, "VAL"))
        self.assertTrue(matches_conditions(gate, complete | {("999", "variable", "VAL_reclamation_stage"): 0}, "VAL"))

    def test_spirit_removal_is_one_time_and_does_not_revoke_earned_focus_bonuses(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        effect = parse_clausewitz(named_block(read("common/scripted_effects/ADISCORD_VAL_effects.txt"), "VAL_complete_reclamation"))[0].value
        self.assertEqual(len(effect), 1)
        branch = effect[0]
        self.assertEqual(branch.key, "if")
        limit = next(e.value for e in branch.value if e.key == "limit")
        self.assertEqual({(e.key, e.value) for e in limit}, {("has_idea", "VAL_harvest_of_ash"), ("VAL_reclamation_complete", "yes")})
        body = [(e.key, e.value) for e in branch.value if e.key != "limit"]
        self.assertEqual(body, [("remove_ideas", "VAL_harvest_of_ash"), ("ADISCORD_economy_mark_dirty", "yes")])
        for completed in (False, True):
            ideas = {"VAL_harvest_of_ash"}
            invalidations = 0
            for _ in range(2):
                ready = all((e.value in ideas) if e.key == "has_idea" else completed for e in limit)
                if ready:
                    for key, value in body:
                        if key == "remove_ideas": ideas.discard(value)
                        elif key == "ADISCORD_economy_mark_dirty": invalidations += 1
            self.assertEqual("VAL_harvest_of_ash" in ideas, not completed)
            self.assertEqual(invalidations, int(completed))

    def test_reclamation_callbacks_resolve_explicit_state_receipts(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        for action in ("finish", "refund"):
            callback = named_block(effects, f"VAL_reclamation_{action}_project")
            self.assertNotIn("FROM =", callback)
            self.assertIn("var = VAL_reclamation_deposit value = 500 compare = equals", callback)
            for state in (24, 42, 48, 54, 55, 56, 57):
                self.assertIn(f"{state} = {{ VAL_reclamation_{action}_state_project = yes }}", callback)

    def test_final_paid_result_checks_completion_without_save_migration(self):
        text = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        finish = named_block(text, "VAL_reclamation_finish_state_project")
        self.assertIn("VAL_complete_reclamation = yes", finish)
        self.assertLess(finish.index("add_to_variable = { var = VAL_reclamation_stage"), finish.index("VAL_complete_reclamation = yes"))
        self.assertIn("VAL = { VAL_complete_reclamation = yes", finish)
        self.assertNotIn("VAL_complete_reclamation", named_block(text, "VAL_reclamation_refund_state_project"))
        actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        startup = named_block(actions, "on_startup")
        self.assertNotIn("VAL_migrate_reclamation_modifiers", startup)
        self.assertNotIn("VAL_complete_reclamation", startup)
        self.assertNotIn("VAL_complete_reclamation", named_block(actions, "on_weekly_VAL"))
        focuses = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        self.assertNotIn("remove_ideas = VAL_harvest_of_ash", focuses)
        self.assertNotIn("VAL_complete_reclamation = yes", focuses)

    def test_reclamation_goal_is_visible_in_both_languages_and_the_spirit(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            keys = dict(re.findall(r'(?m)^\s*([\w.]+):(?:\d+)?\s*"(.*)"$', text))
            for key in ("VAL_reclamation_desc", "VAL_reclamation_settlement_result_tt"):
                self.assertIn("$VAL_reclamation_completion_tt$", keys[key])
            self.assertIn("$VAL_harvest_of_ash$", keys["VAL_reclamation_completion_tt"])
            for state in self.states:
                self.assertIn(f"[{state}.GetName]", keys["VAL_reclamation_completion_tt"])
            ideas = read(f"localisation/{language}/ADISCORD_ideas_l_{language}.yml")
            desc = re.search(r'(?m)^\s*VAL_harvest_of_ash_desc:(?:\d+)?\s*"(.*)"$', ideas).group(1)
            self.assertIn("$VAL_reclamation_completion_tt$", desc)


class TestValExpansionRoute(unittest.TestCase):
    def test_north_policy_does_not_wait_for_someone_elses_civil_war(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        text = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(text, "VAL_frontier_postwar")
        self.assertNotIn("STP_cw_union_wars_finished", gate)
        self.assertNotIn("VAL_stelander_civil_war_active", gate)
        for check in ("has_capitulated = no", "is_subject = no", "NOT = { has_country_flag = VAL_stelander_defeated }"):
            self.assertIn(check, gate)
        entries = parse_clausewitz(gate)[0].value
        def matches(facts):
            return all(not facts.get(child.value, False) if e.key == "NOT" else facts.get(e.key, "no") == e.value
                       for e in entries for child in (e.value if e.key == "NOT" else [e]))
        self.assertTrue(matches({"STP_cw_union_wars_finished": False, "VAL_stelander_civil_war_active": True}))
        for blocked in ("has_capitulated", "is_subject"):
            self.assertFalse(matches({blocked: "yes"}))
        self.assertFalse(matches({"VAL_stelander_defeated": True}))
        decisions = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_frontier")
        for name in ("VAL_frontier_demand_CIN", "VAL_frontier_demand_ERT", "VAL_frontier_begin_offensive"):
            self.assertIn("has_war = no", named_block(named_block(decisions, name), "available"))
        self.assertIn("STP_cw_union_wars_finished", named_block(text, "VAL_stelander_ultimatum_target"))

    def test_expansion_is_central_visible_and_has_no_prerequisite_cycle(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        tree = parse_clausewitz(read("common/national_focus/ADISCORD_national_focus_VAL.txt"))[0].value
        def get(entries, key):
            return next(e.value for e in entries if e.key == key)
        focuses = {get(e.value, "id"): e.value for e in tree if e.key == "focus"}
        entry = focuses["VAL_frontier_conference"]
        spine = focuses["VAL_Contracts_Outlive_Kings"]
        self.assertEqual(get(entry, "x"), get(spine, "x"))
        self.assertEqual(float(get(entry, "y")), float(get(spine, "y")) + 2)
        groups = [e.value for e in entry if e.key == "prerequisite"]
        self.assertEqual(len(groups), 1)
        self.assertEqual({e.value for e in groups[0]}, {"VAL_Contracts_Outlive_Kings", "VAL_The_Steel_Contract", "VAL_Market_Roads_North"})
        for name in ("VAL_frontier_conference", "VAL_frontier_security_plan"):
            self.assertIn("FOCUS_FILTER_ANNEXATION", [e.value for e in get(focuses[name], "search_filters")])
        coords = [(get(f, "x"), get(f, "y")) for f in focuses.values()]
        self.assertEqual(len(coords), len(set(coords)))
        done, active = set(), set()
        def visit(name):
            self.assertNotIn(name, active, f"Cyclic focus route at {name}")
            if name in done: return
            active.add(name)
            for block in focuses[name]:
                if block.key == "prerequisite":
                    for parent in block.value: visit(parent.value)
            active.remove(name)
            done.add(name)
        for name in focuses: visit(name)


class TestValReclamationFollowThrough(unittest.TestCase):
    def test_paid_deadline_matches_the_native_decision_duration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        fallback = named_block(effects, "VAL_reclamation_reconcile_state_project")
        age = int(re.search(r"days\s*>\s*(\d+)", fallback).group(1))
        for suffix in ("roads", "water", "settlement"):
            decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_reclamation_" + suffix)
            days = int(re.search(r"days_remove\s*=\s*(\d+)", decision).group(1))
            self.assertEqual(age + 1, days)

    def test_recapturing_the_last_restored_home_region_rechecks_the_spirit(self):
        actions = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        hook = named_block(actions, "on_state_control_changed")
        self.assertIn("ROOT = { tag = VAL has_idea = VAL_harvest_of_ash }", hook)
        self.assertIn("ROOT = { VAL_complete_reclamation = yes }", hook)
        for state in (24, 42, 48, 54, 55, 56, 57):
            self.assertIn("state = " + str(state), hook)
        self.assertNotIn("VAL_complete_reclamation", named_block(actions, "on_weekly_VAL"))

    def test_legacy_compensation_is_disabled_without_save_migration(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        refresh = named_block(effects, "VAL_reclamation_refresh_state")
        self.assertIn("has_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertIn("remove_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", refresh)
        self.assertNotIn("add_dynamic_modifier = { modifier = VAL_reclamation_recovered_land }", effects)
        legacy = named_block(read("common/dynamic_modifiers/ADISCORD_VAL_contract_dynamic_modifier.txt"), "VAL_reclamation_recovered_land")
        self.assertIn("enable = { always = no }", legacy)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertNotIn("VAL_reclamation_modifier_migrated_v3", startup)

    def test_balchansk_branch_has_localised_names_and_descriptions(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for name in ("VAL_Balchansk_Charter", "VAL_Balchansk_Clearing_House"):
                for key in (name, name + "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^\s*{key}:\d*\s+"[^"\r\n]+"\s*$', text)), 1, (language, key))

    def test_reclamation_and_route_copy_preserve_localisation_references(self):
        from collections import Counter
        catalogues = {}
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            catalogues[language] = dict(re.findall(r'(?m)^\s*(\w+):\d*\s*"(.*)"$', text))
        for key in ("VAL_reclamation_completion_tt", "VAL_startup_guide", "VAL_reclamation_desc",
                    "VAL_reclamation_settlement_result_tt", "VAL_Balchansk_Charter_desc", "VAL_Balchansk_Clearing_House_desc"):
            tokens = {language: Counter(re.findall(r'\$[A-Za-z0-9_]+\$|\[[^\]]+\]', values[key]))
                      for language, values in catalogues.items()}
            self.assertEqual(tokens["russian"], tokens["english"], key)


class KefreytOpeningThemeTests(unittest.TestCase):
    def test_first_focus_plays_registered_theme_for_human_country(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        tree = parse_clausewitz((ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text())[0].value
        focus = next(e.value for e in tree if e.key == "focus" and any(c.key == "id" and c.value == "VAL_The_Contract_State" for c in e.value))
        reward = next(e.value for e in focus if e.key == "completion_reward")
        hidden = next(e.value for e in reward if e.key == "hidden_effect")
        guarded = [e.value for e in hidden if e.key == "if" and any(c.key == "scoped_play_song" for c in e.value)]
        self.assertEqual(len(guarded), 1, "The opening focus must start Kefreyt's theme exactly once")
        limit = next(e.value for e in guarded[0] if e.key == "limit")
        self.assertEqual([(e.key, e.value) for e in limit], [("is_ai", "no")])
        self.assertEqual([e.value for e in guarded[0] if e.key == "scoped_play_song"], ["ADISCORD_val_theme"])
        self.assertFalse(any(e.key == "play_song" for e in reward + hidden + guarded[0]))
        assets = parse_clausewitz((ROOT / "music/ADISCORD_music.asset").read_text())
        theme = [e.value for e in assets if e.key == "music" and any(c.key == "name" and c.value == "ADISCORD_val_theme" for c in e.value)]
        self.assertEqual(len(theme), 1)
        self.assertIn(("file", "ADISCORD_val_theme.ogg"), [(e.key, e.value) for e in theme[0]])
        self.assertIn('song = "ADISCORD_val_theme"', (ROOT / "music/ADISCORD_songs.txt").read_text())

if __name__ == "__main__":
    unittest.main()


class TestValProgressionChoices(unittest.TestCase):
    def focus(self, name):
        source = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        marker = re.search(r"\bid\s*=\s*" + re.escape(name) + r"\s", source)
        self.assertIsNotNone(marker, name)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", source[:marker.start()]))
        return named_block(source[starts[-1].start():], "focus")

    def test_portrait_belongs_to_proclamation_not_unlock(self):
        focus = self.focus("VAL_Contracts_Outlive_Kings")
        self.assertNotIn("set_portraits", focus)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        adopt = named_block(effects, "VAL_adopt_commonwealth")
        self.assertIn("VAL_can_proclaim_commonwealth = yes", adopt)
        self.assertLess(adopt.index("set_cosmetic_tag = VAL_commonwealth"),
                        adopt.index("VAL_sync_solgalov_portrait = yes"))
        sync = named_block(effects, "VAL_sync_solgalov_portrait")
        self.assertIn("has_character = VAL_Valera_Solgalov", sync)
        self.assertIn("has_cosmetic_tag = VAL_commonwealth", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov_contracts", sync)
        self.assertIn("large = GFX_portrait_VAL_Valera_Solgalov }", sync)
        self.assertNotIn("recruit_character", sync)
        startup = named_block(read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt"), "on_startup")
        self.assertEqual(startup.count("VAL_sync_solgalov_portrait = yes"), 1)

    def test_proclamation_has_one_map_marker_and_keeps_real_requirements(self):
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_proclaim_commonwealth")
        for token in ("state_target = yes", "targets = { 48 }", "on_map_mode = map_and_decisions_view", "highlight_states", "cost = 150", "VAL_can_proclaim_commonwealth = yes"):
            self.assertIn(token, decision)
        self.assertIn("has_completed_focus = VAL_Contracts_Outlive_Kings", named_block(decision, "visible"))
        self.assertNotIn("VAL_can_proclaim_commonwealth", named_block(decision, "visible"))
        trigger = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_can_proclaim_commonwealth")
        self.assertIn("VAL_campaign_objectives_met = yes", trigger)
        self.assertNotIn("deferred", trigger)

    def test_frontier_bypass_requires_explicit_choice_and_an_idle_peace(self):
        focus = self.focus("VAL_frontier_treaty_offices")
        bypass = named_block(focus, "bypass")
        self.assertIn("VAL_northern_expansion_deferred = yes", bypass)
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = named_block(triggers, "VAL_northern_expansion_deferred")
        for token in ("has_country_flag = VAL_frontier_expansion_deferred", "has_completed_focus = VAL_frontier_security_plan", "VAL_frontier_idle = yes", "has_war = no", "has_capitulated = no", "is_subject = no"):
            self.assertIn(token, gate)
        self.assertNotIn("is_ai", gate)
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        defer = named_block(decisions, "VAL_defer_northern_expansion")
        self.assertIn("VAL_can_defer_northern_expansion = yes", named_block(defer, "available"))
        self.assertIn("ai_will_do", defer)
        reward = named_block(defer, "complete_effect")
        for forbidden in ("transfer_state", "annex_country", "add_core_of", "set_cosmetic_tag", "VAL_frontier_treaty_signed"):
            self.assertNotIn(forbidden, reward)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", reward)

    def test_declining_then_reopening_does_not_leave_a_stale_opt_out(self):
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        withdraw = named_block(decisions, "VAL_frontier_withdraw_demand")
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", withdraw)
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        withdraw_effect = named_block(effects, "VAL_frontier_withdraw_and_defer")
        self.assertIn("value = 2 compare = equals", withdraw_effect)
        self.assertIn("has_war = no", withdraw_effect)
        self.assertIn("VAL_frontier_close = yes", withdraw_effect)
        self.assertIn("set_country_flag = VAL_frontier_expansion_deferred", withdraw_effect)
        demand = named_block(decisions, "VAL_frontier_demand_CIN")
        self.assertIn("clr_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "complete_effect"))
        self.assertIn("VAL_ai_frontier_force_ready", named_block(demand, "ai_will_do"))
        self.assertIn("has_country_flag = VAL_frontier_expansion_deferred", named_block(demand, "ai_will_do"))

    def test_nodrul_campaign_waits_for_a_real_northern_foothold(self):
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        foothold = named_block(triggers, "VAL_northern_foothold_secured")
        for group in (("58", "59", "60"), ("61", "62", "63"), ("64", "65")):
            for state in group:
                self.assertIn(f"{state} = {{", foothold)
        self.assertIn("OR =", foothold)

        northern = self.focus("VAL_Northern_Settlement")
        available = named_block(northern, "available")
        self.assertIn("VAL_northern_foothold_secured = yes", available)
        self.assertIn("VAL_nod_campaign_foothold_tt", available)

        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        nod = named_block(decisions, "VAL_campaign_against_nod")
        self.assertIn("VAL_stelander_dominated = yes", named_block(nod, "available"))
        self.assertIn("VAL_nod_requires_stelander_victory_tt", named_block(nod, "available"))
        self.assertIn("VAL_northern_foothold_secured = yes", named_block(nod, "available"))
        self.assertIn("NOT = { VAL_stelander_dominated = yes }", named_block(nod, "cancel_trigger"))
        self.assertIn("NOT = { VAL_northern_foothold_secured = yes }", named_block(nod, "cancel_trigger"))
        self.assertIn("VAL_stelander_dominated = yes", named_block(nod, "remove_effect"))
        self.assertIn("VAL_northern_foothold_secured = yes", named_block(nod, "remove_effect"))

        final_crisis = named_block(triggers, "VAL_final_crisis_available")
        self.assertIn("VAL_stelander_dominated = yes", final_crisis)

        stelander = self.focus("VAL_Stelander_Ultimatum")
        if "available = {" in stelander:
            self.assertNotIn("VAL_northern_foothold_secured", named_block(stelander, "available"))

        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        nod_intervention = named_block(effects, "VAL_frontier_issue_nod_ultimatum")
        self.assertNotIn("VAL_northern_foothold_secured", nod_intervention)
        self.assertIn("VAL_stelander_dominated = yes", nod_intervention)

        frontier_join = named_block(effects, "VAL_frontier_join_existing_war")
        self.assertEqual(frontier_join.count("VAL = { VAL_stelander_dominated = yes }"), 3)

        guarantor_ai = named_block(triggers, "VAL_ai_frontier_guarantor_preparation")
        self.assertIn("tag = NOD", guarantor_ai)
        self.assertIn("VAL = { VAL_stelander_dominated = yes }", guarantor_ai)

    def test_ai_strongly_prefers_occidian_invasion_course(self):
        military = self.focus("VAL_Seize_The_Northern_Passes")
        trade = self.focus("VAL_Arms_For_The_Burning")
        neutral = self.focus("VAL_Keep_The_Arsenals")

        def ai_base(focus):
            ai = named_block(focus, "ai_will_do")
            match = re.search(r"\bbase\s*=\s*([0-9.]+)", ai)
            self.assertIsNotNone(match)
            return float(match.group(1))

        self.assertGreaterEqual(ai_base(military), 5 * ai_base(trade))
        self.assertGreaterEqual(ai_base(military), 10 * ai_base(neutral))

        mobilization = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_cw_begin_mobilization")
        ai = named_block(mobilization, "ai_will_do")
        self.assertIn("factor = 5 has_country_flag = VAL_cw_military_course", ai)
        self.assertIn("factor = 2 has_country_flag = VAL_cw_trade_course", ai)

        stelander_campaign = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_campaign_against_stelander")
        self.assertIn("base = 30", named_block(stelander_campaign, "ai_will_do"))

    def test_economic_route_does_not_require_bypassed_military_rewards(self):
        reopen = self.focus("VAL_Reopen_Trade_Routes")
        debts = self.focus("VAL_Settle_Industrial_Debts")
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", reopen)
        self.assertIn("focus = VAL_New_Supply_Base focus = VAL_Contingency_Ledgers", reopen)
        self.assertIn("focus = VAL_Campaign_Secured focus = VAL_Returning_Buyers", debts)
        for name in ("VAL_Reopen_Trade_Routes", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market"):
            with self.subTest(name=name):
                focus = self.focus(name)
                self.assertIn("VAL_economic_settlement_ready = yes", named_block(focus, "available"))
                self.assertNotIn("bypass", focus)
        gate = named_block(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"), "VAL_economic_settlement_ready")
        for token in ("VAL_campaign_objectives_met = yes", "VAL_northern_expansion_deferred = yes", "has_completed_focus = VAL_Returning_Buyers", "has_completed_focus = VAL_Contingency_Ledgers"):
            self.assertIn(token, gate)
        for name in ("VAL_Campaign_Secured", "VAL_New_Supply_Base", "VAL_Veterans_Of_The_Campaign"):
            self.assertNotIn("bypass", self.focus(name))

    def test_choice_and_economic_conditions_are_localised_in_both_languages(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in ("VAL_defer_northern_expansion", "VAL_defer_northern_expansion_desc", "VAL_defer_northern_expansion_tt", "VAL_defer_northern_expansion_ready_tt", "VAL_economic_settlement_ready_tt", "VAL_northern_expansion_deferred_tt", "VAL_nod_campaign_foothold_tt", "VAL_nod_requires_stelander_victory_tt"):
                self.assertRegex(text, rf'(?m)^ {key}:\d* "[^\r\n]*"$')
            self.assertIn("VAL_nod_campaign_foothold_tt", text)


class TestValProgressionContinuation(unittest.TestCase):
    def refusal(self):
        source = read("events/ADISCORD_VAL_contract_events.txt")
        marker = source.index("id = val_rework.111\n")
        return named_block(source[source.rfind("country_event", 0, marker):], "country_event")

    def test_proclamation_category_is_visible_from_its_unlock(self):
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_postwar_administration")
        visible = named_block(category, "visible")
        for focus in ("VAL_frontier_conference", "VAL_Contracts_Outlive_Kings"):
            self.assertIn("has_completed_focus = " + focus, visible)
        self.assertIn("OR =", visible)

    def test_refusal_event_selects_the_same_safe_withdrawal_as_the_decision(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.withdraw")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        reward = named_block(option, "hidden_effect")
        self.assertIn("VAL_frontier_reply_is_current = yes", reward)
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", reward)
        self.assertNotIn("VAL_frontier_close = yes", reward)
        self.assertIn("custom_effect_tooltip = VAL_frontier_withdraw_tt", option)

    def test_ai_refusal_event_uses_the_same_force_gate_as_decisions(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.war")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        chance = named_block(option, "ai_chance")
        self.assertIn("VAL_ai_frontier_force_ready = no", chance)
        self.assertNotIn("num_divisions < 24", chance)

    def test_opt_out_and_recovery_evaluate_the_real_trigger_graph(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        definitions = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        flags, focuses = set(), {"VAL_frontier_security_plan"}
        facts = {"has_war": False, "is_subject": False, "has_capitulated": False,
                 "VAL_frontier_stage": 0, "VAL_campaign_objectives_met": False}

        def evaluate(entry):
            key, value = entry.key, entry.value
            if key in ("OR", "AND", "NOT"):
                result = [evaluate(e) for e in value]
                return any(result) if key == "OR" else (not all(result) if key == "NOT" else all(result))
            if key == "has_country_flag": return value in flags
            if key == "has_completed_focus": return value in focuses
            if key == "tag": return value == "VAL"
            if key in ("has_war", "is_subject", "has_capitulated", "VAL_campaign_objectives_met"):
                return facts[key] == (value == "yes")
            if key == "check_variable":
                data = {e.key: e.value for e in value}
                self.assertEqual(data["compare"], "greater_than")
                return facts.get(data["var"], 0) > float(data["value"])
            if key in definitions:
                self.assertIn(value, ("yes", "no"))
                return all(evaluate(e) for e in definitions[key]) == (value == "yes")
            self.fail("Unimplemented trigger in this fixture: " + key)

        def check(name): return all(evaluate(e) for e in definitions[name])
        self.assertTrue(check("VAL_can_defer_northern_expansion"))
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.add("VAL_frontier_expansion_deferred")
        self.assertFalse(check("VAL_can_defer_northern_expansion"))
        self.assertTrue(check("VAL_northern_expansion_deferred"))
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Returning_Buyers")
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Contingency_Ledgers")
        self.assertTrue(check("VAL_economic_settlement_ready"))
        for key in ("has_war", "is_subject", "has_capitulated"):
            with self.subTest(blocker=key):
                facts[key] = True
                self.assertFalse(check("VAL_northern_expansion_deferred"))
                self.assertFalse(check("VAL_economic_settlement_ready"))
                facts[key] = False
        for stage in (1, 2, 3):
            facts["VAL_frontier_stage"] = stage
            self.assertFalse(check("VAL_northern_expansion_deferred"))
        facts["VAL_frontier_stage"] = 0
        for flag in ("VAL_campaign_mobilizing", "VAL_stelander_defeated"):
            flags.add(flag)
            self.assertFalse(check("VAL_economic_settlement_ready"))
            flags.remove(flag)
        focuses.remove("VAL_frontier_security_plan")
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.clear()
        facts["VAL_campaign_objectives_met"] = True
        self.assertTrue(check("VAL_economic_settlement_ready"))


class TestValReclamationCategory(unittest.TestCase):
    def setUp(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        self.category = next(e.value for e in parse_clausewitz(read(
            "common/decisions/categories/ADISCORD_VAL_rework_categories.txt"))
            if e.key == "VAL_reclamation")
        categories = parse_clausewitz(read("common/decisions/ADISCORD_VAL_decisions.txt"))
        self.decisions = {e.key: e.value for e in next(
            c.value for c in categories if c.key == "VAL_reclamation")}
        self.triggers = {e.key: e.value for e in parse_clausewitz(read(
            "common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        self.steps = (
            ("VAL_reclamation_roads", "VAL_reclamation_survey"),
            ("VAL_reclamation_water", "VAL_reclamation_clean_water"),
            ("VAL_reclamation_settlement", "VAL_reclamation_return_home"),
            ("VAL_reclamation_industry", "VAL_reclamation_industrial_sites"),
        )

    def expand(self, items):
        from dataclasses import replace
        expanded = []
        for entry in items:
            if entry.key in self.triggers:
                self.assertIn(entry.value, ("yes", "no"))
                expanded.append(replace(entry, key="AND" if entry.value == "yes" else "NOT",
                                        value=self.expand(self.triggers[entry.key])))
            elif isinstance(entry.value, list):
                expanded.append(replace(entry, value=self.expand(entry.value)))
            else:
                expanded.append(entry)
        return expanded

    def facts(self, stage, *, survey=True, owned=True, controlled=True, dirty=True):
        facts = {
            ("VAL", "has_completed_focus", "VAL_reclamation_survey"): survey,
            ("VAL", "has_capitulated", "no"): True,
            ("FROM", "is_owned_by", "ROOT"): owned,
            ("FROM", "is_owned_by", "VAL"): owned,
            ("FROM", "is_controlled_by", "ROOT"): controlled,
            ("FROM", "is_controlled_by", "VAL"): controlled,
            ("FROM", "variable", "VAL_reclamation_stage"): stage,
        }
        modifiers = ("ADISCORD_vorkerland_dirty_state", "VAL_reclamation_stage_1_modifier",
                     "VAL_reclamation_stage_2_modifier")
        if dirty and stage < len(modifiers):
            facts[("FROM", "has_dynamic_modifier", modifiers[stage])] = True
        return facts

    def matches(self, items, facts):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        return matches_conditions(self.expand(items), facts, "VAL")

    def decision_condition(self, decision, condition, facts):
        from tools.tests.test_adiscord_stp_preparation import block
        return self.matches(block(self.decisions[decision], condition), facts)

    def visible_rows(self, facts):
        return [name for name in self.decisions if self.decision_condition(name, "visible", facts)]

    def test_empty_reclamation_category_is_not_forced_into_the_list(self):
        from tools.tests.test_adiscord_stp_preparation import scalar
        self.assertEqual(scalar(self.category, "visible_when_empty"), "no")
        self.assertEqual(self.visible_rows(self.facts(0, dirty=False)), [])
        self.assertEqual(self.visible_rows(self.facts(4)), [])
        self.assertEqual(self.visible_rows(self.facts(0, owned=False)), [])

    def test_each_local_stage_has_one_visible_followup_after_survey(self):
        for stage, (name, _) in enumerate(self.steps):
            with self.subTest(stage=stage):
                self.assertEqual(self.visible_rows(self.facts(stage)), [name])
                self.assertEqual(self.visible_rows(self.facts(stage, survey=False)), [])

    def test_missing_followup_focus_blocks_execution_without_hiding_the_project(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        for stage, (name, focus) in enumerate(self.steps[1:], 1):
            with self.subTest(stage=stage):
                facts = self.facts(stage)
                self.assertTrue(self.decision_condition(name, "visible", facts))
                available = block(self.decisions[name], "available")
                self.assertEqual(scalar(available, "has_completed_focus"), focus)
                self.assertFalse(self.matches(available, facts))
                facts[("VAL", "has_completed_focus", focus)] = True
                self.assertTrue(self.matches(available, facts))

    def test_occupation_and_busy_work_keep_the_current_stage_readable(self):
        for stage, (name, focus) in enumerate(self.steps):
            with self.subTest(stage=stage):
                facts = self.facts(stage, controlled=False)
                facts[("VAL", "has_completed_focus", focus)] = True
                self.assertTrue(self.decision_condition(name, "visible", facts))
                self.assertFalse(self.decision_condition(name, "available", facts))
                facts = self.facts(stage)
                facts[("VAL", "has_completed_focus", focus)] = True
                if stage == 3:
                    facts[("FROM", "has_variable", "VAL_reclamation_industry_deposit")] = True
                else:
                    facts[("VAL", "has_variable", "VAL_reclamation_deposit")] = True
                self.assertTrue(self.decision_condition(name, "visible", facts))
                self.assertFalse(self.decision_condition(name, "available", facts))

    def test_clean_and_foreign_states_do_not_gain_fake_reclamation_projects(self):
        facts = self.facts(0, dirty=False)
        for _, focus in self.steps:
            facts[("VAL", "has_completed_focus", focus)] = True
        self.assertEqual(self.visible_rows(facts), [])
        for stage in range(4):
            with self.subTest(stage=stage):
                self.assertEqual(self.visible_rows(self.facts(stage, owned=False)), [])

    def test_projects_stay_in_their_category_with_both_map_and_list_entries(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        self.assertEqual(set(self.decisions), {name for name, _ in self.steps})
        for name, _ in self.steps:
            body = self.decisions[name]
            self.assertEqual(scalar(body, "on_map_mode"), "map_and_decisions_view")
            self.assertEqual(scalar(body, "cost"), "0")
            targets = block(body, "targets")
            self.assertEqual({e.value for e in targets}, {"24", "42", "48", "54", "55", "56", "57"})
            self.assertEqual(scalar(body, "days_remove"), "60" if name.endswith("industry") else "90")
