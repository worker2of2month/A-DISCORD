from __future__ import annotations
from tools.lib.on_actions import read_country_on_actions

from pathlib import Path
from tools.lib.focus_sources import read_focus_source
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]

FOCUS_FILE = ROOT / "common/national_focus/ADISCORD_national_focus_RUS.txt"
DECISION_FILE = ROOT / "common/decisions/ADISCORD_vorkerland_decisions.txt"
CATEGORY_FILE = ROOT / "common/decisions/categories/ADISCORD_vorkerland_categories.txt"
EFFECT_FILE = ROOT / "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
TRIGGER_FILE = ROOT / "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
PLAN_FILE = ROOT / "common/ai_strategy_plans/ADISCORD_vorkerland_plans.txt"
AI_FILE = ROOT / "common/ai_strategy/ADISCORD_vorkerland_ai.txt"
ON_ACTIONS = ROOT / "common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"
IDEA_FILE = ROOT / "common/ideas/ADISCORD_country_unique_ideas.txt"
RUSSIAN_LOC = ROOT / "localisation/russian/ADISCORD_vorkerland_l_russian.yml"
IDEA_LOC = ROOT / "localisation/russian/ADISCORD_ideas_l_russian.yml"
COUNTRY_LOC = ROOT / "localisation/russian/countries_l_russian.yml"
ENGLISH_LOC = ROOT / "localisation/english/ADISCORD_vorkerland_l_english.yml"

RUS_FOCUS_IDS = (
    "RUS_summon_the_aimaqs",
    "RUS_arm_the_border_hosts",
    "RUS_watch_the_western_scar",
    "RUS_claim_the_opened_zone",
    "RUS_drive_starolesye_back",
    "RUS_press_the_closed_zone",
    "RUS_seat_the_khan_chancery",
)

RUS_DECISIONS = (
    "RUS_campaign_sla",
    "RUS_campaign_rza",
    "RUS_campaign_mlr",
    "RUS_campaign_ert",
    "RUS_campaign_irt",
    "RUS_campaign_sca",
    "RUS_proclaim_the_last_empire",
)

LOC_KEYS = (
    *RUS_FOCUS_IDS,
    *(f"{focus_id}_desc" for focus_id in RUS_FOCUS_IDS),
    "RUS_summon_the_aimaqs_tt",
    "RUS_arm_the_border_hosts_tt",
    "RUS_watch_the_western_scar_tt",
    "RUS_claim_the_opened_zone_tt",
    "RUS_claim_the_opened_zone_available_tt",
    "RUS_drive_starolesye_back_available_tt",
    "RUS_press_the_closed_zone_available_tt",
    "RUS_seat_the_khan_chancery_available_tt",
    "RUS_proclaim_the_last_empire_peace_tt",
    "ADISCORD_vorkerland_rus_dirty_campaign_category",
    "ADISCORD_vorkerland_rus_dirty_campaign_category_desc",
    *RUS_DECISIONS,
    *(f"{decision_id}_desc" for decision_id in RUS_DECISIONS),
    "RUS_campaign_sla_tt",
    "RUS_campaign_rza_tt",
    "RUS_campaign_mlr_tt",
    "RUS_campaign_ert_tt",
    "RUS_campaign_irt_tt",
    "RUS_campaign_sca_tt",
    "RUS_campaign_sla_border_tt",
    "RUS_campaign_rza_border_tt",
    "RUS_campaign_mlr_border_tt",
    "RUS_campaign_ert_border_tt",
    "RUS_campaign_irt_border_tt",
    "RUS_campaign_sca_border_tt",
    "RUS_proclaim_the_last_empire_available_tt",
    "RUS_last_empire_cosmetic_tt",
)


def read(path: Path) -> str:
    return read_focus_source(path)


def localisation_entries(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'(?m)^\s+([A-Za-z0-9_]+):(?:\d+)?\s+"(.*)"\s*$', text)
    }


