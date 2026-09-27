from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def block(text, name):
    start = text.index(name + " =")
    opening = text.index("{", start)
    depth = 0
    in_string = False
    escaped = False
    for index in range(opening, len(text)):
        character = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                in_string = False
            continue
        if character == '"':
            in_string = True
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError(f"unterminated block: {name}")


class StelanderStalemateRegressionTests(unittest.TestCase):
    def test_repeatable_civil_war_orders_stop_ai_at_frontage_saturation(self):
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        for name in (
            "STP_cw_raise_territorial_brigade",
            "STP_cw_train_reserve_brigades",
            "STP_party_form_assault_column",
        ):
            with self.subTest(decision=name):
                order = block(decisions, name)
                self.assertIn("NOT = { num_divisions < 24 }", order)

        strategies = read("common/ai_strategy/ADISCORD_STP_civil_war.txt")
        for name, enemy in (
            ("STP_cw_ai_force_saturation", "STS"),
            ("STS_cw_ai_force_saturation", "STP"),
        ):
            with self.subTest(strategy=name):
                profile = block(strategies, name)
                self.assertIn("is_ai = yes", profile)
                self.assertIn(f"has_war_with = {enemy}", profile)
                self.assertIn("NOT = { num_divisions < 24 }", profile)
                self.assertIn("type = ai_wanted_divisions_factor value = -1000", profile)

    def test_kefreyt_volunteers_are_real_diplomatic_volunteers_to_either_side(self):
        triggers = read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
        host = block(triggers, "VAL_stelander_volunteer_host")
        self.assertIn("tag = STP", host)
        self.assertIn("has_war_with = STS", host)
        self.assertIn("tag = STS", host)
        self.assertIn("has_war_with = STP", host)
        self.assertIn("NOT = { has_war_with = VAL }", host)

        diplo = block(
            read("common/scripted_triggers/00_diplo_action_valid_triggers.txt"),
            "is_diplomatic_action_valid_send_volunteers",
        )
        self.assertIn("VAL_stelander_volunteer_mandate", diplo)
        self.assertIn("VAL_stelander_volunteer_host = yes", diplo)

        mandate = block(
            read("common/ideas/ADISCORD_VAL_rework_ideas.txt"),
            "VAL_stelander_volunteer_mandate",
        )
        self.assertIn("can_send_volunteers = yes", mandate)
        self.assertIn("send_volunteer_divisions_required = -1", mandate)
        self.assertIn("VAL_stelander_volunteer_front_open = no", mandate)
        self.assertIn("VAL_recall_stelander_volunteers = yes", mandate)

        decision = block(
            read("common/decisions/ADISCORD_VAL_decisions.txt"),
            "VAL_stelander_volunteers",
        )
        self.assertIn("add_ideas = VAL_stelander_volunteer_mandate", decision)
        self.assertIn("ai_will_do = { base = 0 }", decision)

        recall = block(
            read("common/scripted_effects/ADISCORD_VAL_effects.txt"),
            "VAL_recall_stelander_volunteers",
        )
        self.assertIn("recall_volunteers_from = STP", recall)
        self.assertIn("recall_volunteers_from = STS", recall)


if __name__ == "__main__":
    unittest.main()
