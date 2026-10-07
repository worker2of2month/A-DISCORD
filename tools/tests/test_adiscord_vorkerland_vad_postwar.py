from __future__ import annotations

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return read_focus_source(ROOT / relative, encoding="utf-8-sig")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if not match:
        return ""
    start = source.find("{", match.start())
    depth = 0
    for index in range(start, len(source)):
        character = source[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return source[match.start() : index + 1]
    return ""


class VadPostwarContractTests(unittest.TestCase):
    def test_restored_and_voluntary_sol_remain_subjects_after_handoff(
        self,
    ) -> None:
        source = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            'phase_effects',
        )
        formation = named_block(source, "ADISCORD_vorkerland_form_wrk_from_vad")
        self.assertTrue(formation)

        restored = re.search(
            r"(?s)if\s*=\s*\{\s*limit\s*=\s*\{[^{}]*"
            r"has_global_flag\s*=\s*ADISCORD_vorkerland_sol_restoration_verified"
            r".*?\n\s*\}\s*\n\s*else_if\s*=",
            formation,
        )
        self.assertIsNotNone(restored)
        restored_block = restored.group(0)
        self.assertIn("puppet = SOL", restored_block)
        self.assertIn("autonomy_state = autonomy_puppet", restored_block)
        self.assertIn("add_to_faction = SOL", restored_block)

        voluntary = formation[restored.end() - len("else_if =") :]
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_vad_sol_alliance_accepted", voluntary
        )
        self.assertIn("add_to_faction = SOL", voluntary)
        self.assertIn("puppet = SOL", voluntary)
        self.assertIn("autonomy_state = autonomy_puppet", voluntary)
        detach = formation.index("autonomy_state = autonomy_free")
        annex = formation.index("annex_country = { target = VAD")
        rebind = formation.index("puppet = SOL")
        self.assertLess(detach, annex)
        self.assertLess(annex, rebind)

    def test_destroyed_sol_returns_as_administration_with_velin_and_overlord_colour(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        restoration = named_block(effects, "ADISCORD_vorkerland_restore_sol_as_vad_puppet")
        self.assertIn("104 = { add_core_of = SOL }", restoration)
        self.assertIn("transfer_state = 104", restoration)
        self.assertIn("set_cosmetic_tag = SOL_vorkerland_restoration_administration", restoration)
        self.assertIn("autonomy_state = autonomy_puppet", restoration)
        self.assertIn("use_overlord_color = yes", read("common/autonomous_states/puppet.txt"))
        verification = named_block(effects, "ADISCORD_vorkerland_verify_sol_restoration")
        self.assertIn("owns_state = 104 controls_state = 104", verification)
        self.assertIn("ADISCORD_vorkerland_sync_independence_cosmetic = yes", verification)
        cosmetics = named_block(effects, "ADISCORD_vorkerland_sync_independence_cosmetic")
        self.assertIn("is_subject_of = VAD", cosmetics)
        self.assertIn("WRK = { has_country_flag = ADISCORD_vorkerland_route_joint }", cosmetics)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_restored_by_vad", cosmetics)
        self.assertLess(
            cosmetics.index("set_cosmetic_tag = SOL_vorkerland_restoration_administration"),
            cosmetics.index("set_cosmetic_tag = SOL_vorkerland_worker_protectorate"),
        )

    def test_sol_acceptance_subordinates_only_with_its_choice(self) -> None:
        events = read("events/ADISCORD_vorkerland_events.txt")
        start = events.index("id = ADISCORD_vorkerland_diplomacy.2\n")
        end = events.index("\ncountry_event = {", start)
        event = events[start:end]
        acceptance = named_block(event, "option")
        self.assertIn("puppet = SOL", acceptance)
        self.assertIn("autonomy_state = autonomy_puppet", acceptance)
        decline = event[event.index("name = ADISCORD_vorkerland_diplomacy.2.b"):]
        self.assertNotIn("puppet =", decline)
        self.assertNotIn("set_autonomy", decline)

    def test_vlad_capstone_keeps_empire_while_joint_council_drops_temporary_cosmetic(
        self,
    ) -> None:
        source = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )
        match = re.search(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*WRK_joint_impose_reunification_settlement\b",
            source,
        )
        self.assertIsNotNone(match)
        focus = named_block(source[match.start() :], "focus")
        reward = named_block(focus, "completion_reward")
        self.assertEqual(reward.count("drop_cosmetic_tag = yes"), 1)
        self.assertIn(
            "has_global_flag = ADISCORD_vorkerland_joint_government_formed", reward
        )
        self.assertIn("set_cosmetic_tag = VAD_vorkerland_restoration", reward)
        self.assertIn("character = WRK_Vlad_Petrichev", reward)
        self.assertIn("civilian = { large = GFX_portrait_WRK_Vlad_Petrichev }", reward)
        self.assertIn("portrait = GFX_portrait_WRK_Vlad_Petrichev\n", reward)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", reward)
        self.assertIn(
            "add_ideas = ADISCORD_vorkerland_reunification_settlement", reward
        )

    def test_vlad_postwar_route_unlocks_sequential_imperial_reclamation(self) -> None:
        focuses = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )
        match = re.search(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*WRK_joint_issue_integration_warrants\b",
            focuses,
        )
        self.assertIsNotNone(match)
        warrants = named_block(focuses[match.start() :], "focus")
        self.assertIn(
            "unlock_decision_tooltip = ADISCORD_vorkerland_vad_continue_imperial_reunification",
            warrants,
        )
        self.assertIn(
            "set_country_flag = ADISCORD_vorkerland_vad_imperial_reclamation_unlocked",
            warrants,
        )

        decisions = read("common/decisions/ADISCORD_vorkerland_decisions.txt")
        reclaim = named_block(
            decisions, "ADISCORD_vorkerland_vad_continue_imperial_reunification"
        )
        self.assertTrue(reclaim)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_route_joint", reclaim)
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }",
            reclaim,
        )
        self.assertIn("has_war = no", reclaim)
        self.assertIn("days_re_enable = 14", reclaim)
        self.assertIn("fire_only_once = no", reclaim)
        self.assertIn(
            "ADISCORD_vorkerland_continue_imperial_reunification = yes", reclaim
        )
        dispatch = named_block(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "ADISCORD_vorkerland_continue_imperial_reunification",
        )
        for tag in ("EYR", "EGC", "VLA", "ROM", "ZTA", "TGD"):
            self.assertIn(
                f"declare_war_on = {{ target = {tag} type = annex_everything }}",
                dispatch,
            )

    def test_reunified_vlad_keeps_empire_unless_the_rare_council_formed(self) -> None:
        source = source_section(
            read("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "phase_effects",
        )
        formation = named_block(source, "ADISCORD_vorkerland_form_wrk_from_vad")
        identity = re.search(
            r"(?s)if\s*=\s*\{\s*limit\s*=\s*\{(?P<limit>[^{}]*)\}\s*"
            r"set_cosmetic_tag\s*=\s*WRK_vorkerland_joint_government\s*"
            r"ADISCORD_vorkerland_appoint_joint_council\s*=\s*yes\s*\}"
            r"\s*else\s*=\s*\{(?P<else>.*?portrait\s*=\s*GFX_portrait_WRK_Vlad_Petrichev)\s",
            formation,
        )
        self.assertIsNotNone(identity)
        self.assertIn(
            "ADISCORD_vorkerland_joint_government_formed", identity.group("limit")
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_worker_rescued_by_vlad", identity.group("limit")
        )
        self.assertIn(
            "set_cosmetic_tag = VAD_vorkerland_restoration", identity.group("else")
        )
        self.assertIn("character = WRK_Vlad_Petrichev", identity.group("else"))
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_joint_government_formed }",
            formation,
        )
        self.assertIn("character = WRK_Vlad_Petrichev", formation)
        self.assertIn("character = WRK_Nikita_Worcker", formation)
        self.assertIn("civilian = { large = GFX_portrait_WRK_Vlad_Petrichev }", formation)
        self.assertNotIn("GFX_portrait_WRK_Vlad_Petrichev_civilwar", formation)

    def test_joint_council_gets_specific_victory_text_before_vlad_fallback(
        self,
    ) -> None:
        scripted = read(
            "common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt"
        )
        for suffix in ("title", "quote", "comment"):
            joint_key = f"superevent_vorkerland_joint_victory_{suffix}"
            vlad_key = f"superevent_vorkerland_vlad_victory_{suffix}"
            self.assertEqual(scripted.count(f"localization_key = {joint_key}"), 1)
            self.assertLess(scripted.index(joint_key), scripted.index(vlad_key))

        for path in (
            "localisation/english/ADISCORD_superevents_l_english.yml",
            "localisation/russian/ADISCORD_superevents_l_russian.yml",
        ):
            localisation = read(path)
            for suffix in ("title", "quote", "comment"):
                self.assertIn(
                    f"superevent_vorkerland_joint_victory_{suffix}:", localisation
                )

        russian = ROOT / "localisation/russian/ADISCORD_superevents_l_russian.yml"
        self.assertTrue(russian.read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_joint_council_ai_prefers_chancery_over_commandantures(self) -> None:
        source = source_section(
            read("common/national_focus/ADISCORD_vorkerland_focus.txt"),
            'civil_war_focus',
        )

        def focus(focus_id: str) -> str:
            match = re.search(
                rf"(?ms)^\s*focus\s*=\s*\{{\s*id\s*=\s*{re.escape(focus_id)}\b",
                source,
            )
            self.assertIsNotNone(match)
            return named_block(source[match.start() :], "focus")

        registers_ai = named_block(focus("VAD_open_imperial_registers"), "ai_will_do")
        command_ai = named_block(focus("VAD_form_field_commandantures"), "ai_will_do")
        flag = "has_global_flag = ADISCORD_vorkerland_joint_government_formed"
        self.assertIn(flag, registers_ai)
        self.assertIn("factor = 2", registers_ai)
        self.assertIn(flag, command_ai)
        self.assertIn("factor = 0.5", command_ai)


if __name__ == "__main__":
    unittest.main()
