from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    path = ROOT / relative
    return path.read_text(encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8")


def named_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block {name}")
    depth = 0
    quoted = False
    escaped = False
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[match.start(): index + 1]
    raise AssertionError(f"unclosed block {name}")


class ShabratHegemonyExpansionTests(unittest.TestCase):
    def test_shabrat_route_focuses_swap_portraits_immediately(self) -> None:
        gfx = read("interface/ADISCORD_leader_portraits.gfx")
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")

        self.assertIn('name = "GFX_portrait_STP_Maksim_Shabrat_hegemony"', gfx)
        self.assertIn('texturefile = "gfx/leaders/STP/portrait_STP_Maksim_Shabrat_uniform.png"', gfx)
        self.assertIn('name = "GFX_portrait_STP_Maksim_Shabrat_freedom"', gfx)
        self.assertIn('texturefile = "gfx/leaders/STP/portrait_STP_Maksim_Shabrat_alternative.png"', gfx)

        hegemony = re.search(r"(?ms)id = STP_pc_hegemony_open\b.*?(?=\n\tfocus = \{)", focuses)
        freedom = re.search(r"(?ms)id = STP_pc_freedom_open\b.*?(?=\n\tfocus = \{)", focuses)
        self.assertIsNotNone(hegemony)
        self.assertIsNotNone(freedom)
        self.assertIn("set_portraits", hegemony.group(0))
        self.assertIn("GFX_portrait_STP_Maksim_Shabrat_hegemony", hegemony.group(0))
        self.assertIn("set_portraits", freedom.group(0))
        self.assertIn("GFX_portrait_STP_Maksim_Shabrat_freedom", freedom.group(0))

        hegemony_lock = named_block(effects, "STP_pc_lock_hegemony")
        freedom_lock = named_block(effects, "STP_pc_lock_freedom")
        self.assertIn("GFX_portrait_STP_Maksim_Shabrat_hegemony", hegemony_lock)
        self.assertIn("GFX_portrait_STP_Maksim_Shabrat_freedom", freedom_lock)
        self.assertNotIn("GFX_portrait_STP_Maksim_Shabrat_dictator", hegemony_lock)
        self.assertNotIn("GFX_portrait_STP_Maksim_Shabrat_dictator", freedom_lock)
        self.assertIn("portrait = GFX_portrait_STP_Maksim_Shabrat_dictator", effects)

    def test_final_campaigns_are_staged_north_then_kefreyt(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        for focus_id in (
            "STP_pc_heg_administrations",
            "STP_pc_heg_final_north",
            "STP_pc_heg_final_kefreyt",
        ):
            self.assertEqual(focuses.count(f"id = {focus_id}"), 1, focus_id)
        north = named_block(effects, "STP_heg_start_northern_final_war")
        for tag in ("NOD", "YPR", "TFF"):
            self.assertIn(f"declare_war_on = {{ target = {tag} type = annex_everything }}", north)
        self.assertNotIn("target = VAL", north)
        kefreyt = named_block(effects, "STP_heg_start_kefreyt_final_war")
        self.assertIn("declare_war_on = { target = VAL type = annex_everything }", kefreyt)
        resolved = named_block(triggers, "STP_heg_northern_final_resolved")
        for tag in ("NOD", "YPR", "TFF"):
            self.assertIn(f"NOT = {{ has_war_with = {tag} }}", resolved)

    def test_nod_acceptance_creates_an_annexable_puppet(self) -> None:
        events = read("events/ADISCORD_STP_events.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        decisions = read("common/decisions/ADISCORD_STP_hegemony_decisions.txt")
        self.assertIn("set_country_flag = STP_pc_nod_client_pending", events)
        finalizer = named_block(effects, "STP_pc_finalize_nod_client_subject")
        self.assertIn("puppet = NOD", finalizer)
        self.assertIn("autonomy_state = autonomy_puppet", finalizer)
        annex = named_block(decisions, "STP_heg_annex_nod_administration")
        self.assertIn("has_autonomy_state = autonomy_puppet", annex)
        self.assertIn("annex_country = { target = NOD transfer_troops = yes }", annex)

    def test_second_kefreyt_war_uses_distinct_scripted_peace(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        peace = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        hegemony_actions = read("common/on_actions/11_ADISCORD_STP_hegemony_on_actions.txt")
        settlement = named_block(effects, "STP_heg_settle_kefreyt_final")
        self.assertIn("STP_pc_recover_stelander_cores_from_val = yes", settlement)
        self.assertIn("every_enemy_country = {", settlement)
        self.assertIn("has_country_flag = STP_heg_kefreyt_final_member", settlement)
        self.assertNotIn("VAL_enter_stelander_defeat", settlement)
        self.assertIn("STP_heg_settle_kefreyt_final = yes", peace)
        self.assertIn("on_war_relation_added = {", hegemony_actions)
        self.assertIn("set_country_flag = STP_heg_kefreyt_final_member", hegemony_actions)

    def test_late_hegemony_focuses_are_shorter(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        expected = {
            "STP_pc_heg_nod_break": 3,
            "STP_pc_heg_nod_force": 3,
            "STP_pc_heg_clients": 3,
            "STP_pc_heg_burden": 3,
            "STP_pc_heg_administrations": 3,
            "STP_pc_heg_final_north": 4,
            "STP_pc_heg_final_kefreyt": 4,
        }
        for focus_id, cost in expected.items():
            start = focuses.index(f"id = {focus_id}")
            end = focuses.find("\n\tfocus = {", start)
            block = focuses[start:end if end != -1 else len(focuses)]
            self.assertIn(f"cost = {cost}", block, focus_id)

    def test_hegemony_can_nationalise_without_generic_citizenship_focus(self) -> None:
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        nationalise = named_block(decisions, "STP_pw_nationalise_region")
        self.assertIn("has_completed_focus = STP_pc_heg_administrations", nationalise)
        self.assertIn("has_completed_focus = STP_pw_regional_citizenship", nationalise)

    def test_provisional_administrations_are_closed_and_annexable(self) -> None:
        autonomy = read("common/autonomous_states/ADISCORD_STP_provisional_administration.txt")
        decisions = read("common/decisions/ADISCORD_STP_hegemony_decisions.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertIn("id = autonomy_STP_provisional_administration", autonomy)
        self.assertIn(
            "allowed_levels_filter = {\n\t\tautonomy_STP_provisional_administration\n\t}",
            autonomy,
        )
        for key in ("nod", "ypr", "tff", "val"):
            self.assertIn(f"STP_heg_establish_{key}_administration = {{", decisions)
            self.assertIn(f"STP_heg_annex_{key}_administration = {{", decisions)
        self.assertEqual(decisions.count("days_remove = 90"), 4)
        self.assertEqual(decisions.count("cost = 100"), 4)
        self.assertGreaterEqual(effects.count("autonomy_STP_provisional_administration"), 8)

    def test_defeat_receipts_gate_new_administrations(self) -> None:
        on_actions = read("common/on_actions/11_ADISCORD_STP_hegemony_on_actions.txt")
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")
        self.assertIn("has_country_flag = STP_heg_northern_final_started", on_actions)
        self.assertIn("has_country_flag = STP_heg_kefreyt_final_started", on_actions)
        self.assertIn("set_country_flag = STP_heg_defeated_by_sts", on_actions)
        for name in (
            "STP_heg_nod_administration_available",
            "STP_heg_ypr_administration_available",
            "STP_heg_tff_administration_available",
            "STP_heg_val_administration_available",
        ):
            block = named_block(triggers, name)
            self.assertIn("has_country_flag = STP_heg_administrations_unlocked", block)
            self.assertIn("has_war = no", block)

    def test_ai_path_reaches_new_endgame(self) -> None:
        plans = read("common/ai_strategy_plans/ADISCORD_STP_plans.txt")
        plan = named_block(plans, "STS_shabrat_hegemony_plan")
        sequence = (
            "STP_pc_heg_regional_system",
            "STP_pc_heg_val_force",
            "STP_pc_heg_nod_force",
            "STP_pc_heg_clients",
            "STP_pc_heg_burden",
            "STP_pc_heg_administrations",
            "STP_pc_heg_final_north",
            "STP_pc_heg_final_kefreyt",
        )
        positions = [plan.index(item) for item in sequence]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
