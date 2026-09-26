from __future__ import annotations

import re
import unittest
from pathlib import Path


from tools.lib.paths import source_section


ROOT = Path(__file__).resolve().parents[2]
PHASE_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
PHASE_EVENTS = ROOT / "events/ADISCORD_vorkerland_events.txt"
PHASE_TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def balanced_block(source: str, opening_brace: int) -> str:
    depth = 0
    for index in range(opening_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[opening_brace + 1:index]
    raise AssertionError("unterminated Clausewitz block")


def named_block(source: str, name: str) -> str:
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", source)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    return balanced_block(source, source.find("{", match.start()))


def event_block(source: str, event_id: str) -> str:
    id_match = re.search(rf"(?m)^\s*id\s*=\s*{re.escape(event_id)}\s*$", source)
    if id_match is None:
        raise AssertionError(f"missing event: {event_id}")
    event_start = source.rfind("country_event", 0, id_match.start())
    opening_brace = source.find("{", event_start, id_match.start())
    return balanced_block(source, opening_brace)


class ReunifiedWrkDestinationScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.effects = source_section(read(PHASE_EFFECTS), 'phase_effects')
        cls.events = source_section(read(PHASE_EVENTS), 'phase_events')
        cls.triggers = read(PHASE_TRIGGERS)

    def test_each_winner_is_consumed_by_materialized_wrk(self) -> None:
        contracts = (
            ("wkr", "WKR", "WRK_Nikita_Worcker"),
            ("vad", "VAD", "WRK_VAD_Joint_Council"),
            ("tva", "TVA", "TVA_Dorian_Worx"),
        )
        for suffix, winner, route_character in contracts:
            with self.subTest(winner=winner):
                block = named_block(
                    self.effects,
                    f"ADISCORD_vorkerland_form_wrk_from_{suffix}",
                )
                normalized = " ".join(block.split())
                human_guard = (
                    f"if = {{ limit = {{ {winner} = {{ is_ai = no }} }} "
                    f"change_tag_from = {winner} }}"
                )
                winner_annex = (
                    f"annex_country = {{ target = {winner} transfer_troops = yes }}"
                )

                self.assertEqual(block.count("transfer_state = 32"), 1)
                self.assertIn("set_state_controller_to = WRK", block)
                self.assertIn(f"inherit_technology = {winner}", block)
                self.assertIn(f"copy_completed_from = {winner}", block)
                self.assertIn(route_character, block)
                self.assertIn(human_guard, normalized)
                self.assertEqual(block.count(f"change_tag_from = {winner}"), 1)
                self.assertEqual(normalized.count(winner_annex), 1)
                self.assertIn("focus_unlock = yes", block)
                self.assertIn("mark_focus_tree_layout_dirty = yes", block)

                self.assertLess(block.index("transfer_state = 32"), block.index(route_character))
                self.assertLess(block.index(route_character), block.index(f"change_tag_from = {winner}"))
                self.assertLess(block.index(f"change_tag_from = {winner}"), block.index(winner_annex))
                self.assertLess(block.index(winner_annex), block.index("ADISCORD_vorkerland_finalize_wrk_formation"))

    def test_worker_route_uses_authored_anton_fallback(self) -> None:
        block = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_wkr")
        self.assertIn("ADISCORD_vorkerland_worker_safe_with_loyalists", block)
        self.assertIn("WRK_Nikita_Worcker", block)
        self.assertIn("WRK_Anton_Bagley", block)
        self.assertNotIn("WKR_Worker_Emergency_Presidium", block)
        self.assertNotIn("Lucas", block)

    def test_rescued_worker_and_route_leaders_follow_their_winners(self) -> None:
        vad = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_vad")
        tva = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        self.assertIn("ADISCORD_vorkerland_worker_rescued_by_vlad", vad)
        self.assertIn("character = WRK_Nikita_Worcker", vad)
        self.assertIn("character = WRK_VAD_Joint_Council", vad)
        self.assertIn("character = TVA_Dorian_Worx", tva)

    def test_claimant_war_command_spirits_expire_before_formation_handoff(self) -> None:
        contracts = {
            "WKR": (
                "ADISCORD_vorkerland_wkr_front_operations_bureau",
                "ADISCORD_vorkerland_wkr_republican_mission_commands",
                "ADISCORD_vorkerland_wkr_normative_campaign_tables",
            ),
            "VAD": (
                "ADISCORD_vorkerland_vad_restoration_war_cabinet_2",
                "ADISCORD_vorkerland_vad_dual_authority_protocol_2",
            ),
        }
        for tag, ideas in contracts.items():
            with self.subTest(tag=tag):
                formation = named_block(
                    self.effects,
                    f"ADISCORD_vorkerland_form_wrk_from_{tag.lower()}",
                )
                source_scope = named_block(formation, tag)
                for idea in ideas:
                    token = f"remove_ideas = {idea}"
                    self.assertIn(token, source_scope)
                    self.assertLess(
                        formation.index(token),
                        formation.index(f"change_tag_from = {tag}"),
                    )

    def test_phase_six_runs_all_three_formations_from_wrk_scope(self) -> None:
        phase_six = event_block(self.events, "ADISCORD_vorkerland_phase.6")
        self.assertEqual(
            phase_six.count(
                "country_event = { id = ADISCORD_vorkerland_phase.7 days = 1 }"
            ),
            3,
        )
        for suffix, old_scope in (("wkr", "WKR"), ("vad", "VAD"), ("tva", "TVA")):
            effect = f"ADISCORD_vorkerland_form_wrk_from_{suffix} = yes"
            with self.subTest(winner=old_scope):
                self.assertIn(f"WRK = {{\n\t\t\t\t{effect}", phase_six)
                self.assertNotIn(f"{old_scope} = {{\n\t\t\t\t{effect}", phase_six)

    def test_phase_six_prefers_the_marked_winner_over_tag_order(self) -> None:
        phase_six = event_block(self.events, "ADISCORD_vorkerland_phase.6")
        self.assertEqual(
            phase_six.count("ADISCORD_vorkerland_has_live_marked_central_unifier = no"),
            3,
        )
        for tag in ("WKR", "VAD", "TVA"):
            with self.subTest(winner=tag):
                self.assertRegex(
                    phase_six,
                    rf"{tag}\s*=\s*\{{\s*has_country_flag\s*=\s*ADISCORD_vorkerland_central_unifier\s*\}}",
                )
        marker = named_block(
            self.triggers, "ADISCORD_vorkerland_has_live_marked_central_unifier"
        )
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(
                f"{tag} = {{ exists = yes is_subject = no NOT = {{ has_capitulated = yes }} "
                "has_country_flag = ADISCORD_vorkerland_central_unifier }",
                marker,
            )

    def test_terminal_winner_replaces_stale_unifier_markers(self) -> None:
        contracts = {
            "ADISCORD_vorkerland_apply_worker_map": ("WKR", ("VAD", "TVA")),
            "ADISCORD_vorkerland_apply_vlad_map": ("VAD", ("WKR", "TVA")),
            "ADISCORD_vorkerland_apply_dorian_map": ("TVA", ("WKR", "VAD")),
        }
        for effect_name, (winner, losers) in contracts.items():
            with self.subTest(effect=effect_name):
                effect = named_block(self.effects, effect_name)
                self.assertRegex(
                    effect,
                    rf"{winner}\s*=\s*\{{[\s\S]*?set_country_flag\s*=\s*ADISCORD_vorkerland_central_unifier",
                )
                for loser in losers:
                    self.assertIn(
                        f"country_exists = {loser} }} {loser} = {{ clr_country_flag = "
                        "ADISCORD_vorkerland_central_unifier",
                        effect,
                    )

    def test_tva_formation_rebinds_tgd_but_absorbs_oitfort(self) -> None:
        tva = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        self.assertIn("country_exists = TGD", tva)
        self.assertIn("ADISCORD_vorkerland_joined_worx_directorate", tva)
        self.assertIn("puppet = TGD", tva)
        self.assertIn("freedom_level = 0.10", tva)
        self.assertIn("ADISCORD_vorkerland_absorb_wtd_after_reunification = yes", tva)
        self.assertNotIn("puppet = WTD", tva)
        self.assertNotIn("freedom_level = 0.15", tva)

    def test_worx_formation_preserves_claimant_colour(self) -> None:
        tva = named_block(self.effects, "ADISCORD_vorkerland_form_wrk_from_tva")
        cosmetic = "WRK_vorkerland_technocracy"
        self.assertGreater(tva.index(f"set_cosmetic_tag = {cosmetic}"),
                           tva.index("ADISCORD_vorkerland_finalize_wrk_formation = yes"))
        palette = named_block(read(ROOT / "common/countries/cosmetic.txt"), cosmetic)
        original = read(ROOT / "common/countries/TVA.txt")
        colour = re.search(r"color\s*=\s*rgb\s*\{[^}]+\}", original).group()
        self.assertIn(colour, palette)

    def test_no_random_lucas_contract_leaks_into_formation(self) -> None:
        self.assertNotIn("Lucas", self.effects)
        self.assertNotIn("Lucas", self.events)


if __name__ == "__main__":
    unittest.main()