class RusLastEmpireTests(unittest.TestCase):
    def test_proclamation_keeps_khan_in_new_ruling_party_with_dictator_portrait(self):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block
        effect = named_block(read(EFFECT_FILE), "ADISCORD_vorkerland_rus_proclaim_last_empire")
        self.assertIn("character = RUS_Mark_Rustan", effect)
        self.assertIn("ideology = chauvinism_ideology", effect)
        self.assertIn("set_portraits", effect)
        self.assertIn("GFX_portrait_RUS_Mark_Rustan_dictator", effect)
        self.assertIn("GFX_portrait_RUS_Mark_Rustan_dictator", read(ROOT / "interface/ADISCORD_leader_portraits.gfx"))

    def test_border_peace_preserves_other_occupied_sla_states(self):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block
        effect = named_block(read(EFFECT_FILE), "ADISCORD_vorkerland_resolve_khan_border_war")
        sweep = named_block(effect, "every_controlled_state")
        self.assertIn("is_owned_by = SLA", sweep)
        self.assertIn("set_state_owner_to = RUS", sweep)
        self.assertLess(effect.index("every_controlled_state"), effect.index("white_peace ="))

    def test_every_closed_zone_state_has_exactly_one_opening_successor(self) -> None:
        from tools.lib.vorkerland_collapse_manifest import DIRTY_GROUPS, EXZ_REMAINDER_GROUPS
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read(EFFECT_FILE)
        assigned = []
        for tag, states in DIRTY_GROUPS.items():
            expected = set(states) | set(EXZ_REMAINDER_GROUPS.get(tag, ()))
            setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            actual = set(map(int, re.findall(
                rf"(\d+)\s*=\s*\{{\s*add_core_of = {tag} set_state_owner_to = {tag} set_state_controller_to = {tag}",
                setup,
            )))
            self.assertEqual(actual, expected, tag)
            assigned.extend(actual)
            cores = named_block(effects, f"ADISCORD_vorkerland_rus_core_dirty_{tag.lower()}")
            rus_cores = set(map(int, re.findall(r"(\d+)\s*=\s*\{\s*add_core_of = RUS", cores)))
            self.assertEqual(rus_cores, expected - {168}, tag)
        self.assertEqual(len(assigned), len(set(assigned)))
        for path in (ROOT / "history/states").glob("*.txt"):
            source = read(path)
            if re.search(r"\bowner\s*=\s*EXZ\b", source):
                state = int(re.search(r"\bid\s*=\s*(\d+)", source).group(1))
                self.assertIn(state, assigned, path.name)

    def test_dirty_republics_build_internal_rail_corridors(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read(EFFECT_FILE)
        corridors = {
            "sla": (49, 191),
            "rza": (177, 220),
            "mlr": (152, 189),
            "ert": (169, 171),
            "irt": (181, 178),
            "sca": (173, 211),
        }
        for suffix, (start, target) in corridors.items():
            setup = named_block(effects, f"ADISCORD_vorkerland_setup_{suffix}")
            self.assertIn(
                f"build_railway = {{ level = 2 fallback = yes start_state = {start} target_state = {target} }}",
                setup,
                suffix,
            )

    def test_opened_zone_load_repair_preserves_conquests_and_follows_current_owner(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read(EFFECT_FILE)
        repair = named_block(effects, "ADISCORD_vorkerland_reconcile_dirty_zone_remainder")
        self.assertIn("has_global_flag = ADISCORD_vorkerland_dirty_opened", repair)
        self.assertIn("461 = { is_owned_by = EXZ }", repair)
        self.assertIn("51 = { NOT = { is_owned_by = EXZ } }", repair)
        destination = named_block(repair, "owner")
        transfer = named_block(destination, "461")
        self.assertIn("set_state_owner_to = PREV", transfer)
        self.assertIn("set_state_controller_to = PREV", transfer)
        startup = named_block(read_country_on_actions(ON_ACTIONS, 'vorkerland_collapse'), "on_startup")
        self.assertIn("ADISCORD_vorkerland_reconcile_dirty_zone_remainder = yes", startup)

    def test_focus_tree_is_assigned_to_rus_and_lists_the_ai_branch(self) -> None:
        source = read(FOCUS_FILE)
        self.assertIn("id = RUS_focus", source)
        self.assertIn("original_tag = RUS", source)
        self.assertNotIn("declare_war_on", source)
        self.assertNotIn("create_faction =", source)
        for focus_id in RUS_FOCUS_IDS:
            self.assertIn(f"id = {focus_id}", source)
            self.assertIn("ai_will_do =", source[source.index(f"id = {focus_id}"):])
        self.assertIn("unlock_decision_tooltip = RUS_campaign_sla", source)
        self.assertIn("unlock_decision_tooltip = RUS_proclaim_the_last_empire", source)
        self.assertIn("create_unit", source)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_rus_sla_absorbed", source)
        self.assertNotIn("ADISCORD_vorkerland_rus_aimaqs_summoned", source)
        self.assertIn("swap_ideas = { remove_idea = RUS_national_spirit add_idea = RUS_last_empire_spirit }", source)

    def test_ai_plan_drives_the_authored_branch(self) -> None:
        plan = read(PLAN_FILE)
        self.assertIn("# --- rus_last_empire_plan ---", plan)
        start = plan.index("ADISCORD_vorkerland_rus_last_empire_plan = {")
        body = plan[start:]
        ordered = tuple(re.findall(r"(?m)^\s*(RUS_[A-Za-z0-9_]+)\s*$", body))
        self.assertEqual(ordered, RUS_FOCUS_IDS)
        self.assertIn("is_ai = yes", body)

    def test_decisions_are_scripted_wars_with_one_campaign_escrow(self) -> None:
        decisions = read(DECISION_FILE)
        categories = read(CATEGORY_FILE)
        self.assertIn("ADISCORD_vorkerland_rus_dirty_campaign_category", categories)
        self.assertIn("allowed = { tag = RUS }", categories)
        for decision_id in RUS_DECISIONS:
            self.assertIn(f"{decision_id} = {{", decisions)
            block_start = decisions.index(f"\t{decision_id} = {{")
            block = decisions[block_start:block_start + 900]
            self.assertIn("allowed = { tag = RUS }", block)
            self.assertIn("ai_will_do", block)
        self.assertNotIn("declare_war_on", decisions[decisions.index("ADISCORD_vorkerland_rus_dirty_campaign_category"):])
        effects = read(EFFECT_FILE)
        self.assertIn("declare_war_on = { target = SLA type = annex_everything }", effects)
        self.assertIn("NOT = { has_war_with = SLA }", effects)
        self.assertIn("set_cosmetic_tag = RUS_last_empire", effects)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", effects)
        self.assertIn("RUS_last_empire = {", (ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8"))
        self.assertIn("ADISCORD_vorkerland_rus_can_open_sla_front = {", read(TRIGGER_FILE))
        self.assertIn("ADISCORD_vorkerland_rus_campaign_target_still_open = {", read(TRIGGER_FILE))
        self.assertNotIn("fire_only_once = yes", decisions[decisions.index("RUS_campaign_sla"):decisions.index("RUS_proclaim_the_last_empire")])

    def test_triggers_are_boolean_calls(self) -> None:
        triggers = read(TRIGGER_FILE)
        for name in (
            "ADISCORD_vorkerland_rus_dirty_campaign_idle",
            "ADISCORD_vorkerland_rus_can_proclaim_last_empire",
            "ADISCORD_vorkerland_rus_borders_dirty_sla",
        ):
            self.assertIn(f"{name} = {{", triggers)
        self.assertNotIn("ADISCORD_vorkerland_rus_can_proclaim_last_empire = {", read(FOCUS_FILE))

    def test_runtime_hooks_and_fronts_exist(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block
        on_actions = read_country_on_actions(ON_ACTIONS, 'vorkerland_collapse')
        self.assertIn("on_monthly_RUS", on_actions)
        self.assertIn("ADISCORD_vorkerland_check_rus_dirty_campaign = yes", on_actions)
        capitulation = named_block(on_actions, "on_capitulation")
        self.assertIn("set_global_flag = skip_default_capitulation", capitulation)
        self.assertIn("ADISCORD_vorkerland_check_khan_border_war = yes", capitulation)
        ai = read(AI_FILE)
        for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
            self.assertIn(f"conquer id = {tag} value = 200", ai)

    def test_empire_spirit_and_second_flag_exist(self) -> None:
        ideas = read(IDEA_FILE)
        self.assertIn("RUS_last_empire_spirit = {", ideas)
        self.assertIn("RUS_last_empire_spirit", read(IDEA_LOC))
        self.assertTrue((ROOT / "gfx/flags/RUS_last_empire.tga").exists())
        self.assertTrue((ROOT / "gfx/flags/medium/RUS_last_empire.tga").exists())
        self.assertTrue((ROOT / "gfx/flags/small/RUS_last_empire.tga").exists())
        countries = read(COUNTRY_LOC)
        self.assertIn('RUS_last_empire: "Последняя империя"', countries)
        self.assertIn("RUS_last_empire_DEF", countries)
        self.assertIn("RUS_last_empire_ADJ", countries)

    def test_russian_localisation_has_bom_and_required_keys(self) -> None:
        raw = RUSSIAN_LOC.read_bytes()
        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "Russian Vorkerland loc must keep a UTF-8 BOM")
        entries = localisation_entries(read(RUSSIAN_LOC))
        english = localisation_entries(read(ENGLISH_LOC))
        for key in LOC_KEYS:
            with self.subTest(key=key):
                self.assertTrue(entries.get(key), f"missing Russian {key}")
                self.assertNotIn("зоне отчуждения", entries[key])
                self.assertTrue(english.get(key), f"missing English {key}")
        idea_entries = localisation_entries(read(IDEA_LOC))
        self.assertTrue(idea_entries.get("RUS_last_empire_spirit"))
        self.assertTrue(idea_entries.get("RUS_last_empire_spirit_desc"))

    def test_hold_triggers_match_playable_dirty_groups(self) -> None:
        from tools.lib.vorkerland_collapse_manifest import DIRTY_GROUPS

        triggers = read(TRIGGER_FILE)
        expected = {
            "sla": DIRTY_GROUPS["SLA"],
            "rza": tuple(state for state in DIRTY_GROUPS["RZA"] if state != 125),
            "mlr": DIRTY_GROUPS["MLR"],
            "ert": tuple(state for state in DIRTY_GROUPS["ERT"] if state != 168),
            "irt": DIRTY_GROUPS["IRT"],
            "sca": DIRTY_GROUPS["SCA"],
        }
        for suffix, states in expected.items():
            block = re.search(
                rf"ADISCORD_vorkerland_rus_holds_{suffix}_playable = \{{(.*?)\n\}}",
                triggers,
                re.S,
            )
            self.assertIsNotNone(block, suffix)
            found = tuple(int(value) for value in re.findall(r"controls_state = (\d+)", block.group(1)))
            self.assertEqual(found, states, suffix)

    def test_claimant_rewards_hide_dispatchers_and_keep_focus_unlocks_compact(self) -> None:
        focus = read(ROOT / "common/national_focus/ADISCORD_vorkerland_focus.txt")
        self.assertNotRegex(focus, r"(?m)^\t\t\tcountry_event =")
        self.assertNotIn("show_effect_tooltip = yes", focus)
        self.assertIn("ADISCORD_vorkerland_wkr_war_economy_dummy", focus)
        self.assertIn("ADISCORD_vorkerland_wkr_war_economy_strip", read(ROOT / "common/ideas/ADISCORD_vorkerland_ideas.txt"))
        plans = read(PLAN_FILE)
        self.assertIn("ADISCORD_vorkerland_wrk_prewar_compact_plan", plans)
        self.assertIn("ADISCORD_vorkerland_zao_plan", plans)
        self.assertIn("ADISCORD_vorkerland_iba_plan", plans)


SLA_STATES = (49, 51, 155, 176, 187, 191)


class RusDirtyCampaignRoutes(unittest.TestCase):
    def setUp(self) -> None:
        from tools.tests.test_adiscord_stp_preparation import (
            block,
            entries,
            matches_conditions,
            selected_effects,
        )
        from tools.validators.validate_adiscord_division_templates import Entry

        self.block = block
        self.entries = entries
        self.matches = matches_conditions
        self.selected = selected_effects
        self.effects = entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        self.triggers = entries("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
        definitions = {e.key: e.value for e in self.triggers}

        def expand(items, parameters=None):
            parameters = parameters or {}
            result = []
            for entry in items:
                key = parameters.get(entry.key, entry.key)
                value = (
                    expand(entry.value, parameters) if isinstance(entry.value, list)
                    else parameters.get(entry.value, entry.value)
                )
                if key in definitions:
                    if entry.value not in ("yes", "no"):
                        raise AssertionError(f"Unsupported native scripted trigger call: {key}")
                    value = expand(definitions[key], parameters)
                    result.append(Entry("AND" if entry.value != "no" else "NOT", value, entry.line))
                else:
                    result.append(Entry(key, value, entry.line, entry.quoted))
            return result

        self.expand = expand

    def _hold_sla(self, held: bool) -> dict:
        return {("RUS", "controls_state", str(state)): held for state in SLA_STATES}

    def _active(self, target=1, extra=None) -> dict:
        facts = {
            ("RUS", "tag", "RUS"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_dirty_campaign_active"): True,
            ("RUS", "variable", "ADISCORD_vorkerland_rus_campaign_target"): target,
            ("RUS", "has_capitulated", "yes"): False,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_last_empire_proclaimed"): False,
        }
        facts.update(self._hold_sla(False))
        if extra:
            facts.update(extra)
        return facts

    def _run(self, name, facts):
        return list(self.selected(self.expand(self.block(self.effects, name)), facts, "RUS"))

    def _calls(self, chosen):
        return [e.key for _, e in chosen]

    def test_normal_victory_requires_territory_and_counts_the_neighbor_once(self) -> None:
        held = self._active(extra=self._hold_sla(True))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", held)
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check))
        settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", {
            **held,
            ("RUS", "country_exists", "SLA"): True,
        })
        self.assertIn("ADISCORD_vorkerland_rus_annex_dirty_target", self._calls(settle))
        annex = self._run("ADISCORD_vorkerland_rus_annex_dirty_target", {
            **held,
            ("RUS", "country_exists", "SLA"): True,
        })
        self.assertTrue(any(e.key == "annex_country" for _, e in annex))
        self.assertIn(("RUS", "ADISCORD_vorkerland_rus_sla_absorbed"), [(s, e.value) for s, e in settle if e.key == "set_country_flag"])
        self.assertIn(("RUS", "ADISCORD_vorkerland_rus_sla_counted"), [(s, e.value) for s, e in settle if e.key == "set_country_flag"])
        self.assertTrue(any(e.key == "add_to_variable" for _, e in settle))
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(settle))
        repeat = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", {
            **held,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_sla_counted"): True,
        })
        self.assertFalse(any(e.key == "add_to_variable" for _, e in repeat), "repeat occupation must not increment again")
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(repeat))

    def test_third_party_or_vanished_target_aborts_without_credit(self) -> None:
        still_open = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_campaign_target_still_open"))
        vanished = self._active()
        self.assertTrue(self.matches(still_open, vanished, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", vanished)
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", vanished)
        self.assertFalse(any(e.key in {"add_to_variable", "annex_country"} for _, e in settle))

    def test_live_war_without_control_waits_instead_of_hanging_or_awarding(self) -> None:
        waiting = self._active(extra={("RUS", "has_war_with", "SLA"): True})
        still_open = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_campaign_target_still_open"))
        holds = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_holds_current_target"))
        ready = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_current_target_ready"))
        self.assertFalse(self.matches(still_open, waiting, "RUS"))
        self.assertFalse(self.matches(holds, waiting, "RUS"))
        self.assertFalse(self.matches(ready, waiting, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", waiting)
        self.assertNotIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))

    def test_capitulated_target_settles_without_full_occupation(self) -> None:
        capitulated = self._active(extra={
            ("RUS", "has_war_with", "SLA"): True,
            ("RUS", "country_exists", "SLA"): True,
            ("SLA", "has_capitulated", "yes"): True,
            ("SLA", "capital"): "170",
            ("170", "is_controlled_by", "RUS"): True,
        })
        ready = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_current_target_ready"))
        self.assertTrue(self.matches(ready, capitulated, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", capitulated)
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", capitulated)
        self.assertIn("ADISCORD_vorkerland_rus_annex_dirty_target", self._calls(settle))
        annex = self._run("ADISCORD_vorkerland_rus_annex_dirty_target", capitulated)
        self.assertTrue(any(e.key == "annex_country" for _, e in annex))
        self.assertTrue(any(e.key == "every_owned_state" for _, e in annex))

    def test_foreign_capitulation_cannot_award_rus_another_countrys_victory(self):
        for target, tag in enumerate(("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"), 1):
            facts = self._active(target, {
                ("RUS", "has_war_with", tag): True,
                ("RUS", "country_exists", tag): True,
                (tag, "has_capitulated", "yes"): True,
                (tag, "capital"): "999", ("999", "is_controlled_by", "VAL"): True,
            })
            ready = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_current_target_ready"))
            self.assertFalse(self.matches(ready, facts, "RUS"), tag)
            settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", facts)
            self.assertNotIn("ADISCORD_vorkerland_rus_annex_dirty_target", self._calls(settle), tag)
            won = {**facts, ("999", "is_controlled_by", "RUS"): True}
            self.assertTrue(self.matches(ready, won, "RUS"), tag)
            self.assertIn("ADISCORD_vorkerland_rus_annex_dirty_target",
                          self._calls(self._run("ADISCORD_vorkerland_rus_settle_dirty_target", won)), tag)

    def test_border_war_absorbs_a_fully_occupied_republic(self) -> None:
        occupied = {
            ("RUS", "has_global_flag", "ADISCORD_vorkerland_khan_border_war_started"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_dirty_campaign_active"): False,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_war_with", "SLA"): True,
            ("RUS", "variable", "ADISCORD_vorkerland_rus_campaign_target"): 0,
            **self._hold_sla(True),
        }
        check = self._run("ADISCORD_vorkerland_check_khan_border_war", occupied)
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_resolve_khan_border_war", self._calls(check))

    def test_border_war_belt_still_white_peaces(self) -> None:
        belt = {
            ("RUS", "has_global_flag", "ADISCORD_vorkerland_khan_border_war_started"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_dirty_campaign_active"): False,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_war_with", "SLA"): True,
            ("RUS", "controls_state", "49"): True,
            ("RUS", "controls_state", "176"): True,
            **self._hold_sla(False),
        }
        belt[("RUS", "controls_state", "49")] = True
        belt[("RUS", "controls_state", "176")] = True
        check = self._run("ADISCORD_vorkerland_check_khan_border_war", belt)
        self.assertIn("ADISCORD_vorkerland_resolve_khan_border_war", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        resolve = self._run("ADISCORD_vorkerland_resolve_khan_border_war", belt)
        self.assertTrue(any(e.key == "white_peace" for _, e in resolve))
        self.assertTrue(any(scope == "49" and e.key == "set_state_owner_to" for scope, e in resolve))
        self.assertTrue(any(scope == "176" and e.key == "set_state_owner_to" for scope, e in resolve))
        white_peace_pos = next(i for i, (_, e) in enumerate(resolve) if e.key == "white_peace")
        first_transfer = next(
            i for i, (scope, e) in enumerate(resolve)
            if scope in {"49", "176"} and e.key == "set_state_owner_to"
        )
        self.assertLess(first_transfer, white_peace_pos)

    def test_border_capitulation_annexes_before_partial_peace(self):
        facts = {
            ("RUS", "has_global_flag", "ADISCORD_vorkerland_khan_border_war_started"): True,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_war_with", "SLA"): True,
            ("SLA", "has_capitulated", "yes"): True,
            ("SLA", "capital"): "51",
            ("51", "is_controlled_by", "RUS"): True,
            **self._hold_sla(False),
        }
        calls = self._calls(self._run("ADISCORD_vorkerland_check_khan_border_war", facts))
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", calls)
        self.assertNotIn("ADISCORD_vorkerland_resolve_khan_border_war", calls)

    def test_invalid_target_or_own_capitulation_clears_the_operation(self) -> None:
        invalid = self._active(target=0)
        self.assertTrue(self.matches(self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_campaign_target_still_open")), invalid, "RUS"))
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", invalid)))
        own_loss = self._active(extra={("RUS", "has_capitulated", "yes"): True, ("RUS", "has_war_with", "SLA"): True})
        lost = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", own_loss)
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(lost))
        self.assertNotIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(lost))

    def test_liberation_clears_absorbed_and_allows_a_repeat_campaign(self) -> None:
        liberated = {
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_sla_absorbed"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_sla_counted"): True,
            ("RUS", "has_war_with", "SLA"): False,
            **self._hold_sla(False),
        }
        released = self._run("ADISCORD_vorkerland_rus_release_lost_absorptions", liberated)
        self.assertIn(("RUS", "ADISCORD_vorkerland_rus_sla_absorbed"), [(s, e.value) for s, e in released if e.key == "clr_country_flag"])
        self.assertNotIn(("RUS", "ADISCORD_vorkerland_rus_sla_counted"), [(s, e.value) for s, e in released if e.key == "clr_country_flag"])
        decisions = read(DECISION_FILE)
        sla = decisions[decisions.index("\tRUS_campaign_sla = {"):decisions.index("\tRUS_campaign_rza = {")]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_sla_absorbed }", sla)
        rza = decisions[decisions.index("\tRUS_campaign_rza = {"):decisions.index("\tRUS_campaign_mlr = {")]
        self.assertIn("NOT = { has_country_flag = ADISCORD_vorkerland_rus_rza_absorbed }", rza)

    def test_empire_gate_accepts_three_held_belts_or_no_independent_republics(self) -> None:
        from tools.lib.vorkerland_collapse_manifest import DIRTY_GROUPS

        gate = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_has_empire_territory"))
        excluded = {"RZA": {125}, "ERT": {168}}

        def territory(*held_tags: str) -> dict:
            held = set(held_tags)
            facts = {}
            for tag, states in DIRTY_GROUPS.items():
                for state in states:
                    if state in excluded.get(tag, set()):
                        continue
                    facts[("RUS", "controls_state", str(state))] = tag in held
            for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
                facts[("RUS", "country_exists", tag)] = True
                facts[(tag, "is_subject", "yes")] = False
            return facts

        self.assertTrue(self.matches(gate, territory("SLA", "RZA", "MLR"), "RUS"))
        self.assertTrue(self.matches(gate, territory("ERT", "IRT", "SCA"), "RUS"))
        self.assertFalse(self.matches(gate, territory("SLA", "RZA"), "RUS"))

        no_republics = territory()
        for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
            no_republics[("RUS", "country_exists", tag)] = False
        self.assertTrue(self.matches(gate, no_republics, "RUS"))

        source = read(TRIGGER_FILE)
        gate_start = source.index("ADISCORD_vorkerland_rus_has_empire_territory = {")
        gate_body = source[gate_start:source.index("\n}", gate_start) + 2]
        self.assertNotIn("dirty_neighbors_taken", gate_body)


if __name__ == "__main__":
    unittest.main()
