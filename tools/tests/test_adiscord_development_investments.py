from pathlib import Path
import re
import unittest

from tools.lib.focus_sources import read_focus_source

ROOT = Path(__file__).resolve().parents[2]
GENERIC_DECISIONS = ROOT / "common/decisions/ADISCORD_economy_projects.txt"
GENERIC_CATEGORIES = ROOT / "common/decisions/categories/ADISCORD_economy_projects.txt"
VAL_DECISIONS = ROOT / "common/decisions/ADISCORD_VAL_decisions.txt"
STP_DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
VAL_FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt"
STP_FOCUS = ROOT / "common/national_focus/ADISCORD_national_focus_STP.txt"
IDEAS = ROOT / "common/ideas/ADISCORD_economy_ideas.txt"
RU_ECON = ROOT / "localisation/russian/ADISCORD_economy_l_russian.yml"
EN_ECON = ROOT / "localisation/english/ADISCORD_economy_l_english.yml"


def named_block(text: str, name: str) -> str:
    marker = f"{name} = {{"
    start = text.index(marker)
    brace = text.index("{", start)
    depth = 0
    in_string = False
    escaped = False
    for index in range(brace, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
                continue
            if character == "\\":
                escaped = True
                continue
            if character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unclosed block: {name}")


def focus_block(text: str, focus_id: str) -> str:
    marker = f"id = {focus_id}"
    position = text.index(marker)
    start = text.rfind("focus = {", 0, position)
    brace = text.index("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"Unclosed focus: {focus_id}")


class RouteGatedDevelopmentProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generic_decisions = GENERIC_DECISIONS.read_text(encoding="utf-8")
        cls.generic_categories = GENERIC_CATEGORIES.read_text(encoding="utf-8")
        cls.val_decisions = VAL_DECISIONS.read_text(encoding="utf-8")
        cls.stp_decisions = STP_DECISIONS.read_text(encoding="utf-8")
        cls.val_focus = read_focus_source(VAL_FOCUS, encoding="utf-8")
        cls.stp_focus = read_focus_source(STP_FOCUS, encoding="utf-8")
        cls.ideas = IDEAS.read_text(encoding="utf-8")

    def test_standalone_development_category_is_removed(self) -> None:
        self.assertNotIn("ADISCORD_development_investments = {", self.generic_decisions)
        self.assertNotIn(
            "ADISCORD_development_investments = {", self.generic_categories
        )
        for legacy in (
            "ADISCORD_invest_army_development",
            "ADISCORD_invest_state_development",
            "ADISCORD_invest_economic_development",
            "ADISCORD_invest_society_development",
            "ADISCORD_invest_social_system_development",
            "ADISCORD_invest_cultural_development",
        ):
            self.assertNotIn(legacy, self.generic_decisions)

    def test_programmes_use_fixed_progress_instead_of_temporary_spirits(self) -> None:
        self.assertNotIn("ADISCORD_development_program_", self.ideas)

    def test_kefreyt_programmes_live_in_reclamation_and_unlock_along_left_branch(
        self,
    ) -> None:
        category = named_block(self.val_decisions, "VAL_reclamation")
        specs = {
            "VAL_recovery_road_corps_program": (
                "VAL_reclamation_road_crews",
                "ADISCORD_state_development_progress",
            ),
            "VAL_recovery_field_medicine_program": (
                "VAL_Field_Surgeons",
                "ADISCORD_social_system_development_progress",
            ),
            "VAL_recovery_workshop_program": (
                "VAL_reclamation_workshops",
                "ADISCORD_economic_development_progress",
            ),
        }
        for decision_id, (focus_id, progress_var) in specs.items():
            with self.subTest(decision=decision_id):
                body = named_block(category, decision_id)
                self.assertIn(f"has_completed_focus = {focus_id}", body)
                self.assertIn(
                    "custom_cost_trigger = { ADISCORD_economy_can_spend_500 = yes }",
                    body,
                )
                self.assertEqual(body.count("ADISCORD_economy_spend_500 = yes"), 1)
                self.assertIn("days_remove = 120", body)
                self.assertIn("days_re_enable = 60", body)
                self.assertIn(
                    "custom_effect_tooltip = ADISCORD_development_program_result_35",
                    body,
                )
                self.assertIn(
                    f"add_to_variable = {{ var = {progress_var} value = 35 }}",
                    body,
                )
                self.assertNotIn("add_timed_idea", body)
                self.assertNotRegex(
                    body,
                    r"ADISCORD_(?:increase|decrease)_\w+_development_monthly_growth",
                )
                focus = focus_block(self.val_focus, focus_id)
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", focus)

    def test_stelander_programmes_use_existing_route_categories_and_expire_before_split(
        self,
    ) -> None:
        party = named_block(self.stp_decisions, "STP_elections_in_the_party")
        shabrat = named_block(self.stp_decisions, "STP_battle_for_stelander")
        specs = (
            (
                party,
                "STP_party_staff_drills_program",
                "STP_defense_budget",
                "ADISCORD_army_development_progress",
            ),
            (
                party,
                "STP_party_civil_service_program",
                "STP_party_civil_register",
                "ADISCORD_state_development_progress",
            ),
            (
                shabrat,
                "STP_shabrat_staff_courses_program",
                "STP_cw_officer_contacts",
                "ADISCORD_army_development_progress",
            ),
            (
                shabrat,
                "STP_shabrat_reconstruction_program",
                "STP_cw_repair_niansas",
                "ADISCORD_economic_development_progress",
            ),
        )
        for owner, decision_id, focus_id, progress_var in specs:
            with self.subTest(decision=decision_id):
                body = named_block(owner, decision_id)
                self.assertIn(
                    "custom_cost_trigger = { ADISCORD_economy_can_spend_300 = yes }",
                    body,
                )
                self.assertEqual(body.count("ADISCORD_economy_spend_300 = yes"), 1)
                self.assertIn("days_remove = 42", body)
                self.assertIn("days_re_enable = 21", body)
                self.assertIn(
                    "days_mission_timeout@STP_cw_election_window value = 43 compare = greater_than",
                    body,
                )
                self.assertIn(
                    "custom_effect_tooltip = ADISCORD_development_program_result_25",
                    body,
                )
                self.assertIn(
                    f"add_to_variable = {{ var = {progress_var} value = 25 }}",
                    body,
                )
                self.assertNotIn("add_timed_idea", body)
                self.assertNotRegex(
                    body,
                    r"ADISCORD_(?:increase|decrease)_\w+_development_monthly_growth",
                )
                focus = focus_block(self.stp_focus, focus_id)
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", focus)

    def test_shared_cost_localisation_is_complete_and_russian_keeps_bom(self) -> None:
        self.assertTrue(RU_ECON.read_bytes().startswith(b"\xef\xbb\xbf"))
        for path in (RU_ECON, EN_ECON):
            text = path.read_text(encoding="utf-8-sig")
            self.assertNotIn("ADISCORD_development_investments:", text)
            self.assertNotIn("ADISCORD_development_investment_cost_250:", text)
            for price in (300, 500):
                for suffix in ("", "_blocked", "_tooltip"):
                    key = f"ADISCORD_development_program_cost_{price}{suffix}"
                    match = re.search(rf'^ {re.escape(key)}:0? "([^"]+)"$', text, re.M)
                    self.assertIsNotNone(match, f"{path}: missing {key}")
                    self.assertIn(str(price), match.group(1))
                    self.assertIn("£ADISCORD_economy_treasury_texticon", match.group(1))


class CountryDevelopmentReformTests(unittest.TestCase):
    AXES = ("society", "social_system", "army", "cultural", "state", "economic")

    @classmethod
    def setUpClass(cls):
        from tools.tests.test_adiscord_economy_weekly_contracts import EconomyScriptFixture

        cls.fixture_type = EconomyScriptFixture
        cls.effects = (ROOT / "common/scripted_effects/ADISCORD_society_development_effects.txt").read_text(encoding="utf-8")
        cls.triggers = (ROOT / "common/scripted_triggers/ADISCORD_society_development_triggers.txt").read_text(encoding="utf-8")
        cls.lists = (ROOT / "common/scripted_triggers/ADISCORD_development_country_lists.txt").read_text(encoding="utf-8")

    def fixture(self, countries=None):
        return self.fixture_type(
            countries=countries,
            texts=(self.effects, self.triggers, self.lists),
            stubs=("custom_effect_tooltip", "ADISCORD_economy_mark_dirty"),
        )

    def test_reforms_pay_exact_progress_and_monthly_growth_in_each_direction(self):
        for axis in self.AXES:
            with self.subTest(axis=axis):
                fixture = self.fixture()
                fixture.run("ADISCORD_initialize_default_country_development")
                values = fixture.scopes["A"]
                prefix = f"ADISCORD_{axis}_development"
                values[prefix + "_progress"] = 91.5
                values[prefix + "_monthly_growth"] = 0.75
                fixture.run(f"ADISCORD_reform_{axis}_development")
                self.assertEqual(values[prefix + "_progress"], 116.5)
                self.assertEqual(values[prefix + "_monthly_growth"], 2.75)
                for other in set(self.AXES) - {axis}:
                    self.assertEqual(values[f"ADISCORD_{other}_development_progress"], 0)
                    self.assertEqual(values[f"ADISCORD_{other}_development_monthly_growth"], 0)
                self.assertIn("ADISCORD_economy_mark_dirty", fixture.calls)

    def test_country_handoff_copies_all_axes_without_resetting_paid_progress(self):
        from copy import deepcopy

        fixture = self.fixture({"STP": {}, "STS": {}, "WRK": {}})
        donor = fixture.scopes["STP"]
        for index, axis in enumerate(self.AXES):
            prefix = f"ADISCORD_{axis}_development"
            donor[prefix + "_level"] = 2 + index % 3
            donor[prefix + "_progress"] = 95.25 + index
            donor[prefix + "_monthly_growth"] = index - 0.5
        original = deepcopy(donor)
        for source, recipient in (("STP", "STS"), ("STS", "WRK")):
            fixture.run("ADISCORD_initialize_default_country_development", recipient)
            fixture.run("ADISCORD_copy_development_from_prev", recipient, source)
            for key, expected in original.items():
                self.assertEqual(fixture.scopes[recipient][key], expected, key)
            for axis in self.AXES:
                prefix = f"ADISCORD_{axis}_development"
                level = original[prefix + "_level"]
                for candidate in range(1, 6):
                    self.assertEqual(
                        fixture.scopes[recipient].get(f"idea@{prefix}_{candidate}", False),
                        candidate == level,
                    )
            self.assertEqual(fixture.scopes[recipient]["ADISCORD_total_development_score"], 18)
        self.assertEqual(donor, original)

    def test_successor_ticks_are_scheduled_once_for_humans_and_ai(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        hooks = (ROOT / "common/on_actions/00_ADISCORD_on_actions.txt").read_text(encoding="utf-8")
        monthly = parse_clausewitz(named_block(hooks, "on_monthly"))[0].value
        yearly = parse_clausewitz(named_block(hooks, "on_yearly"))[0].value

        def development_condition(hook, call):
            effect = next(node.value for node in hook if node.key == "effect")
            branch = next(node.value for node in effect if node.key == "if" and any(child.key == call for child in node.value))
            return next(node.value for node in branch if node.key == "limit")

        month = development_condition(monthly, "ADISCORD_tick_all_society_development_monthly")
        year = development_condition(yearly, "ADISCORD_tick_all_society_development_yearly")
        for tag in ("STS", "SRP", "WKR", "TVA", "WRK", "VAD", "NOD"):
            for ai in (False, True):
                with self.subTest(tag=tag, ai=ai):
                    fixture = self.fixture({"A": {"tag": tag, "is_ai": ai, "ADISCORD_fresh_campaign_contract_v1": True}})
                    scheduled = [fixture.condition(month), fixture.condition(year)]
                    self.assertEqual(sum(scheduled), 1)
        fixture = self.fixture({"A": {"tag": "VAD", "is_ai": True, "ADISCORD_fresh_campaign_contract_v1": True, "ADISCORD_non_participating_minor_optimized": True}})
        self.assertFalse(fixture.condition(year))

    def test_stelander_creation_scope_and_repeat_preserve_successor_progress(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        text = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
        creation = parse_clausewitz(named_block(text, "STP_cw_prepare_successor"))[0].value
        for tag in ("STS", "SRP"):
            fixture = self.fixture({"STP": {}, tag: {}})
            fixture.run("ADISCORD_initialize_default_country_development", "STP")
            progress = "ADISCORD_army_development_progress"
            fixture.scopes["STP"][progress] = 83.5
            fixture.execute(creation[:1], tag, "STP", "STP")
            self.assertEqual(fixture.scopes[tag][progress], 83.5)
            fixture.scopes[tag]["STP_cw_templates_loaded"] = True
            fixture.scopes[tag][progress] = 91.75
            fixture.scopes["STP"][progress] = 7
            fixture.execute(creation[:1], tag, "STP", "STP")
            self.assertEqual(fixture.scopes[tag][progress], 91.75)

    def test_reforms_cover_all_six_axes_and_do_not_repeat_along_one_route(self):
        sources = (
            "VAL/main", "SHL/main", "NAM/main", "IVN/main", "STP/postwar/party",
        )
        pattern = r"ADISCORD_reform_(\w+)_development = yes"
        for source in sources:
            text = (ROOT / "focus_trees" / source / "focuses.txt").read_text(encoding="utf-8")
            axes = re.findall(pattern, text)
            self.assertEqual(set(axes), set(self.AXES), source)
            # Kefreyt's food and medicine alternatives each support social services.
            expected = 7 if source == "VAL/main" else 6
            self.assertEqual(len(axes), expected, source)
        text = (ROOT / "focus_trees/VAL/main/focuses.txt").read_text(encoding="utf-8")
        for focus, alternative in (("VAL_Field_Surgeons", "VAL_Bread_From_Barracks"), ("VAL_Bread_From_Barracks", "VAL_Field_Surgeons")):
            body = focus_block(text, focus)
            self.assertIn(f"mutually_exclusive = {{ focus = {alternative} }}", body)
            self.assertIn("ADISCORD_reform_social_system_development = yes", body)
        text = (ROOT / "focus_trees/Vorkerland/civil_war/focuses.txt").read_text(encoding="utf-8")
        for route in ("worker", "joint", "utilitarian"):
            pairs = {
                "pw_census": "society", "pw_municipal_network": "social_system",
                "pw_officer_school": "army", "restore_unity_tower": "cultural",
                "pw_service_charter": "state", "pw_production_board": "economic",
            }
            for suffix, axis in pairs.items():
                body = focus_block(text, f"WRK_{route}_{suffix}")
                self.assertIn(f"has_country_flag = ADISCORD_vorkerland_route_{route}", body)
                self.assertNotIn("bypass =", body)
                self.assertIn(f"ADISCORD_reform_{axis}_development = yes", body)
        shabrat = (ROOT / "focus_trees/STP/postwar/shabrat/focuses.txt").read_text(encoding="utf-8")
        self.assertCountEqual(re.findall(pattern, shabrat), ("social_system", "army", "cultural"))
        for axis in ("society", "state", "economic"):
            self.assertIn(f"ADISCORD_increase_{axis}_development_monthly_growth = yes", shabrat)

    def test_copy_runs_during_creation_and_before_claimant_annexation(self):
        stp = (ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt").read_text(encoding="utf-8")
        successor = named_block(stp, "STP_cw_prepare_successor")
        self.assertIn("NOT = { has_country_flag = STP_cw_templates_loaded }", successor)
        self.assertLess(successor.index("ADISCORD_copy_development_from_prev"), successor.index("set_country_flag = STP_cw_templates_loaded"))
        self.assertLess(successor.index("ADISCORD_copy_development_from_prev"), successor.index("ADISCORD_economy_initialize_country"))
        vorkerland = (ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt").read_text(encoding="utf-8")
        opening = named_block(vorkerland, "ADISCORD_vorkerland_prepare_initial_combatants")
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn("ADISCORD_copy_development_from_prev = yes", named_block(opening, tag))
            formation = named_block(vorkerland, "ADISCORD_vorkerland_form_wrk_from_" + tag.lower())
            self.assertEqual(formation.count("ADISCORD_copy_development_from_prev = yes"), 1)
            self.assertLess(formation.index("ADISCORD_copy_development_from_prev"), formation.index(f"annex_country = {{ target = {tag}"))

    def test_reform_tooltips_are_valid_single_line_localisation(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_society_development_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for axis in self.AXES:
                key = f"ADISCORD_{axis}_development_reform_tt"
                values = re.findall(rf'^ {key}:0 "([^"\n]+)"$', text, re.M)
                self.assertEqual(len(values), 1, key)
                for value in ("+25", "+2", "100"):
                    self.assertIn(value, values[0])


if __name__ == "__main__":
    unittest.main()
