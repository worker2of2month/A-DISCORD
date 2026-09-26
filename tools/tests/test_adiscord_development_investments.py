from pathlib import Path
import re
import unittest


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
                return text[start:index + 1]
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
                return text[start:index + 1]
    raise AssertionError(f"Unclosed focus: {focus_id}")


class RouteGatedDevelopmentProgrammeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.generic_decisions = GENERIC_DECISIONS.read_text(encoding="utf-8")
        cls.generic_categories = GENERIC_CATEGORIES.read_text(encoding="utf-8")
        cls.val_decisions = VAL_DECISIONS.read_text(encoding="utf-8")
        cls.stp_decisions = STP_DECISIONS.read_text(encoding="utf-8")
        cls.val_focus = VAL_FOCUS.read_text(encoding="utf-8")
        cls.stp_focus = STP_FOCUS.read_text(encoding="utf-8")
        cls.ideas = IDEAS.read_text(encoding="utf-8")

    def test_standalone_development_category_is_removed(self) -> None:
        self.assertNotIn("ADISCORD_development_investments = {", self.generic_decisions)
        self.assertNotIn("ADISCORD_development_investments = {", self.generic_categories)
        for legacy in (
            "ADISCORD_invest_army_development",
            "ADISCORD_invest_state_development",
            "ADISCORD_invest_economic_development",
            "ADISCORD_invest_society_development",
            "ADISCORD_invest_social_system_development",
            "ADISCORD_invest_cultural_development",
        ):
            self.assertNotIn(legacy, self.generic_decisions)

    def test_shared_programme_spirits_are_temporary_growth_multipliers(self) -> None:
        specs = {
            "ADISCORD_development_program_army": "ADISCORD_country_development_army_growth_factor = 1.00",
            "ADISCORD_development_program_state": "ADISCORD_country_development_state_growth_factor = 1.00",
            "ADISCORD_development_program_economic": "ADISCORD_country_development_economic_growth_factor = 1.00",
            "ADISCORD_development_program_social_system": "ADISCORD_country_development_social_system_growth_factor = 1.00",
        }
        for idea_id, modifier in specs.items():
            with self.subTest(idea=idea_id):
                body = named_block(self.ideas, idea_id)
                self.assertIn("allowed = { always = no }", body)
                self.assertIn(modifier, body)

    def test_kefreyt_programmes_live_in_reclamation_and_unlock_along_left_branch(self) -> None:
        category = named_block(self.val_decisions, "VAL_reclamation")
        specs = {
            "VAL_recovery_road_corps_program": (
                "VAL_reclamation_road_crews",
                "ADISCORD_development_program_state",
            ),
            "VAL_recovery_field_medicine_program": (
                "VAL_Field_Surgeons",
                "ADISCORD_development_program_social_system",
            ),
            "VAL_recovery_workshop_program": (
                "VAL_reclamation_workshops",
                "ADISCORD_development_program_economic",
            ),
        }
        for decision_id, (focus_id, idea_id) in specs.items():
            with self.subTest(decision=decision_id):
                body = named_block(category, decision_id)
                self.assertIn(f"has_completed_focus = {focus_id}", body)
                self.assertIn("custom_cost_trigger = { ADISCORD_economy_can_spend_100 = yes }", body)
                self.assertEqual(body.count("ADISCORD_economy_spend_100 = yes"), 1)
                self.assertIn("days_remove = 120", body)
                self.assertIn("days_re_enable = 60", body)
                self.assertIn(f"add_timed_idea = {{ idea = {idea_id} days = 120 }}", body)
                self.assertIn(f"remove_ideas = {idea_id}", body)
                self.assertNotRegex(body, r"ADISCORD_(?:increase|decrease)_\w+_development_monthly_growth")
                focus = focus_block(self.val_focus, focus_id)
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", focus)

    def test_stelander_programmes_use_existing_route_categories_and_expire_before_split(self) -> None:
        party = named_block(self.stp_decisions, "STP_elections_in_the_party")
        shabrat = named_block(self.stp_decisions, "STP_battle_for_stelander")
        specs = (
            (party, "STP_party_staff_drills_program", "STP_defense_budget", "ADISCORD_development_program_army"),
            (party, "STP_party_civil_service_program", "STP_party_civil_register", "ADISCORD_development_program_state"),
            (shabrat, "STP_shabrat_staff_courses_program", "STP_cw_officer_contacts", "ADISCORD_development_program_army"),
            (shabrat, "STP_shabrat_reconstruction_program", "STP_cw_repair_niansas", "ADISCORD_development_program_economic"),
        )
        for owner, decision_id, focus_id, idea_id in specs:
            with self.subTest(decision=decision_id):
                body = named_block(owner, decision_id)
                self.assertIn("custom_cost_trigger = { ADISCORD_economy_can_spend_50 = yes }", body)
                self.assertEqual(body.count("ADISCORD_economy_spend_50 = yes"), 1)
                self.assertIn("days_remove = 42", body)
                self.assertIn("days_re_enable = 21", body)
                self.assertIn("days_mission_timeout@STP_cw_election_window value = 43 compare = greater_than", body)
                self.assertIn(f"add_timed_idea = {{ idea = {idea_id} days = 42 }}", body)
                self.assertIn(f"remove_ideas = {idea_id}", body)
                self.assertNotRegex(body, r"ADISCORD_(?:increase|decrease)_\w+_development_monthly_growth")
                focus = focus_block(self.stp_focus, focus_id)
                self.assertIn(f"unlock_decision_tooltip = {decision_id}", focus)

    def test_shared_cost_localisation_is_complete_and_russian_keeps_bom(self) -> None:
        self.assertTrue(RU_ECON.read_bytes().startswith(b"\xef\xbb\xbf"))
        for path in (RU_ECON, EN_ECON):
            text = path.read_text(encoding="utf-8-sig")
            self.assertNotIn("ADISCORD_development_investments:", text)
            self.assertNotIn("ADISCORD_development_investment_cost_250:", text)
            for price in (50, 100):
                for suffix in ("", "_blocked", "_tooltip"):
                    key = f"ADISCORD_development_program_cost_{price}{suffix}"
                    match = re.search(rf'^ {re.escape(key)}:0? "([^"]+)"$', text, re.M)
                    self.assertIsNotNone(match, f"{path}: missing {key}")
                    self.assertIn(str(price), match.group(1))
                    self.assertIn("£ADISCORD_economy_treasury_texticon", match.group(1))


if __name__ == "__main__":
    unittest.main()
