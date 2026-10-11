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
            if key in ("STP_pc_hegemony_continues", "RUS_crisis_regional_wars_available"):
                result = value == "yes"
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
                super().execute([entry], stack)
                target = self.resolve(scalar(value, "target"), stack)
                self.existing.discard(target)
                self.subjects.pop(target, None)
            elif key == "white_peace":
                # Native peace can end the entire merged war, not just this pair.
                super().execute([entry], stack)
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

    def launch(self):
        self.execute(self.effects["STP_heg_start_cannibal_campaign"], ["STS"])

    def defeat(self, tag):
        self.root = tag
        self.winner = "STS"
        self.execute(self.effects["STP_heg_settle_cannibal_campaign"], [tag])


class NorthernAdministrationTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
