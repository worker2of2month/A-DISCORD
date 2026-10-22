from __future__ import annotations

import re
import unittest
from dataclasses import replace
from pathlib import Path


from tools.lib.paths import source_section
from tools.tests.test_adiscord_stp_preparation import (
    matches_conditions,
    block as parsed_block,
    scalar,
    selected_effects,
)
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


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
                return source[opening_brace + 1 : index]
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

    def test_republic_defeat_follows_the_wartime_country(self) -> None:
        defeated = parse_clausewitz(
            named_block(self.triggers, "ADISCORD_vorkerland_wrk_defeated")
        )
        for exists, capitulated, expected in (
            (True, False, False),
            (True, True, True),
            (False, False, True),
        ):
            with self.subTest(exists=exists, capitulated=capitulated):
                facts = {
                    ("VAD", "country_exists", "WKR"): exists,
                    ("VAD", "country_exists", "WRK"): False,
                    ("WKR", "has_capitulated", "yes"): capitulated,
                }
                self.assertEqual(matches_conditions(defeated, facts, "VAD"), expected)

    def test_human_handoff_queues_continuation_before_invalidating_scope(self) -> None:
        for winner in ("WKR", "VAD", "TVA"):
            with self.subTest(winner=winner):
                formation = parse_clausewitz(named_block(
                    self.effects, f"ADISCORD_vorkerland_form_wrk_from_{winner.lower()}"
                ))
                facts = {(winner, "is_ai", "no"): True}
                actions = list(selected_effects(formation, facts, "WRK"))
                handoff = next(i for i, (_, e) in enumerate(actions) if e.key == "change_tag_from")
                queued = [
                    (scope, scalar(e.value, "id"))
                    for scope, e in actions[:handoff]
                    if e.key == "country_event"
                ]
                self.assertIn(("WRK", "ADISCORD_vorkerland_phase.7"), queued)
                self.assertEqual(actions[handoff + 1:], [])

    def test_a_live_or_liberated_rival_blocks_every_victory_route(self) -> None:
        triggers = {e.key: e.value for e in parse_clausewitz(self.triggers)}

        def expand(items):
            result = []
            for entry in items:
                if entry.key in triggers:
                    self.assertIn(entry.value, ("yes", "no"))
                    result.append(replace(
                        entry,
                        key="AND" if entry.value == "yes" else "NOT",
                        value=expand(triggers[entry.key]),
                    ))
                elif isinstance(entry.value, list):
                    result.append(replace(entry, value=expand(entry.value)))
                else:
                    result.append(entry)
            return result

        routes = {
            "WKR": ("worker", (27, 32, 33, 34, 35, 40, 79, 82)),
            "VAD": ("vlad", (32, 40, 75, 81)),
            "TVA": ("dorian", (32, 40, 36, 37, 38, 39)),
        }
        for winner, (route, states) in routes.items():
            candidate = expand(triggers[f"ADISCORD_vorkerland_{route}_victory_candidate"])
            facts = {(winner, "controls_state", str(state)): True for state in states}
            self.assertTrue(matches_conditions(candidate, facts, winner))
            for rival in routes.keys() - {winner}:
                with self.subTest(winner=winner, rival=rival):
                    facts[(winner, "country_exists", rival)] = True
                    facts[(rival, "has_capitulated", "yes")] = False
                    self.assertFalse(matches_conditions(candidate, facts, winner))
                    facts[(rival, "has_capitulated", "yes")] = True
                    self.assertTrue(matches_conditions(candidate, facts, winner))
                    facts[(rival, "has_capitulated", "yes")] = False
                    self.assertFalse(matches_conditions(candidate, facts, winner))
                    facts[(winner, "country_exists", rival)] = False

    def test_oitfort_handoff_cannot_invalidate_settlement(self) -> None:
        event = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.7"))
        immediate = parsed_block(event, "immediate")
        facts = {
            ("WRK", "is_ai", "yes"): True,
            ("WTD", "exists", "yes"): True,
            ("WTD", "is_ai", "no"): True,
        }
        actions = list(selected_effects(immediate, facts, "WRK"))
        self.assertEqual([e.key for _, e in actions], ["country_event", "change_tag_from"])
        self.assertEqual(scalar(actions[0][1].value, "id"), "ADISCORD_vorkerland_phase.7")
        self.assertEqual(actions[1][1].value, "WTD")
        facts[("WRK", "is_ai", "yes")] = False
        actions = list(selected_effects(immediate, facts, "WRK"))
        self.assertFalse(any(e.key == "change_tag_from" for _, e in actions))
        self.assertEqual(actions[0][1].key, "ADISCORD_vorkerland_finish_delayed_wrk_handoff")

    def test_lost_victory_before_handoff_reopens_the_war_phase(self) -> None:
        event = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.6"))
        facts = {
            ("VAD", "has_global_flag", "ADISCORD_vorkerland_phase_reunification"): True,
            ("VAD", "ADISCORD_vorkerland_coalition_victory_ready", "yes"): False,
        }
        self.assertTrue(matches_conditions(parsed_block(event, "trigger"), facts, "VAD"))
        actions = list(selected_effects(parsed_block(event, "immediate"), facts, "VAD"))
        self.assertIn(("VAD", "ADISCORD_vorkerland_set_phase_central_showdown"), [
            (scope, e.key) for scope, e in actions
        ])
        self.assertFalse(any(e.key in ("transfer_state", "change_tag_from", "annex_country") for _, e in actions))

    def test_all_routes_annex_claimants_oitfort_and_zshat_with_troop_transfer(self) -> None:
        effects = {e.key: e.value for e in parse_clausewitz(self.effects)}
        for winner, route in (("WKR", "worker"), ("VAD", "joint"), ("TVA", "utilitarian")):
            with self.subTest(winner=winner):
                facts = {
                    ("WRK", "has_country_flag", f"ADISCORD_vorkerland_route_{route}"): True,
                    ("EGC", "has_country_flag", "ADISCORD_vorkerland_prep_treaty_signed"): True,
                }
                for tag in ("WKR", "VAD", "TVA", "WTD", "EGC"):
                    facts[("WRK", "country_exists", tag)] = True
                dispatch = list(selected_effects(
                    effects["ADISCORD_vorkerland_finish_delayed_wrk_handoff"], facts, "WRK"
                ))
                self.assertEqual([e.key for _, e in dispatch], [
                    f"ADISCORD_vorkerland_complete_wrk_from_{winner.lower()}"
                ])
                actions = list(selected_effects(effects[dispatch[0][1].key], facts, "WRK"))
                expanded = []
                for scope, entry in actions:
                    if entry.key in (
                        "ADISCORD_vorkerland_absorb_wtd_after_reunification",
                        "ADISCORD_vorkerland_absorb_egc_after_reunification",
                    ):
                        expanded.extend(selected_effects(effects[entry.key], facts, scope))
                    else:
                        expanded.append((scope, entry))
                annexations = []
                for scope, entry in expanded:
                    self.assertNotEqual(entry.key, "change_tag_from")
                    if entry.key == "annex_country":
                        self.assertEqual(scope, "WRK")
                        self.assertEqual(scalar(entry.value, "transfer_troops"), "yes")
                        annexations.append(scalar(entry.value, "target"))
                self.assertCountEqual(annexations, ["WKR", "VAD", "TVA", "WTD", "EGC"])

    def test_zshat_player_handoff_precedes_annexation(self) -> None:
        event = parse_clausewitz(event_block(self.events, "ADISCORD_vorkerland_phase.7"))
        facts = {
            ("WRK", "is_ai", "yes"): True,
            ("EGC", "exists", "yes"): True,
            ("EGC", "is_ai", "no"): True,
        }
        actions = list(selected_effects(parsed_block(event, "immediate"), facts, "WRK"))
        self.assertEqual([e.key for _, e in actions], ["country_event", "change_tag_from"])
        self.assertEqual(scalar(actions[0][1].value, "id"), "ADISCORD_vorkerland_phase.7")
        self.assertEqual(actions[1][1].value, "EGC")
        facts[("WRK", "is_ai", "yes")] = False
        actions = list(selected_effects(parsed_block(event, "immediate"), facts, "WRK"))
        self.assertFalse(any(e.key == "change_tag_from" for _, e in actions))
        self.assertEqual(actions[0][1].key, "ADISCORD_vorkerland_finish_delayed_wrk_handoff")

    def test_zshat_settlement_controls_owned_districts_and_skips_absent_country(self) -> None:
        effect = parse_clausewitz(named_block(
            self.effects, "ADISCORD_vorkerland_absorb_egc_after_reunification"
        ))
        facts = {
            ("WRK", "country_exists", "EGC"): True,
            ("81", "is_owned_by", "WRK"): True,
            ("110", "is_owned_by", "WRK"): True,
            ("124", "is_owned_by", "WRK"): False,
        }
        actions = list(selected_effects(effect, facts, "WRK"))
        self.assertEqual(
            [(scope, entry.value) for scope, entry in actions if entry.key == "set_state_controller_to"],
            [("81", "WRK"), ("110", "WRK")],
        )
        self.assertIn("ADISCORD_economy_mark_dirty", [entry.key for _, entry in actions])
        facts[("WRK", "country_exists", "EGC")] = False
        self.assertEqual(list(selected_effects(effect, facts, "WRK")), [])

    def test_surviving_zshat_blocks_terminal_verification(self) -> None:
        gate = parse_clausewitz(named_block(
            self.triggers, "ADISCORD_vorkerland_reunification_verified"
        ))
        facts = {
            ("WRK", "country_exists", "WRK"): True,
            ("WRK", "is_subject", "no"): True,
            ("WRK", "controls_state", "32"): True,
            ("WRK", "has_country_flag", "ADISCORD_vorkerland_route_joint"): True,
            ("32", "is_owned_by", "WRK"): True,
            ("32", "is_controlled_by", "WRK"): True,
        }
        self.assertTrue(matches_conditions(gate, facts, "WRK"))
        facts[("WRK", "country_exists", "EGC")] = True
        self.assertFalse(matches_conditions(gate, facts, "WRK"))

    def test_worker_victory_is_checked_on_the_living_claimant(self) -> None:
        candidate = named_block(
            self.triggers, "ADISCORD_vorkerland_worker_victory_candidate"
        )
        self.assertRegex(candidate, r"(?m)^\s*tag = WKR\s*$")
        self.assertNotRegex(candidate, r"(?m)^\s*tag = WRK\s*$")

    def test_reunification_dispatch_does_not_use_the_callback_country(self) -> None:
        dispatch = named_block(
            self.effects, "ADISCORD_vorkerland_begin_reunification"
        )
        outer = named_block(dispatch, "if")
        gate = named_block(outer, "limit")
        self.assertIn(
            "NOT = { has_global_flag = ADISCORD_vorkerland_phase_reunification }",
            gate,
        )
        event = "country_event = { id = ADISCORD_vorkerland_phase.6 days = 1 }"
        branches = re.findall(r"\b(?:if|else_if)\s*=\s*\{", outer)
        self.assertEqual(len(branches), 3)
        normalized = " ".join(outer.split())
        for tag in ("WKR", "VAD", "TVA"):
            self.assertIn(
                f"{tag} = {{ exists = yes is_subject = no NOT = {{ has_capitulated = yes }} }}",
                normalized,
            )
            self.assertIn(f"{tag} = {{ {event} }}", outer)
        self.assertEqual(outer.count(event), 3)

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
                completion = named_block(
                    self.effects,
                    f"ADISCORD_vorkerland_complete_wrk_from_{suffix}",
                )
                block += completion
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

                self.assertLess(
                    block.index("transfer_state = 32"), block.index(route_character)
                )
                self.assertLess(
                    block.index(route_character),
                    block.index(f"change_tag_from = {winner}"),
                )
                self.assertLess(
                    block.index(f"change_tag_from = {winner}"),
                    block.index(winner_annex),
                )
                self.assertLess(
                    block.index(winner_annex),
                    block.index("ADISCORD_vorkerland_finalize_wrk_formation"),
                )

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
                actions = list(selected_effects(parse_clausewitz(formation), {}, "WRK"))
                removals = [(scope, e.value) for scope, e in actions if e.key == "remove_ideas"]
                for idea in ideas:
                    token = f"remove_ideas = {idea}"
                    self.assertIn((tag, idea), removals)
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
            0,
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
                effect = named_block(read(PHASE_EFFECTS), effect_name)
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
        tva = named_block(self.effects, "ADISCORD_vorkerland_complete_wrk_from_tva")
        self.assertIn("country_exists = TGD", tva)
        self.assertIn("ADISCORD_vorkerland_joined_worx_directorate", tva)
        self.assertIn("puppet = TGD", tva)
        self.assertIn("freedom_level = 0.10", tva)
        self.assertIn("ADISCORD_vorkerland_absorb_wtd_after_reunification = yes", tva)
        self.assertNotIn("puppet = WTD", tva)
        self.assertNotIn("freedom_level = 0.15", tva)

    def test_worx_formation_preserves_claimant_colour(self) -> None:
        tva = named_block(self.effects, "ADISCORD_vorkerland_complete_wrk_from_tva")
        cosmetic = "WRK_vorkerland_technocracy"
        self.assertGreater(
            tva.index(f"set_cosmetic_tag = {cosmetic}"),
            tva.index("ADISCORD_vorkerland_finalize_wrk_formation = yes"),
        )
        palette = named_block(read(ROOT / "common/countries/cosmetic.txt"), cosmetic)
        original = read(ROOT / "common/countries/TVA.txt")
        colour = re.search(r"color\s*=\s*rgb\s*\{[^}]+\}", original).group()
        self.assertIn(colour, palette)

    def test_no_random_lucas_contract_leaks_into_formation(self) -> None:
        self.assertNotIn("Lucas", self.effects)
        self.assertNotIn("Lucas", self.events)


if __name__ == "__main__":
    unittest.main()
