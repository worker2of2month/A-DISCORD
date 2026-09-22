

class TestValExpansionAndReclamation(unittest.TestCase):
    regions = ("24", "42", "48", "54", "55", "56", "57")

    def definitions(self, path):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        return {entry.key: entry.value for entry in parse_clausewitz(read(path))}

    def focuses(self):
        from tools.tests.test_adiscord_stp_preparation import scalar
        tree = self.definitions("common/national_focus/ADISCORD_national_focus_VAL.txt")["focus_tree"]
        return {scalar(entry.value, "id"): entry.value for entry in tree if entry.key == "focus"}

    def expand_triggers(self, entries, stack=()):
        from tools.validators.validate_adiscord_division_templates import Entry
        triggers = self.definitions("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        result = []
        for entry in entries:
            if entry.key in triggers and isinstance(entry.value, str):
                self.assertIn(entry.value, ("yes", "no"))
                self.assertNotIn(entry.key, stack, "recursive trigger")
                result.append(Entry("AND" if entry.value == "yes" else "NOT",
                                    self.expand_triggers(triggers[entry.key], stack + (entry.key,)), entry.line))
            elif isinstance(entry.value, list):
                result.append(Entry(entry.key, self.expand_triggers(entry.value, stack), entry.line))
            else:
                result.append(entry)
        return result

    def recovery_facts(self):
        facts = {("VAL", "has_idea", "VAL_harvest_of_ash"): True,
                 ("VAL", "has_completed_focus", "VAL_reclamation_return_home"): True}
        for region in self.regions:
            facts[(region, "variable", "VAL_reclamation_stage")] = 3
            facts[(region, "is_owned_by", "VAL")] = True
            facts[(region, "is_controlled_by", "VAL")] = True
        return facts

    def test_expansion_spine_continues_the_central_contract_axis(self):
        from tools.tests.test_adiscord_stp_preparation import scalar
        focuses = self.focuses()
        axis = scalar(focuses["VAL_Contracts_Outlive_Kings"], "x")
        last_y = int(scalar(focuses["VAL_Contracts_Outlive_Kings"], "y"))
        for name in ("VAL_frontier_conference", "VAL_frontier_security_plan", "VAL_frontier_treaty_offices",
                     "VAL_New_Supply_Base", "VAL_Campaign_Secured", "VAL_Settle_Industrial_Debts", "VAL_Return_To_World_Market"):
            with self.subTest(focus=name):
                self.assertEqual(scalar(focuses[name], "x"), axis)
                y = int(scalar(focuses[name], "y"))
                self.assertGreater(y, last_y)
                last_y = y
        prerequisites = [entry.value for entry in focuses["VAL_frontier_conference"] if entry.key == "prerequisite"]
        self.assertEqual([[e.value for e in group] for group in prerequisites], [["VAL_Contracts_Outlive_Kings"]])

    def test_expansion_layout_has_separated_nodes_and_downward_dependencies(self):
        from tools.tests.test_adiscord_stp_preparation import scalar
        focuses = self.focuses()
        positions = {key: (int(scalar(value, "x")), int(scalar(value, "y"))) for key, value in focuses.items()}
        for key, value in focuses.items():
            x, y = positions[key]
            for other, (ox, oy) in positions.items():
                if key < other and oy == y:
                    self.assertGreaterEqual(abs(x - ox), 2, (key, other))
            for group in (e.value for e in value if e.key == "prerequisite"):
                for prerequisite in group:
                    if prerequisite.key == "focus":
                        self.assertLess(positions[prerequisite.value][1], y, (prerequisite.value, key))
        for name in ("VAL_Stelander_Crisis_Opens", "VAL_The_Steel_Contract", "VAL_Occidian_Registries",
                     "VAL_Balchansk_Charter", "VAL_Balchansk_Clearing_House", "VAL_Integrate_Occidia"):
            self.assertGreaterEqual(positions[name][0], 30, name)
        for name in ("VAL_frontier_conference", "VAL_frontier_security_plan"):
            self.assertIn("FOCUS_FILTER_ANNEXATION", [e.value for group in focuses[name] if group.key == "search_filters" for e in group.value])

    def test_north_is_independent_of_stelander_war_but_keeps_sovereignty_guards(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions, block, walk
        triggers = self.definitions("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        gate = self.expand_triggers(triggers["VAL_frontier_postwar"])
        for finished in (False, True):
            facts = {("VAL", "has_capitulated", "no"): True, ("VAL", "is_subject", "no"): True,
                     ("VAL", "has_global_flag", "STP_cw_union_wars_finished"): finished}
            self.assertTrue(matches_conditions(gate, facts, "VAL"))
            for key in (("VAL", "has_capitulated", "no"), ("VAL", "is_subject", "no")):
                self.assertFalse(matches_conditions(gate, facts | {key: False}, "VAL"))
            self.assertFalse(matches_conditions(gate, facts | {("VAL", "has_country_flag", "VAL_stelander_defeated"): True}, "VAL"))
        decisions = self.definitions("common/decisions/ADISCORD_VAL_decisions.txt")["VAL_frontier"]
        for decision in ("VAL_frontier_demand_CIN", "VAL_frontier_demand_ERT", "VAL_frontier_begin_offensive"):
            availability = block(block(decisions, decision), "available")
            expanded = self.expand_triggers(availability)
            self.assertFalse(any(e.key == "has_global_flag" and e.value == "STP_cw_union_wars_finished" for e in walk(expanded)))
            self.assertTrue(any(e.key == "has_war" and e.value == "no" for e in walk(availability)))

    def test_balchansk_focus_names_and_descriptions_load_in_both_languages(self):
        for language in ("russian", "english"):
            text = read(f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml")
            for name in ("VAL_Balchansk_Charter", "VAL_Balchansk_Clearing_House"):
                for key in (name, name + "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^\s*{key}:\d*\s+"[^"\r\n]+"\s*$', text)), 1, (language, key))

    def test_harvest_requires_all_seven_regions_not_a_focus_or_ceded_pollution(self):
        from tools.tests.test_adiscord_stp_preparation import matches_conditions
        triggers = self.definitions("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        self.assertIn("VAL_reclamation_fully_restored", triggers)
        condition = self.expand_triggers(triggers["VAL_reclamation_fully_restored"])
        facts = self.recovery_facts()
        self.assertTrue(matches_conditions(condition, facts, "VAL"))
        for region in self.regions:
            for stage in (0, 1, 2):
                with self.subTest(region=region, stage=stage):
                    self.assertFalse(matches_conditions(condition, facts | {(region, "variable", "VAL_reclamation_stage"): stage}, "VAL"))
            for key in ("is_owned_by", "is_controlled_by"):
                self.assertFalse(matches_conditions(condition, facts | {(region, key, "VAL"): False}, "VAL"))
            self.assertTrue(matches_conditions(condition, facts | {(region, "variable", "VAL_reclamation_stage"): 4}, "VAL"))
        self.assertFalse(matches_conditions(condition, facts | {("VAL", "has_variable", "VAL_reclamation_deposit"): True}, "VAL"))

    def test_harvest_removal_is_idempotent_and_invalidates_the_budget(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects
        effects = self.definitions("common/scripted_effects/ADISCORD_VAL_effects.txt")
        self.assertIn("VAL_reclamation_check_full_recovery", effects)
        effect = self.expand_triggers(effects["VAL_reclamation_check_full_recovery"])
        facts = self.recovery_facts()
        selected = [e for _, e in selected_effects(effect, facts, "VAL")]
        self.assertEqual([e.value for e in selected if e.key == "remove_ideas"], ["VAL_harvest_of_ash"])
        self.assertEqual(sum(e.key == "ADISCORD_economy_mark_dirty" for e in selected), 1)
        for changes in ({("VAL", "has_idea", "VAL_harvest_of_ash"): False},
                        {("57", "variable", "VAL_reclamation_stage"): 2}):
            self.assertEqual(list(selected_effects(effect, facts | changes, "VAL")), [])

    def test_last_paid_settlement_and_old_save_load_reconcile_harvest(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        finish = named_block(effects, "VAL_reclamation_finish_state_project")
        call = "VAL_reclamation_check_full_recovery = yes"
        self.assertIn(call, finish)
        self.assertLess(finish.index("add_to_variable = { var = VAL_reclamation_stage"), finish.index(call))
        hooks = read("common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt")
        self.assertIn(call, named_block(hooks, "on_startup"))
        self.assertIn(call, named_block(hooks, "on_state_control_changed"))
        self.assertNotIn(call, named_block(hooks, "on_weekly_VAL"))
        for name in ("VAL_reclamation_refund_project", "VAL_reclamation_refund_state_project", "VAL_reclamation_begin_project"):
            self.assertNotIn(call, named_block(effects, name))
        self.assertNotIn(call, read("common/national_focus/ADISCORD_national_focus_VAL.txt"))

    def test_paid_reclamation_fallback_preserves_the_ninety_day_deadline(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        fallback = named_block(effects, "VAL_reclamation_reconcile_state_project")
        age = int(re.search(r'days\s*>\s*(\d+)', fallback).group(1))
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for suffix in ("roads", "water", "settlement"):
            duration = int(re.search(r'days_remove\s*=\s*(\d+)', named_block(decisions, "VAL_reclamation_" + suffix)).group(1))
            self.assertEqual(age + 1, duration)

    def test_quarterly_payment_charges_political_power_only_once(self):
        effects = read("common/scripted_effects/ADISCORD_VAL_effects.txt")
        decision = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_pay_quarterly_contract_norm")
        payment = named_block(effects, "VAL_pay_quarterly_contract_norm")
        self.assertEqual(len(re.findall(r'add_political_power\s*=\s*-10\b', decision + payment)), 1)
        self.assertIn("has_country_flag = VAL_contract_rifles_paid", payment)

    def test_supply_precedes_shared_outcome_without_redundant_crossing_arrows(self):
        focuses = self.focuses()
        def parents(name):
            return {e.value for group in focuses[name] if group.key == "prerequisite" for e in group.value if e.key == "focus"}
        self.assertIn("VAL_New_Supply_Base", parents("VAL_Campaign_Secured"))
        self.assertNotIn("VAL_New_Supply_Base", parents("VAL_Reopen_Trade_Routes"))
        self.assertNotIn("VAL_Industrial_Mobilization_Plan", parents("VAL_Settle_Industrial_Debts"))
        self.assertNotIn("VAL_Army_Of_The_Ledger", parents("VAL_Veterans_Of_The_Campaign"))
