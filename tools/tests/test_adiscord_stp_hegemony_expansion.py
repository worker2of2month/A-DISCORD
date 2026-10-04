from __future__ import annotations

import re
import unittest
from pathlib import Path
from tools.lib.focus_sources import read_focus_source
from tools.tests.test_adiscord_peace_coalition_lifecycle import TreatyFixture
from tools.tests.test_adiscord_stp_preparation import scalar

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

    def test_nod_acceptance_creates_an_annexable_puppet(self) -> None:
        events = read("events/ADISCORD_STP_events.txt")
        effects = read("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        decisions = read("common/decisions/ADISCORD_STP_decisions.txt")
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

    def test_provisional_administrations_are_closed_and_annexable(self) -> None:
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
            self.assertIn(f"STP_heg_annex_{key}_administration = {{", decisions)
        self.assertEqual(named_block(decisions, "STP_hegemony_administration").count("days_remove = 90"), 4)
        self.assertEqual(
            named_block(decisions, "STP_hegemony_administration").count("cost = 100"), 4
        )
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
        self.capitulated = set()
        self.variables["STS", "STP_pc_cap_side"] = 1 if opponent == "VAL" else 2
        self.variables["STS", "STP_pc_course"] = course
        self.wars = {frozenset(("STS", opponent)), frozenset(("VAL", "ZZZ"))}
        self.flags["STS"].add("STP_cw_postwar")
        self.stubs.update({
            "ADISCORD_economy_initialize_country",
            "ADISCORD_economy_update_postwar_demobilization",
            "VAL_enforce_stelander_defeat",
            "STP_pc_clear_settlement",
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
        self.execute(self.effects["STP_pc_begin_settlement"])


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


if __name__ == "__main__":
    unittest.main()
