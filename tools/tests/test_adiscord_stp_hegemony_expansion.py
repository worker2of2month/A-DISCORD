from __future__ import annotations

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source
from tools.tests.test_adiscord_peace_coalition_lifecycle import TreatyFixture
from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    path = ROOT / relative
    return read_focus_source(
        path, encoding="utf-8-sig" if path.suffix == ".yml" else "utf-8"
    )


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
                return text[match.start() : index + 1]
    raise AssertionError(f"unclosed block {name}")


class ShabratHegemonyExpansionTests(unittest.TestCase):
    def test_administration_flags_follow_both_country_creation_paths(self):
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        for tag in ("NOD", "VAL", "YPR", "TFF"):
            with self.subTest(tag=tag):
                preparation = named_block(
                    effects, f"STP_heg_prepare_{tag.lower()}_administration"
                )
                self.assertEqual(
                    preparation.count(f"set_cosmetic_tag = {tag}_STS_administration"),
                    2,
                )

    def test_administration_flag_cleanup_preserves_other_political_routes(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        cleanup = block(effects, "STP_heg_clear_foreign_administration_flag")
        self.assertTrue(cleanup)
        for tag in ("NOD", "VAL", "YPR", "TFF"):
            for overlord in ("STS", "STP", None):
                for cosmetic in (
                    f"{tag}_STS_administration", f"{tag}_STP_revolution", "other"
                ):
                    with self.subTest(tag=tag, overlord=overlord, cosmetic=cosmetic):
                        facts = {
                            (tag, "is_subject_of", "STS"): overlord == "STS",
                            (tag, "has_cosmetic_tag", cosmetic): True,
                        }
                        result = [
                            e.key for _, e in selected_effects(cleanup, facts, tag)
                        ]
                        self.assertEqual(
                            "drop_cosmetic_tag" in result,
                            overlord != "STS" and cosmetic == f"{tag}_STS_administration",
                        )
        actions = read("common/on_actions/02_ADISCORD_STP_on_actions.txt")
        for hook in ("on_puppet", "on_release_as_puppet", "on_subject_free"):
            self.assertIn(
                "STP_heg_clear_foreign_administration_flag = yes",
                named_block(actions, hook),
            )

    def test_shabrat_route_focuses_swap_portraits_immediately(self) -> None:
        gfx = read("interface/ADISCORD_leader_portraits.gfx")
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")

        self.assertIn('name = "GFX_portrait_STP_Maksim_Shabrat_hegemony"', gfx)
        self.assertIn(
            'texturefile = "gfx/leaders/STP/portrait_STP_Maksim_Shabrat_uniform.png"',
            gfx,
        )
        self.assertIn('name = "GFX_portrait_STP_Maksim_Shabrat_freedom"', gfx)
        self.assertIn(
            'texturefile = "gfx/leaders/STP/portrait_STP_Maksim_Shabrat_alternative.png"',
            gfx,
        )

        hegemony = re.search(
            r"(?ms)id = STP_pc_hegemony_open\b.*?(?=\n\tfocus = \{)", focuses
        )
        freedom = re.search(
            r"(?ms)id = STP_pc_freedom_open\b.*?(?=\n\tfocus = \{)", focuses
        )
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

    def test_all_in_icon_is_shared_by_the_two_high_stakes_focuses(self) -> None:
        stp = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        val = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        gfx = read("interface/ADISCORD_national_focus.gfx")
        shine = read("interface/ADISCORD_focus_shines.gfx")

        self.assertRegex(
            stp,
            r"(?s)id = STP_pc_heg_final_kefreyt\b.*?icon = GFX_focus_ADISCORD_All_In",
        )
        self.assertRegex(
            val,
            r"(?s)id = VAL_October_Of_2160\b.*?icon = GFX_focus_ADISCORD_All_In",
        )
        self.assertIn(
            'texturefile = "gfx/interface/goals/_shared/GFX_focus_ADISCORD_All_In.png"',
            gfx,
        )
        self.assertIn('name = "GFX_focus_ADISCORD_All_In_shine"', shine)
        self.assertTrue(
            (
                ROOT / "gfx/interface/goals/_shared/GFX_focus_ADISCORD_All_In.png"
            ).is_file()
        )
        self.assertFalse(
            (ROOT / "gfx/interface/goals/_spare/STP/GFX_focus_STP_All_In.png").exists()
        )

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
            self.assertIn(
                f"declare_war_on = {{ target = {tag} type = annex_everything }}", north
            )
        self.assertNotIn("target = VAL", north)
        kefreyt = named_block(effects, "STP_heg_start_kefreyt_final_war")
        self.assertIn(
            "declare_war_on = { target = VAL type = annex_everything }", kefreyt
        )
        resolved = named_block(triggers, "STP_heg_northern_final_resolved")
        for tag in ("NOD", "YPR", "TFF"):
            self.assertIn(f"NOT = {{ has_war_with = {tag} }}", resolved)

    def test_nod_acceptance_preserves_a_separate_puppet(self) -> None:
        events = read("events/ADISCORD_STP_events.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        self.assertIn("set_country_flag = STP_pc_nod_client_pending", events)
        finalizer = named_block(effects, "STP_pc_finalize_nod_client_subject")
        self.assertIn("puppet = NOD", finalizer)
        self.assertIn("autonomy_state = autonomy_puppet", finalizer)
        self.assertNotIn("STP_heg_annex_nod_administration", decisions)

    def test_second_kefreyt_war_uses_distinct_scripted_peace(self) -> None:
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        peace = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        hegemony_actions = read(
            "common/on_actions/11_ADISCORD_STP_hegemony_on_actions.txt"
        )
        settlement = named_block(effects, "STP_heg_settle_kefreyt_final")
        self.assertIn("STP_pc_recover_stelander_cores_from_val = yes", settlement)
        self.assertIn("every_enemy_country = {", settlement)
        self.assertIn("has_country_flag = STP_heg_kefreyt_final_member", settlement)
        self.assertNotIn("VAL_enter_stelander_defeat", settlement)
        self.assertIn("STP_heg_settle_kefreyt_final = yes", peace)
        self.assertIn("on_war_relation_added = {", hegemony_actions)
        self.assertIn(
            "set_country_flag = STP_heg_kefreyt_final_member", hegemony_actions
        )

    def test_final_kefreyt_victory_subordinates_the_surviving_government(self):
        self.assert_final_administration("VAL", "STP_heg_settle_kefreyt_final")

    def test_final_nod_victory_subordinates_the_surviving_government(self):
        self.assert_final_administration("NOD", "STP_pc_begin_settlement")

    def assert_final_administration(self, opponent, effect_name):
        from tools.tests.test_adiscord_stp_preparation import (
            entries,
            scalar,
            selected_effects,
        )

        effects = {
            e.key: e.value
            for e in entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        }
        final_flag = {
            "VAL": "STP_heg_kefreyt_final_started",
            "NOD": "STP_heg_northern_final_started",
        }[opponent]
        for final_campaign in (False, True):
            with self.subTest(opponent=opponent, final_campaign=final_campaign):
                facts = {
                    ("STS", "has_country_flag", final_flag): final_campaign,
                    ("STS", "has_war_with", opponent): True,
                    ("STS", "variable", "STP_pc_cap_side"): 2,
                    (opponent, "exists", "yes"): True,
                }
                outcomes = []

                def run(items, scope="STS"):
                    for country, entry in selected_effects(items, facts, scope):
                        if entry.key.startswith("STP_heg_prepare_"):
                            run(effects[entry.key], country)
                        elif entry.key == "white_peace":
                            facts[(country, "has_war_with", entry.value)] = False
                            facts[(entry.value, "has_war_with", country)] = False
                        elif entry.key == "set_autonomy":
                            self.assertFalse(facts[("STS", "has_war_with", opponent)])
                            outcomes.append(
                                (
                                    country,
                                    scalar(entry.value, "target"),
                                    scalar(entry.value, "autonomy_state"),
                                )
                            )

                run(effects[effect_name])
                self.assertEqual(
                    outcomes,
                    [("STS", opponent, "autonomy_STP_provisional_administration")]
                    if final_campaign else [],
                    "A final military victory must change the surviving government's status",
                )

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
            block = focuses[start : end if end != -1 else len(focuses)]
            self.assertIn(f"cost = {cost}", block, focus_id)

    def test_hegemony_can_nationalise_without_generic_citizenship_focus(self) -> None:
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        nationalise = named_block(decisions, "STP_pw_nationalise_region")
        self.assertIn("has_completed_focus = STP_pc_heg_administrations", nationalise)
        self.assertIn("has_completed_focus = STP_pw_regional_citizenship", nationalise)

    def test_provisional_administrations_keep_their_territory(self) -> None:
        autonomy = read(
            "common/autonomous_states/ADISCORD_STP_provisional_administration.txt"
        )
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.assertIn("id = autonomy_STP_provisional_administration", autonomy)
        self.assertIn(
            "allowed_levels_filter = {\n\t\tautonomy_STP_provisional_administration\n\t}",
            autonomy,
        )
        for key in ("nod", "ypr", "tff", "val"):
            self.assertIn(f"STP_heg_establish_{key}_administration = {{", decisions)
            self.assertNotIn(f"STP_heg_annex_{key}_administration", decisions)
            self.assertNotIn(f"STP_heg_{key}_integrated", decisions)
        self.assertNotIn("annex_country", named_block(decisions, "STP_hegemony_administration"))
        self.assertIn("can_lose_level = { always = no }", autonomy)
        self.assertGreaterEqual(
            effects.count("autonomy_STP_provisional_administration"), 8
        )

    def test_defeat_receipts_gate_new_administrations(self) -> None:
        on_actions = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
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

    def test_ai_resolves_bezhaysk_and_nodrul_before_kefreyt(self) -> None:
        focuses = read("common/national_focus/ADISCORD_national_focus_STP.txt")
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
        triggers = read("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt")

        bezhaysk = re.search(
            r"(?ms)id = STP_pw_take_bezhaysk\b.*?(?=\n\tfocus = \{)", focuses
        )
        nodrul = re.search(
            r"(?ms)id = STP_pc_heg_nod_break\b.*?(?=\n\tfocus = \{)", focuses
        )
        kefreyt = re.search(
            r"(?ms)id = STP_pc_heg_val_audit\b.*?(?=\n\tfocus = \{)", focuses
        )
        self.assertIsNotNone(bezhaysk)
        self.assertIsNotNone(nodrul)
        self.assertIsNotNone(kefreyt)
        self.assertIn("ai_will_do = { base = 20 }", bezhaysk.group(0))
        self.assertIn("STP_shabrat_ai_bezhaysk_resolved = yes", nodrul.group(0))
        self.assertIn("STP_shabrat_ai_bezhaysk_resolved = yes", kefreyt.group(0))
        self.assertIn("STP_shabrat_ai_nodrul_resolved = yes", kefreyt.group(0))

        self.assertTrue(named_block(triggers, "STP_shabrat_ai_bezhaysk_resolved"))
        self.assertTrue(named_block(triggers, "STP_shabrat_ai_nodrul_resolved"))

        prepare_nod = named_block(decisions, "STP_pw_prepare_nod_campaign")
        begin_nod = named_block(decisions, "STP_pw_begin_nod_campaign")
        self.assertIn("STP_shabrat_ai_bezhaysk_resolved = no", prepare_nod)
        self.assertIn("STP_shabrat_ai_bezhaysk_resolved = no", begin_nod)

        prepare_val = named_block(decisions, "STP_pw_prepare_val_campaign")
        begin_val = named_block(decisions, "STP_pw_begin_val_campaign")
        for block in (prepare_val, begin_val):
            self.assertIn("STP_shabrat_ai_bezhaysk_resolved = no", block)
            self.assertIn("STP_shabrat_ai_nodrul_resolved = no", block)
        self.assertIn("strength_ratio = { tag = VAL ratio < 1.0 }", begin_val)

    def test_ai_path_reaches_new_endgame(self) -> None:
        plans = read("common/ai_strategy_plans/ADISCORD_STP_plans.txt")
        plan = named_block(plans, "STS_shabrat_hegemony_plan")
        sequence = (
            "STP_pc_heg_regional_system",
            "STP_pw_take_bezhaysk",
            "STP_pc_heg_nod_break",
            "STP_pc_heg_nod_force",
            "STP_pc_heg_val_audit",
            "STP_pc_heg_val_terms",
            "STP_pc_heg_val_force",
            "STP_pc_heg_clients",
            "STP_pc_heg_burden",
            "STP_pc_heg_administrations",
            "STP_pc_heg_final_north",
            "STP_pc_heg_final_kefreyt",
        )
        positions = [plan.index(item) for item in sequence]
        self.assertEqual(positions, sorted(positions))


class FinalKefreytWarFixture(TreatyFixture):
    """Model war entry and immediate allied joins without assuming hook timing."""

    def __init__(self):
        super().__init__()
        self.root = "STS"
        self.load("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.load("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt", True)
        self.completed = {"STP_pc_heg_final_north"}
        self.ready = {
            "RUS_crisis_regional_wars_available",
            "STP_pc_focus_available",
            "STP_pc_hegemony_continues",
        }
        self.variables["STS", "STP_pc_course"] = 1
        self.wars.clear()
        self.capitulated.clear()
        self.factions = {"VAL": "contract", "NOD": "contract"}
        self.declarations = []
        self.declaration_succeeds = True
        self.focus = next(
            e.value
            for e in entries("focus_trees/STP/postwar/shabrat/focuses.txt")
            if e.key == "focus" and scalar(e.value, "id") == "STP_pc_heg_final_kefreyt"
        )

    def matches(self, rows, stack):
        for entry in rows:
            if entry.key == "custom_trigger_tooltip":
                result = self.matches([e for e in entry.value if e.key != "tooltip"], stack)
            elif entry.key in (
                "RUS_crisis_regional_wars_available",
                "STP_pc_focus_available",
                "STP_pc_hegemony_continues",
            ):
                result = (entry.key in self.ready) == (entry.value == "yes")
            elif entry.key == "has_completed_focus":
                result = entry.value in self.completed
            else:
                result = super().matches([entry], stack)
            if not result:
                return False
        return True

    def execute(self, rows, stack=None):
        stack = stack or [self.root]
        for entry in rows:
            if entry.key == "declare_war_on":
                target = scalar(entry.value, "target")
                self.declarations.append(target)
                if self.declaration_succeeds:
                    self.wars.update(frozenset((stack[-1], tag)) for tag in (target, "NOD"))
            else:
                super().execute([entry], stack)

    def launch(self):
        self.execute(self.effects["STP_heg_start_kefreyt_final_war"])


class FinalKefreytWarTests(unittest.TestCase):
    def test_focus_and_dispatcher_reject_changed_diplomacy(self):
        from copy import deepcopy

        original = FinalKefreytWarFixture()
        self.assertTrue(original.matches(block(original.focus, "available"), ["STS"]))
        for failure in (
            "absent", "our_subject", "foreign_subject", "ally", "capitulated",
            "already_at_war", "northern_war", "northern_focus", "our_subject_status",
            "our_capitulation", "course", "government", "world_crisis", "started",
        ):
            with self.subTest(failure=failure):
                fixture = deepcopy(original)
                if failure == "absent":
                    fixture.existing.remove("VAL")
                elif failure in ("our_subject", "foreign_subject"):
                    fixture.subjects["VAL"] = "STS" if failure == "our_subject" else "ZZZ"
                elif failure == "ally":
                    fixture.factions["STS"] = "contract"
                elif failure == "capitulated":
                    fixture.capitulated.add("VAL")
                elif failure in ("already_at_war", "northern_war"):
                    fixture.wars.add(frozenset(("STS", "VAL" if failure == "already_at_war" else "YPR")))
                elif failure == "northern_focus":
                    fixture.completed.clear()
                elif failure == "our_subject_status":
                    fixture.subjects["STS"] = "ZZZ"
                elif failure == "our_capitulation":
                    fixture.capitulated.add("STS")
                elif failure == "course":
                    fixture.variables["STS", "STP_pc_course"] = 2
                elif failure == "government":
                    fixture.ready.remove("STP_pc_focus_available")
                elif failure == "world_crisis":
                    fixture.ready.remove("RUS_crisis_regional_wars_available")
                elif failure == "started":
                    fixture.flags["STS"].add("STP_heg_kefreyt_final_started")
                self.assertFalse(fixture.matches(block(fixture.focus, "available"), ["STS"]))
                before = deepcopy(fixture.flags)
                fixture.launch()
                self.assertEqual(fixture.declarations, [])
                self.assertEqual(fixture.flags, before)
        self.assertEqual(scalar(original.focus, "cancel_if_invalid"), "yes")

    def test_limited_peace_is_not_a_bypass_but_subjugation_is(self):
        fixture = FinalKefreytWarFixture()
        fixture.flags["VAL"].add("VAL_stelander_defeated")
        self.assertFalse(fixture.matches(block(fixture.focus, "bypass"), ["STS"]))
        self.assertTrue(fixture.matches(block(fixture.focus, "available"), ["STS"]))
        fixture.subjects["VAL"] = "STS"
        self.assertTrue(fixture.matches(block(fixture.focus, "bypass"), ["STS"]))
        fixture.subjects.clear()
        fixture.existing.remove("VAL")
        self.assertTrue(fixture.matches(block(fixture.focus, "bypass"), ["STS"]))

    def test_failed_native_declaration_does_not_record_a_campaign(self):
        fixture = FinalKefreytWarFixture()
        fixture.declaration_succeeds = False
        fixture.launch()
        self.assertEqual(fixture.declarations, ["VAL"])
        self.assertNotIn("STP_heg_kefreyt_final_started", fixture.flags["STS"])
        self.assertNotIn("STP_heg_kefreyt_final_member", fixture.flags["VAL"])

    def test_success_records_immediate_allies_and_cannot_declare_twice(self):
        fixture = FinalKefreytWarFixture()
        fixture.launch()
        self.assertIn("STP_heg_kefreyt_final_started", fixture.flags["STS"])
        for tag in ("VAL", "NOD"):
            self.assertIn("STP_heg_kefreyt_final_member", fixture.flags[tag])
        self.assertNotIn("STP_heg_kefreyt_final_member", fixture.flags["YPR"])
        fixture.launch()
        self.assertEqual(fixture.declarations, ["VAL"])


class ShabratTreatyFixture(TreatyFixture):
    """Execute territorial/subject effects; model unrelated politics explicitly."""

    def __init__(self, opponent="VAL", course=1):
        super().__init__()
        self.countries += ["CIN", "OSF", "APH", "NKA", "SLI"]
        self.flags.update({tag: set() for tag in self.countries})
        self.root = "STS"
        self.owners = {str(state): "VAL" for state in range(58, 66)}
        self.owners["709"] = "VAL"
        self.controllers = dict(self.owners)
        self.cores = {
            str(state): {tag}
            for tag, states in (("CIN", (58, 59, 60)), ("OSF", (61, 62, 63)), ("APH", (64, 65)))
            for state in states
        }
        self.cores["709"] = {"SLI"}
        self.existing = {"STS", "NOD", "VAL", "ZZZ"}
        self.completed = set()
        self.autonomy = {}
        self.cosmetics = {}
        self.capitulated = set()
        self.temporary_variables = {}
        self.variables["STS", "STP_pc_cap_side"] = 1 if opponent == "VAL" else 2
        self.variables["STS", "STP_pc_course"] = course
        self.wars = {frozenset(("STS", opponent)), frozenset(("VAL", "ZZZ"))}
        self.flags["STS"].add("STP_cw_postwar")
        self.stubs.update({
            "ADISCORD_economy_initialize_country",
            "ADISCORD_economy_update_postwar_demobilization",
            "VAL_enforce_stelander_defeat",
            "STP_pc_clear_settlement",
            "STP_heg_install_nod_administrator",
            "STP_heg_install_val_administrator",
        })
        self.load("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        self.load("common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt", True)

    def matches(self, rows, stack):
        current = stack[-1]
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("AND", "hidden_trigger"):
                result = self.matches(value, stack)
            elif key == "OR":
                result = any(self.matches([child], stack) for child in value)
            elif key == "NOT":
                result = not any(self.matches([child], stack) for child in value)
            elif key == "state":
                result = current == value
            elif key == "has_completed_focus":
                result = (current, value) in self.completed
            elif key == "check_variable" and (current, scalar(value, "var")) in self.temporary_variables:
                assert scalar(value, "compare") == "equals"
                result = self.temporary_variables[current, scalar(value, "var")] == float(scalar(value, "value"))
            elif key == "is_owned_by":
                result = self.owners.get(current) == value
            elif key == "is_core_of":
                result = value in self.cores.get(current, set())
            elif key == "owner":
                result = self.matches(value, stack + [self.owners[current]])
            elif key == "any_owned_state":
                result = any(
                    owner == current and self.matches(value, stack + [state])
                    for state, owner in self.owners.items()
                )
            else:
                result = super().matches([entry], stack)
            if not result:
                return False
        return True

    def execute(self, rows, stack=None):
        stack = stack or [self.root]
        current = stack[-1]
        taken = False
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                gate = next((e.value for e in value if e.key == "limit"), [])
                if not taken and self.matches(gate, stack):
                    taken = True
                    self.execute([e for e in value if e.key != "limit"], stack)
            elif key in ("every_state", "every_owned_state", "every_subject_country"):
                scopes = list(self.countries if key == "every_subject_country" else self.owners)
                gate = next((e.value for e in value if e.key == "limit"), [])
                for scope in scopes:
                    if key == "every_owned_state" and self.owners[scope] != current:
                        continue
                    if key == "every_subject_country" and self.subjects.get(scope) != current:
                        continue
                    if self.matches(gate, stack + [scope]):
                        self.execute([e for e in value if e.key != "limit"], stack + [scope])
            elif key == "overlord":
                self.execute(value, stack + [self.subjects[current]])
            elif key == "set_autonomy":
                target = self.resolve(scalar(value, "target"), stack)
                tier = scalar(value, "autonomy_state")
                if tier == "autonomy_free":
                    self.subjects.pop(target, None)
                    self.autonomy.pop(target, None)
                else:
                    assert frozenset((current, target)) not in self.wars
                    self.subjects[target] = current
                    self.autonomy[target] = tier
            elif key == "white_peace":
                target = self.resolve(value, stack)
                self.wars.discard(frozenset((current, target)))
                self.capitulated.discard(target)
                # Occupation evidence disappears before subjects/territory are awarded.
                self.controllers = dict(self.owners)
            elif key in ("transfer_state", "transfer_state_to"):
                state = self.resolve(value, stack) if key == "transfer_state" else current
                recipient = current if key == "transfer_state" else self.resolve(value, stack)
                self.owners[state] = recipient
                self.existing.add(recipient)
            elif key == "set_state_controller_to":
                self.controllers[current] = value
            elif key == "set_cosmetic_tag":
                self.cosmetics[current] = value
            elif key == "set_temp_variable":
                self.temporary_variables[current, scalar(value, "var")] = float(scalar(value, "value"))
            elif key == "add_core_of":
                self.cores.setdefault(current, set()).add(value)
            elif key == "clear_variable":
                self.variables.pop((current, value), None)
            elif key == "VAL_enter_stelander_defeat":
                self.flags[current].add("VAL_stelander_defeated")
                # Closing the frontier campaign can already reset occupation.
                self.controllers = dict(self.owners)
            elif key == "STP_nod_settle_border_treaty":
                self.flags[current].add("STP_pc_defeated_by_sts")
                self.wars.discard(frozenset(("STS", current)))
                self.calls.append((key, current))
            else:
                super().execute([entry], stack)

    def settle(self, opponent="VAL"):
        self.variables["STS", "STP_pc_cap_side"] = 1 if opponent == "VAL" else 2
        try:
            self.execute(self.effects["STP_pc_begin_settlement"])
        finally:
            self.temporary_variables.clear()


class ShabratRepeatedPeaceTests(unittest.TestCase):
    def test_first_then_second_victory_changes_the_surviving_overlord(self):
        for opponent, receipt in (("NOD", "STP_pc_defeated_by_sts"), ("VAL", "VAL_stelander_defeated")):
            with self.subTest(opponent=opponent):
                fixture = ShabratTreatyFixture(opponent)
                fixture.settle(opponent)
                self.assertNotIn(opponent, fixture.subjects)
                self.assertIn(receipt, fixture.flags[opponent])
                fixture.wars.add(frozenset(("STS", opponent)))
                fixture.settle(opponent)
                self.assertEqual(fixture.subjects[opponent], "STS")
                self.assertEqual(fixture.autonomy[opponent], "autonomy_STP_provisional_administration")
                self.assertEqual(fixture.cosmetics[opponent], f"{opponent}_STS_administration")
                self.assertIn(frozenset(("VAL", "ZZZ")), fixture.wars)

    def test_refused_demand_campaign_does_not_fall_back_to_limited_peace(self):
        for opponent in ("NOD", "VAL"):
            with self.subTest(opponent=opponent):
                fixture = ShabratTreatyFixture(opponent)
                fixture.completed.add(("STS", f"STP_pc_heg_{opponent.lower()}_force"))
                fixture.settle(opponent)
                self.assertEqual(fixture.subjects[opponent], "STS")
                self.assertNotIn(("STP_nod_settle_border_treaty", "NOD"), fixture.calls)

    def test_liberation_victory_does_not_impose_hegemony(self):
        for opponent, receipt in (("NOD", "STP_pc_defeated_by_sts"), ("VAL", "VAL_stelander_defeated")):
            fixture = ShabratTreatyFixture(opponent, course=2)
            fixture.flags[opponent].add(receipt)
            fixture.settle(opponent)
            self.assertNotIn(opponent, fixture.subjects)

    def test_council_revanche_in_hegemony_preserves_val_as_a_subject(self):
        fixture = ShabratTreatyFixture()
        fixture.flags["VAL"].update(("VAL_stelander_defeated", "VAL_council_revanche_active"))
        fixture.settle()
        self.assertEqual(fixture.subjects["VAL"], "STS")
        self.assertNotIn("VAL", fixture.annexed)
        self.assertNotIn("VAL_council_revanche_active", fixture.flags["VAL"])

    def test_first_peace_returns_islands_and_restores_annexed_tribes(self):
        fixture = ShabratTreatyFixture()
        fixture.settle()
        self.assertEqual(fixture.owners["709"], "STS")
        self.assertEqual(fixture.controllers["709"], "STS")
        for state, cores in fixture.cores.items():
            if state == "709":
                continue
            tribe = next(iter(cores))
            self.assertEqual(fixture.owners[state], tribe)
            self.assertEqual(fixture.subjects[tribe], "STS")
        self.assertTrue(all(not values for values in fixture.arrays.values()))
        owners, subjects = dict(fixture.owners), dict(fixture.subjects)
        fixture.execute(fixture.effects["STP_pc_settle_val_northern_conquests"])
        self.assertEqual(fixture.owners, owners)
        self.assertEqual(fixture.subjects, subjects)

    def test_existing_common_administration_receives_captured_resource_belt(self):
        fixture = ShabratTreatyFixture()
        fixture.existing.add("NKA")
        fixture.subjects["NKA"] = "VAL"
        for state in ("58", "62", "63", "64", "65"):
            fixture.owners[state] = "NKA"
        fixture.settle()
        self.assertEqual(fixture.subjects["NKA"], "STS")
        self.assertTrue(all(fixture.owners[str(state)] == "NKA" for state in range(58, 66)))
        self.assertTrue(all(tag not in fixture.existing for tag in ("CIN", "OSF", "APH")))

    def test_existing_tribal_subjects_keep_foreign_land_and_unrelated_wars(self):
        fixture = ShabratTreatyFixture()
        fixture.existing.add("CIN")
        fixture.subjects["CIN"] = "VAL"
        fixture.owners["999"] = "CIN"
        fixture.controllers["999"] = "ZZZ"
        fixture.wars.add(frozenset(("CIN", "ZZZ")))
        fixture.settle()
        self.assertEqual(fixture.subjects["CIN"], "STS")
        self.assertEqual(fixture.owners["999"], "CIN")
        self.assertIn(frozenset(("CIN", "ZZZ")), fixture.wars)

    def test_independent_tribes_foreign_land_and_occupation_are_excluded(self):
        fixture = ShabratTreatyFixture()
        fixture.existing.add("CIN")
        fixture.owners["58"] = "CIN"
        fixture.controllers["61"] = "ZZZ"
        fixture.owners["64"] = "ZZZ"
        fixture.owners["709"] = "SLI"
        fixture.settle()
        self.assertNotIn("CIN", fixture.subjects)
        self.assertEqual(fixture.owners["59"], "VAL")
        self.assertEqual(fixture.owners["61"], "VAL")
        self.assertEqual(fixture.owners["64"], "ZZZ")
        self.assertEqual(fixture.owners["709"], "SLI")


class FrontierExpansionFixture(FinalKefreytWarFixture):
    def __init__(self, target="AIN"):
        super().__init__()
        self.target = target
        self.join_succeeds = True
        self.countries.append("AIN")
        self.existing.add("AIN")
        self.flags["AIN"] = set()
        self.subjects = {"TFF": "STS", "NOD": "STS"}
        self.factions.clear()
        self.completed = {"STP_pc_heg_administrations"}
        self.owners = {1: target, 999: target, 2: "ZZZ"}
        self.controllers = dict(self.owners)
        self.cores = {2: {target}}
        self.focus = next(
            e.value for e in entries("focus_trees/STP/postwar/shabrat/focuses.txt")
            if e.key == "focus" and scalar(e.value, "id") == f"STP_pc_heg_frontier_{target.lower()}"
        )

    def execute(self, rows, stack=None):
        from tools.tests.test_scripted_peace_on_actions import GenericPeaceFixture

        stack = stack or [self.root]
        for entry in rows:
            if entry.key == "declare_war_on":
                target = scalar(entry.value, "target")
                self.declarations.append(target)
                if self.declaration_succeeds:
                    self.wars.add(frozenset((stack[-1], target)))
            elif entry.key == "add_to_war":
                target = scalar(entry.value, "enemy")
                leader = scalar(entry.value, "targeted_alliance")
                assert frozenset((leader, target)) in self.wars
                if self.join_succeeds:
                    self.wars.add(frozenset((stack[-1], target)))
                self.calls.append(("add_to_war", stack[-1], leader, target))
            elif entry.key == "white_peace":
                GenericPeaceFixture.execute(self, [entry], stack)
                self.execute(self.effects["STP_heg_reconcile_frontier_expansion"], stack)
            elif entry.key == "annex_country":
                GenericPeaceFixture.execute(self, [entry], stack)
                self.existing.discard(self.resolve(scalar(entry.value, "target"), stack))
                self.execute(self.effects["STP_heg_reconcile_frontier_expansion"], stack)
            else:
                super().execute([entry], stack)

    def launch(self):
        self.execute(self.effects[f"STP_heg_start_frontier_{self.target.lower()}"], ["STS"])

    def capitulate(self, winner="STS"):
        self.root = self.target
        self.winner = winner
        # Native has_capitulated may still be false in the immediate callback.
        actions = block(entries("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"), "on_actions")
        immediate = block(block(actions, "on_capitulation_immediate"), "effect")
        guarded = next(e.value for e in immediate if e.key == "if")
        dispatcher = next(
            e for e in guarded if e.key == "if" and any(
                c.key == "STP_heg_frontier_capitulation_managed"
                for c in block(e.value, "limit")
            )
        )
        self.execute([dispatcher])


class FrontierExpansionTests(unittest.TestCase):
    def test_focus_starts_one_shared_war_and_rechecks_changed_conditions(self):
        for target in ("AIN", "COF"):
            original = FrontierExpansionFixture(target)
            self.assertTrue(original.matches(block(original.focus, "available"), ["STS"]))
            original.launch()
            original.launch()
            self.assertEqual(original.declarations, [target])
            self.assertIn(frozenset(("STS", target)), original.wars)
            self.assertIn(("add_to_war", "TFF", "STS", target), original.calls)
            for failure in ("missing_target", "foreign_subject", "ally", "already_at_war", "missing_frontier", "free_frontier", "defeated_frontier", "world_crisis"):
                with self.subTest(target=target, failure=failure):
                    fixture = FrontierExpansionFixture(target)
                    if failure == "missing_target":
                        fixture.existing.remove(target)
                    elif failure == "foreign_subject":
                        fixture.subjects[target] = "NOD"
                    elif failure == "ally":
                        fixture.factions.update({"STS": "league", target: "league"})
                    elif failure == "already_at_war":
                        fixture.wars.add(frozenset(("STS", target)))
                    elif failure == "missing_frontier":
                        fixture.existing.remove("TFF")
                    elif failure == "free_frontier":
                        fixture.subjects.pop("TFF")
                    elif failure == "defeated_frontier":
                        fixture.capitulated.add("TFF")
                    elif failure == "world_crisis":
                        fixture.ready.remove("RUS_crisis_regional_wars_available")
                    self.assertFalse(fixture.matches(block(fixture.focus, "available"), ["STS"]))
                    fixture.launch()
                    self.assertEqual(fixture.declarations, [])
            failed = FrontierExpansionFixture(target)
            failed.declaration_succeeds = False
            failed.launch()
            self.assertNotIn("STP_heg_frontier_campaign_active", failed.flags[target])
            failed_join = FrontierExpansionFixture(target)
            failed_join.join_succeeds = False
            failed_join.launch()
            self.assertNotIn("STP_heg_frontier_campaign_active", failed_join.flags[target])

    def test_our_or_subject_victory_awards_only_target_land_to_frontier_once(self):
        for target in ("AIN", "COF"):
            for winner in ("STS", "TFF", "NOD"):
                with self.subTest(target=target, winner=winner):
                    fixture = FrontierExpansionFixture(target)
                    fixture.launch()
                    fixture.wars.add(frozenset((winner, target)))
                    fixture.capitulate(winner)
                    self.assertEqual(fixture.owners, {1: "TFF", 999: "TFF", 2: "ZZZ"})
                    self.assertEqual(fixture.controllers[999], "TFF")
                    self.assertEqual(fixture.annexed, [target])
                    self.assertNotIn("STP_heg_frontier_campaign_active", fixture.flags[target])
                    self.assertIn("STP_heg_frontier_capitulation_reserved", fixture.flags[target])
                    self.assertNotIn("skip_default_capitulation", fixture.global_flags)
                    fixture.capitulate(winner)
                    self.assertEqual(fixture.annexed, [target])

    def test_foreign_victory_and_lost_recipient_cannot_award_land(self):
        for failure in ("foreign_victor", "free_frontier", "defeated_frontier", "defeated_overlord", "peace", "frontier_peace", "target_subject"):
            with self.subTest(failure=failure):
                fixture = FrontierExpansionFixture()
                fixture.launch()
                if failure == "free_frontier":
                    fixture.subjects.pop("TFF")
                elif failure == "defeated_frontier":
                    fixture.capitulated.add("TFF")
                elif failure == "defeated_overlord":
                    fixture.capitulated.add("STS")
                elif failure == "peace":
                    fixture.wars.clear()
                elif failure == "frontier_peace":
                    fixture.wars.discard(frozenset(("TFF", "AIN")))
                elif failure == "target_subject":
                    fixture.subjects["AIN"] = "NOD"
                fixture.capitulate("ZZZ" if failure == "foreign_victor" else "STS")
                self.assertEqual(fixture.annexed, [])
                fixture.execute(fixture.effects["STP_heg_reconcile_frontier_expansion"])
                if failure != "foreign_victor":
                    self.assertNotIn("STP_heg_frontier_campaign_active", fixture.flags["AIN"])

    def test_late_callback_reserves_generic_annexation_and_focus_ids_are_unique(self):
        source = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        late = named_block(source, "on_capitulation")
        receipt = "STP_heg_frontier_capitulation_reserved"
        self.assertIn(f"has_country_flag = {receipt}", late)
        self.assertIn(f"clr_country_flag = {receipt}", late)
        for target in ("ain", "cof"):
            key = f"STP_pc_heg_frontier_{target}"
            native = read("common/national_focus/ADISCORD_STP_civil_war.txt")
            self.assertEqual(native.count(f"id = {key}"), 1)
            for lang in ("russian", "english"):
                loc = read(f"localisation/{lang}/ADISCORD_STP_hegemony_l_{lang}.yml")
                self.assertEqual(len(re.findall(rf"(?m)^ {key}:", loc)), 1)
                self.assertIn(f"{key}_desc:", loc)


class NorthernAdministrationFixture(ShabratTreatyFixture):
    """Execute northern transfers and coalition settlement with explicit native edges."""

    def __init__(self):
        super().__init__()
        self.leader = "STS"
        self.course = "hegemony"
        self.flags["STS"].add("STP_cw_won_union_battle")
        self.global_flags.add("STP_cw_union_wars_finished")
        self.wars.clear()
        self.owners.update({"24": "VAL", "55": "VAL", "48": "VAL"})
        self.controllers = dict(self.owners)
        self.subjects = {"VAL": "STS"}
        self.completed = {
            ("STS", "STP_pc_heg_administrations"),
            ("STS", "STP_pc_heg_northern_administration"),
        }
        self.stubs.update({"STP_heg_install_nka_administrator", "inherit_technology"})
        self.triggers["VAL_frontier_has_only_claimed_states"] = block(
            entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"),
            "VAL_frontier_has_only_claimed_states",
        )
        self.declarations = []
        self.declaration_succeeds = True
        self.humans = set()
        self.handoffs = []
        self.war_sides = []

    def resolve(self, token, stack):
        if token.startswith("event_target:"):
            return self.targets[token]
        return super().resolve(token, stack)

    def matches(self, rows, stack):
        current = stack[-1]
        for entry in rows:
            key, value = entry.key, entry.value
            if key == "STP_pc_hegemony_continues":
                result = (current == "STS" and self.course == "hegemony") == (value == "yes")
            elif key == "STP_pc_sword_directory_branch":
                result = (current == "STS" and self.course == "directory") == (value == "yes")
            elif key == "STP_pc_sword_directory_current":
                result = (
                    current == "STS"
                    and self.course == "directory"
                    and ("STS", "STP_pc_sdir_oath") in self.completed
                ) == (value == "yes")
            elif key == "RUS_crisis_regional_wars_available":
                result = value == "yes"
            elif key == "tag":
                result = current == self.resolve(value, stack)
            elif key == "is_subject_of":
                result = self.subjects.get(current) == self.resolve(value, stack)
            elif key == "is_owned_by":
                result = self.owners.get(current) == self.resolve(value, stack)
            elif key == "is_controlled_by":
                result = self.controllers.get(current) == self.resolve(value, stack)
            elif key == "has_war":
                result = bool(self.enemies(current)) == (value == "yes")
            elif key == "all_owned_state":
                result = all(
                    self.matches(value, stack + [state])
                    for state, owner in self.owners.items() if owner == current
                )
            elif key == "owns_state":
                result = self.owners.get(value) == current
            elif key == "is_ai":
                result = (current not in self.humans) == (value == "yes")
            else:
                result = super().matches([entry], stack)
            if not result:
                return False
        return True

    def execute(self, rows, stack=None):
        stack = stack or [self.root]
        current = stack[-1]
        taken = False
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                gate = next((e.value for e in value if e.key == "limit"), [])
                if not taken and self.matches(gate, stack):
                    taken = True
                    self.execute([e for e in value if e.key != "limit"], stack)
            elif key == "save_event_target_as":
                self.targets["event_target:" + value] = current
            elif key.startswith("event_target:"):
                self.execute(value, stack + [self.resolve(key, stack)])
            elif key == "owner":
                self.execute(value, stack + [self.owners[current]])
            elif key == "set_state_controller_to":
                self.controllers[current] = self.resolve(value, stack)
            elif key == "add_core_of":
                self.cores.setdefault(current, set()).add(self.resolve(value, stack))
            elif key == "declare_war_on":
                target = scalar(value, "target")
                self.declarations.append(target)
                if self.declaration_succeeds:
                    self.wars.add(frozenset((current, target)))
                    self.war_sides = [{current}, {target}]
            elif key == "add_to_war":
                leader = self.resolve(scalar(value, "targeted_alliance"), stack)
                enemy = self.resolve(scalar(value, "enemy"), stack)
                assert frozenset((leader, enemy)) in self.wars
                side = next(side for side in self.war_sides if leader in side)
                other = next(side for side in self.war_sides if enemy in side)
                side.add(current)
                for opponent in other:
                    self.wars.add(frozenset((current, opponent)))
            elif key == "set_capital":
                self.capitals[current] = scalar(value, "state")
            elif key == "change_tag_from":
                previous = self.resolve(value, stack)
                self.humans.discard(previous)
                self.humans.add(current)
                self.handoffs.append((previous, current))
            elif key == "annex_country":
                target = self.resolve(scalar(value, "target"), stack)
                national_control = {
                    state for state, owner in self.owners.items()
                    if owner == target and self.controllers.get(state) == target
                }
                super().execute([entry], stack)
                for state in national_control:
                    self.controllers[state] = current
                self.existing.discard(target)
                self.subjects.pop(target, None)
            elif key == "white_peace":
                # Native peace can end the entire merged war, not just this pair.
                foreign_control = {
                    state: controller
                    for state, controller in self.controllers.items()
                    if controller not in set().union(*self.war_sides)
                    and controller != self.owners.get(state)
                }
                super().execute([entry], stack)
                self.controllers.update(foreign_control)
                self.wars.clear()
                self.execute(self.effects["STP_heg_reconcile_cannibal_campaign"], stack)
            else:
                super().execute([entry], stack)

    def form(self):
        self.execute(self.effects["STP_heg_form_northern_administration"], ["STS"])

    def independent_tribes(self):
        for state, cores in self.cores.items():
            if state != "709":
                self.owners[state] = next(iter(cores))
        self.existing.update(("CIN", "OSF", "APH"))
        self.controllers = dict(self.owners)

    def use_course(self, course, leader="STS"):
        self.course = course
        self.leader = leader
        self.root = leader
        self.existing.add(leader)
        self.flags[leader].update({"STP_cw_postwar", "STP_cw_won_union_battle"})
        self.completed = {(leader, "STP_pw_common_market")}
        if course == "directory":
            self.variables[leader, "STP_pc_course"] = 3
            self.completed.add((leader, "STP_pc_sdir_oath"))

    def launch(self):
        self.execute(self.effects["STP_heg_start_cannibal_campaign"], [self.leader])

    def defeat(self, tag):
        self.root = tag
        self.winner = self.leader
        self.execute(self.effects["STP_heg_settle_cannibal_campaign"], [tag])


class NorthernAdministrationTests(unittest.TestCase):
    def test_arsenal_extensions_stay_with_val_and_reorganization_respects_foreign_land(self):
        for state in ("54", "57"):
            for owner, controller in (("VAL", "VAL"), ("VAL", "STS"), ("VAL", "ALLY"), ("VAL", "ZZZ"), ("STS", "STS"), ("STS", "ZZZ"), ("ZZZ", "STS")):
                with self.subTest(state=state, owner=owner, controller=controller):
                    f = NorthernAdministrationFixture()
                    f.use_course("directory")
                    f.stubs.add("STP_sdir_apply_district_government")
                    f.stubs.add("STP_sdir_consolidate_bezhaysk_administration")
                    f.subjects["ALLY"] = "STS"
                    f.owners[state] = owner
                    f.controllers[state] = controller
                    f.execute(f.effects["STP_sdir_reorganize_districts"], ["STS"])
                    f.execute(f.effects["STP_sdir_reorganize_districts"], ["STS"])
                    expected = "VAL" if owner in ("VAL", "STS") and controller != "ZZZ" else owner
                    self.assertEqual(f.owners[state], expected)
                    settled = owner in ("VAL", "STS") and controller != "ZZZ"
                    self.assertEqual(f.controllers[state], "VAL" if settled else controller)

    def test_directory_northern_plan_opens_shared_campaign_without_common_market(self):
        from tools.tests.test_adiscord_stp_preparation import walk

        for leader, course in (("STS", "directory"), ("STS", "charter"), ("STP", "party")):
            with self.subTest(leader=leader, course=course):
                f = NorthernAdministrationFixture()
                f.use_course(course, leader)
                f.independent_tribes()
                f.completed.discard((leader, "STP_pw_common_market"))
                f.completed.add((leader, "STP_pc_sdir_northern_plan"))
                f.launch()
                self.assertEqual(bool(f.declarations), course == "directory")
                if course != "directory":
                    f.completed.add((leader, "STP_pw_common_market"))
                    f.launch()
                    self.assertEqual(f.declarations, ["CIN"])
        focus = next(
            e.value for e in walk(entries("focus_trees/STP/civil_war/focuses.txt"))
            if e.key == "focus" and isinstance(e.value, list)
            and scalar(e.value, "id") == "STP_pc_cannibal_campaign"
        )
        self.assertEqual(
            {e.value for e in block(focus, "prerequisite")},
            {"STP_pw_common_market", "STP_pc_sdir_northern_plan"},
        )
        plan = named_block(read("common/ai_strategy_plans/ADISCORD_STP_plans.txt"), "STS_sword_directory_plan")
        for name in (
            "STP_pw_regional_citizenship", "STP_pw_regional_connections",
            "STP_pw_cadastral_commissions", "STP_pw_local_officer_courses",
            "STP_pw_workshop_contracts", "STP_pw_common_market",
        ):
            self.assertNotIn(name, plan)
        for name in (
            "STP_pw_republic_army_register", "STP_pw_republic_officer_school",
            "STP_pw_republic_supply_service", "STP_pw_republic_professional_service",
            "STP_pw_take_bezhaysk", "STP_pc_cannibal_campaign",
        ):
            self.assertIn(name, plan)

    def test_registers_always_fund_three_integrations_without_repeating_an_unlock(self):
        from tools.tests.test_adiscord_stp_preparation import selected_effects

        focus = next(
            e.value for e in entries("focus_trees/STP/postwar/shabrat/focuses.txt")
            if e.key == "focus" and scalar(e.value, "id") == "STP_pc_sdir_annexed_registers"
        )
        for citizenship, administrations in ((False, False), (True, False), (False, True), (True, True)):
            with self.subTest(citizenship=citizenship, administrations=administrations):
                facts = {
                    ("STS", "has_completed_focus", "STP_pw_regional_citizenship"): citizenship,
                    ("STS", "has_completed_focus", "STP_pc_heg_administrations"): administrations,
                }
                rewards = [e for _, e in selected_effects(block(focus, "completion_reward"), facts, "STS")]
                self.assertEqual([e.value for e in rewards if e.key == "add_political_power"], ["150"])
                self.assertEqual(
                    any(e.key == "unlock_decision_tooltip" for e in rewards),
                    not citizenship and not administrations,
                )

    def test_party_and_charter_share_the_war_but_keep_local_subjects(self):
        for leader, course in (("STP", "party"), ("STS", "charter")):
            with self.subTest(leader=leader, course=course):
                f = NorthernAdministrationFixture()
                f.use_course(course, leader)
                f.independent_tribes()
                before = dict(f.owners)
                f.launch()
                self.assertEqual(f.declarations, ["CIN"])
                self.assertEqual(f.war_sides, [{leader}, {"CIN", "OSF", "APH"}])
                for tag in ("CIN", "OSF", "APH"):
                    f.defeat(tag)
                self.assertFalse(f.annexed)
                self.assertEqual(f.owners, before)
                self.assertTrue(all(f.subjects[tag] == leader for tag in ("CIN", "OSF", "APH")))
                self.assertFalse(f.majors)
                self.assertNotIn("STP_heg_cannibal_campaign_active", f.flags[leader])

    def test_directory_annexes_defeated_owners_and_preserves_player_handoff(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        f.humans.add("CIN")
        f.launch()
        for tag in ("CIN", "OSF", "APH"):
            f.defeat(tag)
        self.assertEqual(set(f.annexed), {"CIN", "OSF", "APH"})
        self.assertIn(("CIN", "STS"), f.handoffs)
        for state in range(58, 66):
            self.assertEqual(f.owners[str(state)], "STS")
            self.assertEqual(f.controllers[str(state)], "STS")
            self.assertIn("STS", f.cores[str(state)])
        self.assertFalse(f.majors)

    def test_directory_campaign_cannot_take_foreign_owned_or_occupied_states(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        f.launch()
        f.owners["60"] = "ZZZ"
        f.controllers["60"] = "ZZZ"
        f.controllers["61"] = "ZZZ"
        for tag in ("CIN", "OSF", "APH"):
            f.defeat(tag)
        self.assertEqual(f.owners["60"], "ZZZ")
        self.assertEqual(f.controllers["60"], "ZZZ")
        self.assertEqual(f.owners["61"], "OSF")
        self.assertEqual(f.controllers["61"], "ZZZ")
        self.assertNotIn("OSF", f.annexed)
        self.assertEqual(f.subjects["OSF"], "STS")
        self.assertEqual(f.owners["62"], "STS")
        self.assertEqual(f.owners["63"], "STS")

    def test_foreign_capitulator_does_not_issue_a_campaign_defeat_receipt(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        f.launch()
        f.root = "CIN"
        f.winner = "ZZZ"
        f.wars.add(frozenset(("CIN", "ZZZ")))
        f.execute(f.effects["STP_heg_settle_cannibal_campaign"], ["CIN"])
        self.assertNotIn("STP_heg_cannibal_defeated", f.flags["CIN"])
        self.assertFalse(f.annexed)

    def test_current_campaign_save_load_needs_only_persistent_receipts(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        f.launch()
        f.defeat("CIN")
        f.targets.clear()
        f.defeat("OSF")
        f.targets.clear()
        f.defeat("APH")
        self.assertEqual(set(f.annexed), {"CIN", "OSF", "APH"})
        self.assertFalse(f.majors)
        self.assertTrue(all(not values for values in f.arrays.values()))

    def test_directory_absorbs_only_defeated_dependants_in_the_eight_states(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.subjects.clear()
        before = dict(f.owners)
        f.execute(f.effects["STP_sdir_absorb_cannibal_conquests"], ["STS"])
        self.assertEqual(f.owners, before)
        f.subjects["VAL"] = "STS"
        f.controllers["60"] = "ZZZ"
        f.owners["61"] = "ZZZ"
        f.controllers["61"] = "ZZZ"
        f.execute(f.effects["STP_sdir_absorb_cannibal_conquests"], ["STS"])
        self.assertEqual(f.owners["58"], "STS")
        self.assertEqual(f.owners["60"], "VAL")
        self.assertEqual(f.controllers["60"], "ZZZ")
        self.assertEqual(f.owners["61"], "ZZZ")
        self.assertEqual(f.owners["24"], "VAL")
        self.assertEqual(f.owners["55"], "VAL")
        self.assertEqual(f.owners["48"], "VAL")
        self.assertFalse(f.matches(f.triggers["STP_sdir_cannibal_lands_secured"], ["STS"]))
        f.owners["61"] = "VAL"
        f.controllers["60"] = "VAL"
        f.controllers["61"] = "VAL"
        f.execute(f.effects["STP_sdir_absorb_cannibal_conquests"], ["STS"])
        self.assertTrue(f.matches(f.triggers["STP_sdir_cannibal_lands_secured"], ["STS"]))

    def test_kefreyt_conquests_do_not_create_a_new_campaign_against_its_subjects(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        for tag in ("CIN", "OSF", "APH"):
            f.subjects[tag] = "VAL"
        before = dict(f.owners)
        f.launch()
        self.assertFalse(f.declarations)
        self.assertEqual(f.owners, before)
        self.assertTrue(f.matches(f.triggers["STP_heg_cannibals_resolved"], ["STS"]))

    def test_oath_reward_absorbs_preexisting_subjects_before_focus_completion(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.completed.remove(("STS", "STP_pc_sdir_oath"))
        self.assertFalse(f.matches(f.triggers["STP_pc_sword_directory_current"], ["STS"]))
        f.execute(f.effects["STP_sdir_absorb_cannibal_conquests"], ["STS"])
        self.assertTrue(f.matches(f.triggers["STP_sdir_cannibal_lands_secured"], ["STS"]))

    def test_late_subject_peace_absorbs_only_after_its_actual_war_ends(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.wars.add(frozenset(("VAL", "ZZZ")))
        f.controllers["60"] = "ZZZ"
        f.owners["61"] = "ZZZ"
        f.controllers["61"] = "ZZZ"
        before = dict(f.owners)
        f.root = "VAL"
        f.winner = "ZZZ"
        f.execute(f.effects["STP_sdir_follow_up_cannibal_conquests"], ["VAL"])
        self.assertEqual(f.owners, before)
        f.wars.clear()
        f.targets.clear()
        f.execute(f.effects["STP_sdir_follow_up_cannibal_conquests"], ["VAL"])
        self.assertEqual(f.owners["58"], "STS")
        self.assertEqual(f.owners["60"], "VAL")
        self.assertEqual(f.controllers["60"], "ZZZ")
        self.assertEqual(f.owners["61"], "ZZZ")
        self.assertEqual(f.owners["48"], "VAL")

    def test_follow_up_callbacks_wait_for_campaign_snapshot_and_ignore_other_wars(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        before = dict(f.owners)
        for root, winner, settling in (("STS", "ZZZ", False), ("VAL", "ZZZ", True)):
            f.root = root
            f.winner = winner
            if settling:
                f.flags["STS"].add("STP_heg_cannibal_settlement_in_progress")
            f.execute(f.effects["STP_sdir_follow_up_cannibal_conquests"], [root])
            self.assertEqual(f.owners, before)
        call = "STP_sdir_follow_up_cannibal_conquests = yes"
        for path, hooks in (
            ("common/on_actions/02_ADISCORD_STP_on_actions.txt", ("on_puppet", "on_release_as_puppet")),
            ("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt", ("on_peace", "on_annex", "on_peaceconference_ended")),
        ):
            source = read(path)
            for hook in hooks:
                self.assertEqual(named_block(source, hook).count(call), 1)

    def test_directory_absorption_hands_over_a_fully_owned_playable_subject(self):
        f = NorthernAdministrationFixture()
        f.use_course("directory")
        f.independent_tribes()
        f.subjects.update({"CIN": "STS", "OSF": "STS", "APH": "STS"})
        f.humans.add("CIN")
        f.controllers["61"] = "ZZZ"
        f.execute(f.effects["STP_sdir_absorb_cannibal_conquests"], ["STS"])
        self.assertIn(("CIN", "STS"), f.handoffs)
        self.assertIn("CIN", f.annexed)
        self.assertNotIn("OSF", f.annexed)
        self.assertEqual(f.owners["61"], "OSF")
        self.assertEqual(f.controllers["61"], "ZZZ")
        self.assertEqual(f.owners["62"], "STS")
        self.assertEqual(f.owners["48"], "VAL")

    def test_conquered_north_forms_without_reopening_a_war(self):
        f = NorthernAdministrationFixture()
        f.form()
        self.assertEqual(f.subjects["NKA"], "STS")
        for state in (24, 55, *range(58, 66)):
            self.assertEqual(f.owners[str(state)], "NKA")
            self.assertEqual(f.controllers[str(state)], "NKA")
        self.assertEqual(f.owners["48"], "VAL")
        self.assertEqual(f.capitals["NKA"], "64")
        f.launch()
        self.assertEqual(f.declarations, [])
        self.assertTrue(f.matches(f.triggers["STP_heg_cannibals_resolved"], ["STS"]))

    def test_independent_tribes_require_all_defeats_in_one_shared_war(self):
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.form()
        self.assertEqual(f.owners["58"], "CIN")
        f.launch()
        f.launch()
        self.assertEqual(f.declarations, ["CIN"])
        self.assertEqual(f.war_sides, [{"STS", "NKA"}, {"CIN", "OSF", "APH"}])
        self.assertTrue({"CIN", "OSF", "APH"}.issubset(f.majors))
        f.defeat("CIN")
        f.defeat("OSF")
        self.assertEqual(f.annexed, [])
        f.defeat("APH")
        self.assertEqual(set(f.annexed), {"CIN", "OSF", "APH"})
        self.assertTrue(all(f.owners[str(s)] == "NKA" for s in range(58, 66)))
        self.assertFalse(f.wars)
        self.assertFalse(f.majors)
        self.assertTrue(all(not array for array in f.arrays.values()))

    def test_liberated_member_blocks_final_settlement_again(self):
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.form()
        f.launch()
        f.defeat("CIN")
        f.flags["CIN"].discard("STP_heg_cannibal_defeated")
        f.defeat("OSF")
        f.defeat("APH")
        self.assertFalse(f.annexed)
        f.defeat("CIN")
        self.assertEqual(set(f.annexed), {"CIN", "OSF", "APH"})

    def test_subject_merge_preserves_player_and_foreign_occupation_is_excluded(self):
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.subjects.update({"CIN": "STS", "OSF": "STS", "APH": "STS"})
        f.humans.add("CIN")
        f.controllers["61"] = "ZZZ"
        f.form()
        self.assertIn(("CIN", "NKA"), f.handoffs)
        self.assertIn("CIN", f.annexed)
        self.assertNotIn("OSF", f.annexed)
        self.assertEqual(f.owners["61"], "OSF")
        self.assertEqual(f.controllers["61"], "ZZZ")

    def test_foreign_nka_or_border_owner_prevents_creation(self):
        for case in ("foreign_nka", "foreign_border", "occupied_border"):
            with self.subTest(case=case):
                f = NorthernAdministrationFixture()
                if case == "foreign_nka":
                    f.existing.add("NKA")
                    f.subjects["NKA"] = "ZZZ"
                elif case == "foreign_border":
                    f.owners["24"] = "ZZZ"
                else:
                    f.controllers["55"] = "ZZZ"
                before = dict(f.owners)
                f.form()
                self.assertEqual(f.owners, before)

    def test_failed_declaration_and_lost_administration_release_only_own_majors(self):
        for failure in ("declaration", "subject"):
            with self.subTest(failure=failure):
                f = NorthernAdministrationFixture()
                f.independent_tribes()
                f.form()
                f.majors.add("CIN")
                if failure == "declaration":
                    f.declaration_succeeds = False
                f.launch()
                if failure == "subject":
                    f.subjects["NKA"] = "ZZZ"
                    f.execute(f.effects["STP_heg_reconcile_cannibal_campaign"])
                self.assertEqual(f.majors, {"CIN"})
                for tag in ("CIN", "OSF", "APH"):
                    self.assertNotIn("STP_heg_cannibal_campaign_active", f.flags[tag])
                    self.assertNotIn("STP_heg_cannibal_added_major", f.flags[tag])


    def test_partial_conquest_skips_absent_targets_and_uses_next_war_anchor(self):
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.existing.discard("CIN")
        for state in ("58", "59", "60"):
            f.owners[state] = "VAL"
            f.controllers[state] = "VAL"
        f.form()
        f.launch()
        self.assertEqual(f.declarations, ["OSF"])
        self.assertNotIn("STP_heg_cannibal_campaign_active", f.flags["CIN"])
        self.assertEqual(f.owners["58"], "NKA")
        f.defeat("OSF")
        f.defeat("APH")
        self.assertEqual(set(f.annexed), {"OSF", "APH"})

    def test_new_capitulation_receipt_is_reset_reserved_consumed_and_liberated(self):
        source = read("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt")
        hooks = block(entries("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"), "on_actions")
        immediate = block(block(hooks, "on_capitulation_immediate"), "effect")
        guarded = next(e.value for e in immediate if e.key == "if")
        dispatcher = next(e for e in guarded if e.key == "if" and any(
            c.key == "STP_heg_cannibal_capitulation_managed"
            for c in block(e.value, "limit")
        ))
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.form()
        f.launch()
        f.root = "CIN"
        f.winner = "STS"
        f.execute([dispatcher])
        receipt = "STP_heg_cannibal_capitulation_reserved"
        self.assertIn(receipt, f.flags["CIN"])
        self.assertNotIn("skip_default_capitulation", f.global_flags)
        self.assertFalse(f.annexed)
        self.assertIn("clr_country_flag = " + receipt, named_block(source, "on_capitulation_immediate"))
        self.assertIn("has_country_flag = " + receipt, named_block(source, "on_capitulation"))
        self.assertIn("clr_country_flag = STP_heg_cannibal_defeated", named_block(source, "on_uncapitulation"))

    def test_campaign_cleanup_preserves_another_scripted_major_owner(self):
        f = NorthernAdministrationFixture()
        f.independent_tribes()
        f.form()
        f.majors.add("OSF")
        f.flags["OSF"].add("VAL_frontier_added_major")
        f.launch()
        f.subjects["NKA"] = "ZZZ"
        f.execute(f.effects["STP_heg_reconcile_cannibal_campaign"])
        self.assertEqual(f.majors, {"OSF"})
        self.assertIn("VAL_frontier_added_major", f.flags["OSF"])

    def test_new_focus_positions_and_localisation_are_unique(self):
        focuses = [e.value for e in entries("focus_trees/STP/postwar/shabrat/focuses.txt") if e.key == "focus"]
        for name in ("STP_pc_heg_northern_administration", "STP_pc_heg_cannibal_campaign"):
            selected = [f for f in focuses if scalar(f, "id") == name]
            self.assertEqual(len(selected), 1)
            position = (scalar(selected[0], "x"), scalar(selected[0], "y"))
            self.assertEqual(sum((scalar(f, "x"), scalar(f, "y")) == position for f in focuses), 1)
            for lang in ("russian", "english"):
                source = read(f"localisation/{lang}/ADISCORD_STP_hegemony_l_{lang}.yml")
                for key in (name, name + "_desc"):
                    self.assertEqual(len(re.findall(rf'(?m)^ {key}:\d* "[^"\n]*"$', source)), 1)



class DistrictProjectFixture(NorthernAdministrationFixture):
    """Execute state receipts, producer payments, cancellation and construction."""

    project_names = {
        1: ("STP_sdir_air_defence_project", "STP_pc_sdir_covered_frontier"),
        2: ("STP_sdir_forward_airfield", "STP_pc_sdir_forward_airfields"),
        3: ("STP_sdir_civil_workshop", "STP_pc_sdir_return_to_work"),
    }

    def __init__(self):
        super().__init__()
        self.use_course("directory")
        self.owners.update({str(n): "STS" for n in (10, 11, 24, 42, 43, 44, 55, 58, 59, 60, 61, 62, 63, 64, 65, 88)})
        self.owners.update({"54": "VAL", "57": "VAL"})
        self.controllers = dict(self.owners)
        self.variables["STS", "ADISCORD_economy_treasury"] = 5000
        self.equipment = {
            ("STS", "support_equipment", "STS"): 300,
            ("STS", "support_equipment", "VAL"): 300,
            ("STS", "motorized_equipment", "STS"): 200,
            ("STS", "motorized_equipment", "VAL"): 300,
        }
        self.buildings = {}
        self.slots = {state: 2 for state in self.owners}
        self.decisions = {
            decision.key: decision.value
            for category in entries("common/decisions/ADISCORD_STP_decisions.txt")
            for decision in category.value
            if isinstance(decision.value, list)
        }

    def stock(self, kind, country="STS"):
        return sum(
            amount for (owner, equipment, _producer), amount in self.equipment.items()
            if owner == country and equipment == kind
        )

    def number(self, token, stack):
        try:
            return float(token)
        except ValueError:
            pass
        if token.startswith("num_equipment@"):
            return self.stock(token.split("@", 1)[1], stack[-1])
        scope = stack[-1]
        name = token
        if "." in token:
            prefix, name = token.split(".", 1)
            scope = self.resolve(prefix, stack)
        return self.temporary_variables.get(
            (scope, name), self.variables.get((scope, name), 0)
        )

    @staticmethod
    def compare(left, operator, right):
        return {
            "=": left == right,
            "<": left < right,
            ">": left > right,
            "<=": left <= right,
            ">=": left >= right,
        }[operator]

    @staticmethod
    def groups(rows):
        index = 0
        while index < len(rows):
            size = 1 if rows[index].key else 3
            yield rows[index:index + size]
            index += size

    def matches(self, rows, stack):
        current = stack[-1]
        for group in self.groups(rows):
            entry = group[0]
            key, value = entry.key, entry.value
            if not key:
                name, operator, threshold = (item.value for item in group)
                result = self.compare(
                    self.buildings.get((current, name), 0),
                    operator,
                    self.number(threshold, stack),
                )
            elif key in ("AND", "hidden_trigger", "custom_trigger_tooltip"):
                result = self.matches([item for item in value if item.key != "tooltip"], stack)
            elif key in ("OR", "NOT"):
                result = any(self.matches(part, stack) for part in self.groups(value))
                if key == "NOT":
                    result = not result
            elif key == "check_variable":
                operator = {
                    "equals": "=",
                    "greater_than": ">",
                    "greater_than_or_equals": ">=",
                    "less_than": "<",
                    "less_than_or_equals": "<=",
                }[scalar(value, "compare")]
                result = self.compare(
                    self.number(scalar(value, "var"), stack),
                    operator,
                    self.number(scalar(value, "value"), stack),
                )
            elif key == "has_variable":
                result = (current, value) in self.variables
            elif key == "has_equipment":
                kind, operator, threshold = (item.value for item in value)
                result = self.compare(self.stock(kind, current), operator, float(threshold))
            elif key == "free_building_slots":
                result = self.slots.get(current, 0) > 0
            else:
                result = super().matches([entry], stack)
            if not result:
                return False
        return True

    def execute(self, rows, stack=None):
        stack = stack or [self.root]
        current = stack[-1]
        taken = False
        for entry in rows:
            key, value = entry.key, entry.value
            if key in ("if", "else_if", "else"):
                if key == "if":
                    taken = False
                gate = next((item.value for item in value if item.key == "limit"), [])
                if not taken and self.matches(gate, stack):
                    taken = True
                    self.execute([item for item in value if item.key != "limit"], stack)
            elif key == "hidden_effect":
                self.execute(value, stack)
            elif key in (
                "set_variable", "set_temp_variable", "add_to_variable",
                "subtract_from_variable", "subtract_from_temp_variable",
                "multiply_temp_variable",
            ):
                store = self.temporary_variables if "temp_variable" in key else self.variables
                name = scalar(value, "var")
                amount = self.number(scalar(value, "value"), stack)
                old = store.get((current, name), 0)
                if key.startswith("set"):
                    new = amount
                elif key.startswith("add"):
                    new = old + amount
                elif key.startswith("subtract"):
                    new = old - amount
                else:
                    new = old * amount
                store[current, name] = new
            elif key == "every_possible_country":
                gate = next((item.value for item in value if item.key == "limit"), [])
                body = [item for item in value if item.key != "limit"]
                for country in self.countries:
                    if self.matches(gate, stack + [country]):
                        self.execute(body, stack + [country])
            elif key == "add_equipment_to_stockpile":
                kind = scalar(value, "type")
                amount = self.number(scalar(value, "amount"), stack)
                producer = next((item.value for item in value if item.key == "producer"), current)
                producer = self.resolve(producer, stack)
                receipt = (current, kind, producer)
                self.equipment[receipt] = max(0, self.equipment.get(receipt, 0) + amount)
            elif key == "add_building_construction":
                kind = scalar(value, "type")
                self.buildings[current, kind] = self.buildings.get((current, kind), 0) + int(scalar(value, "level"))
                if kind == "industrial_complex":
                    self.slots[current] -= 1
            elif key in ("custom_effect_tooltip", "tooltip"):
                continue
            else:
                super().execute([entry], stack)

    def begin(self, kind, state="58"):
        name, focus = self.project_names[kind]
        self.completed.add(("STS", focus))
        self.winner = state
        self.execute(block(self.decisions[name], "complete_effect"), ["STS"])

    def finish(self, kind, state="58"):
        name, _focus = self.project_names[kind]
        self.winner = state
        self.execute(block(self.decisions[name], "remove_effect"), ["STS"])

    def cancel(self, kind, state="58"):
        name, _focus = self.project_names[kind]
        self.winner = state
        self.execute(block(self.decisions[name], "cancel_effect"), ["STS"])


class DistrictProjectTests(unittest.TestCase):
    def test_arsenal_extensions_are_not_direct_project_targets(self):
        for state in ("54", "57"):
            for owner in ("VAL", "STS"):
                for kind in (1, 2, 3):
                    with self.subTest(state=state, owner=owner, kind=kind):
                        f = DistrictProjectFixture()
                        f.owners[state] = owner
                        f.controllers[state] = owner
                        f.begin(kind, state)
                        self.assertNotIn((state, "STP_sdir_district_project_kind"), f.variables)
                        targets = block(f.decisions[f.project_names[kind][0]], "targets")
                        self.assertNotIn(state, {e.value for e in targets})
        rear = DistrictProjectFixture().decisions["STP_sdir_rebuild_rear"]
        self.assertEqual({e.value for e in block(rear, "targets")}, {"24", "42", "55"})

    def test_original_stelander_airfield_is_usable_before_foreign_conquests(self):
        f = DistrictProjectFixture()
        f.owners = {"1": "STS"}
        f.controllers = {"1": "STS"}
        f.slots = {"1": 2}
        for kind, expected in ((1, False), (2, True), (3, False)):
            f.begin(kind, "1")
            self.assertEqual(("1", "STP_sdir_district_project_kind") in f.variables, expected)
            if expected:
                f.finish(kind, "1")
        self.assertEqual(f.buildings["1", "air_base"], 2)
        f.begin(2, "1")
        f.execute(f.effects["STP_sdir_refund_all_district_projects"], ["STS"])
        self.assertNotIn(("1", "STP_sdir_district_project_kind"), f.variables)
        self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 4400)

    def test_exact_costs_debit_materials_across_producers_and_award_once(self):
        for kind, price, equipment, amount, building, levels in (
            (1, 350, "support_equipment", 100, "anti_air_building", 2),
            (2, 600, "motorized_equipment", 200, "air_base", 2),
            (3, 900, "support_equipment", 100, "industrial_complex", 1),
        ):
            with self.subTest(kind=kind):
                f = DistrictProjectFixture()
                f.variables["STS", "ADISCORD_economy_treasury"] = price
                f.equipment = {
                    ("STS", equipment, "STS"): amount / 4,
                    ("STS", equipment, "VAL"): amount * 3 / 4,
                }
                f.begin(kind)
                self.assertAlmostEqual(f.stock(equipment), 0)
                self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 0)
                self.assertEqual(f.variables["58", "STP_sdir_district_treasury_deposit"], price)
                f.finish(kind)
                f.finish(kind)
                f.cancel(kind)
                self.assertEqual(f.buildings["58", building], levels)
                self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 0)
                self.assertNotIn(("58", "STP_sdir_district_project_kind"), f.variables)

    def test_fractional_shortage_cannot_start_or_leave_an_unpaid_receipt(self):
        for kind, price, equipment, amount in (
            (1, 350, "support_equipment", 100),
            (2, 600, "motorized_equipment", 200),
            (3, 900, "support_equipment", 100),
        ):
            with self.subTest(kind=kind):
                f = DistrictProjectFixture()
                f.equipment = {("STS", equipment, "VAL"): amount - 0.1}
                f.begin(kind)
                self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 5000)
                self.assertAlmostEqual(f.stock(equipment), amount - 0.1)
                self.assertNotIn(("58", "STP_sdir_district_project_kind"), f.variables)

    def test_distinct_targets_keep_distinct_deposits_and_one_slot_per_state(self):
        f = DistrictProjectFixture()
        f.begin(1, "58")
        f.begin(2, "59")
        balance = f.variables["STS", "ADISCORD_economy_treasury"]
        f.begin(2, "58")
        self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], balance)
        self.assertEqual(f.variables["58", "STP_sdir_district_project_kind"], 1)
        self.assertEqual(f.variables["59", "STP_sdir_district_project_kind"], 2)
        f.cancel(1, "58")
        f.cancel(1, "58")
        self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 4400)
        self.assertEqual(f.stock("support_equipment"), 600)
        f.finish(2, "59")
        self.assertEqual(f.buildings["59", "air_base"], 2)
        self.assertEqual(f.stock("motorized_equipment"), 300)

    def test_lost_site_course_or_capacity_refunds_both_currencies(self):
        for failure in ("owner", "controller", "course", "capitulation", "capacity"):
            with self.subTest(failure=failure):
                f = DistrictProjectFixture()
                f.begin(3)
                if failure == "owner":
                    f.owners["58"] = "ZZZ"
                elif failure == "controller":
                    f.controllers["58"] = "ZZZ"
                elif failure == "course":
                    f.course = "charter"
                elif failure == "capitulation":
                    f.capitulated.add("STS")
                else:
                    f.slots["58"] = 0
                f.finish(3)
                f.cancel(3)
                self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 5000)
                self.assertEqual(f.stock("support_equipment"), 600)
                self.assertFalse(f.buildings)

    def test_caps_clamp_delivery_and_current_save_load_keeps_receipts(self):
        for kind, building, cap in ((1, "anti_air_building", 5), (2, "air_base", 10)):
            with self.subTest(kind=kind):
                f = DistrictProjectFixture()
                f.buildings["58", building] = cap - 1
                f.begin(kind)
                f.temporary_variables.clear()
                f.targets.clear()
                f.finish(kind)
                self.assertEqual(f.buildings["58", building], cap)

    def test_country_loss_refunds_all_bounded_receipts_once(self):
        f = DistrictProjectFixture()
        f.begin(1, "58")
        f.begin(2, "59")
        f.execute(f.effects["STP_sdir_refund_all_district_projects"], ["STS"])
        f.execute(f.effects["STP_sdir_refund_all_district_projects"], ["STS"])
        self.assertEqual(f.variables["STS", "ADISCORD_economy_treasury"], 5000)
        self.assertEqual(f.stock("support_equipment"), 600)
        self.assertEqual(f.stock("motorized_equipment"), 500)
        self.assertFalse(any(name.startswith("STP_sdir_district_") for _scope, name in f.variables))


if __name__ == "__main__":
    unittest.main()
