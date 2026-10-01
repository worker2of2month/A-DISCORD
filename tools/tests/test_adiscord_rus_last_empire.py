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
    "RUS_imperial_general_staff",
    "RUS_western_supply_lines",
    "RUS_imperial_arsenals",
    "RUS_aimaq_reserve",
    "RUS_break_the_hegemon",
    "RUS_register_conquered_lands",
    "RUS_empire_without_rivals",
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

        effect = named_block(
            read(EFFECT_FILE), "ADISCORD_vorkerland_rus_proclaim_last_empire"
        )
        self.assertIn("character = RUS_Mark_Rustan", effect)
        self.assertIn("ideology = chauvinism_ideology", effect)
        self.assertIn("set_portraits", effect)
        self.assertIn("GFX_portrait_RUS_Mark_Rustan_dictator", effect)
        self.assertIn(
            "GFX_portrait_RUS_Mark_Rustan_dictator",
            read(ROOT / "interface/ADISCORD_leader_portraits.gfx"),
        )

    def test_border_peace_preserves_other_occupied_sla_states(self):
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effect = named_block(
            read(EFFECT_FILE), "ADISCORD_vorkerland_resolve_khan_border_war"
        )
        sweep = named_block(effect, "every_controlled_state")
        self.assertIn("is_owned_by = SLA", sweep)
        self.assertIn("set_state_owner_to = RUS", sweep)
        self.assertLess(
            effect.index("every_controlled_state"), effect.index("white_peace =")
        )

    def test_every_closed_zone_state_has_exactly_one_opening_successor(self) -> None:
        from tools.lib.vorkerland_collapse_manifest import (
            DIRTY_GROUPS,
            EXZ_REMAINDER_GROUPS,
        )
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read(EFFECT_FILE)
        assigned = []
        for tag, states in DIRTY_GROUPS.items():
            expected = set(states) | set(EXZ_REMAINDER_GROUPS.get(tag, ()))
            setup = named_block(effects, f"ADISCORD_vorkerland_setup_{tag.lower()}")
            actual = set(
                map(
                    int,
                    re.findall(
                        rf"(\d+)\s*=\s*\{{\s*add_core_of = {tag} set_state_owner_to = {tag} set_state_controller_to = {tag}",
                        setup,
                    ),
                )
            )
            self.assertEqual(actual, expected, tag)
            assigned.extend(actual)
            cores = named_block(
                effects, f"ADISCORD_vorkerland_rus_core_dirty_{tag.lower()}"
            )
            rus_cores = set(
                map(int, re.findall(r"(\d+)\s*=\s*\{\s*add_core_of = RUS", cores))
            )
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

    def test_opened_zone_load_repair_preserves_conquests_and_follows_current_owner(
        self,
    ) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        effects = read(EFFECT_FILE)
        repair = named_block(
            effects, "ADISCORD_vorkerland_reconcile_dirty_zone_remainder"
        )
        self.assertIn("has_global_flag = ADISCORD_vorkerland_dirty_opened", repair)
        self.assertIn("461 = { is_owned_by = EXZ }", repair)
        self.assertIn("51 = { NOT = { is_owned_by = EXZ } }", repair)
        destination = named_block(repair, "owner")
        transfer = named_block(destination, "461")
        self.assertIn("set_state_owner_to = PREV", transfer)
        self.assertIn("set_state_controller_to = PREV", transfer)
        startup = named_block(
            read_country_on_actions(ON_ACTIONS, 'vorkerland_collapse'), "on_startup"
        )
        self.assertIn(
            "ADISCORD_vorkerland_reconcile_dirty_zone_remainder = yes", startup
        )

    def test_focus_tree_is_assigned_to_rus_and_lists_the_ai_branch(self) -> None:
        source = read(FOCUS_FILE)
        self.assertIn("id = RUS_focus", source)
        self.assertIn("original_tag = RUS", source)
        self.assertNotIn("declare_war_on", source)
        self.assertNotIn("create_faction =", source)
        for focus_id in RUS_FOCUS_IDS:
            self.assertIn(f"id = {focus_id}", source)
            self.assertIn("ai_will_do =", source[source.index(f"id = {focus_id}") :])
        self.assertIn("unlock_decision_tooltip = RUS_campaign_sla", source)
        self.assertIn("unlock_decision_tooltip = RUS_proclaim_the_last_empire", source)
        self.assertIn("create_unit", source)
        self.assertIn("has_country_flag = ADISCORD_vorkerland_rus_sla_absorbed", source)
        self.assertNotIn("ADISCORD_vorkerland_rus_aimaqs_summoned", source)
        self.assertIn(
            "swap_ideas = { remove_idea = RUS_national_spirit add_idea = RUS_last_empire_spirit }",
            source,
        )

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
            block = decisions[block_start : block_start + 900]
            self.assertIn("allowed = { tag = RUS }", block)
            self.assertIn("ai_will_do", block)
        self.assertNotIn(
            "declare_war_on",
            decisions[
                decisions.index("ADISCORD_vorkerland_rus_dirty_campaign_category") :
            ],
        )
        effects = read(EFFECT_FILE)
        self.assertIn(
            "declare_war_on = { target = SLA type = annex_everything }", effects
        )
        self.assertIn("NOT = { has_war_with = SLA }", effects)
        self.assertIn("set_cosmetic_tag = RUS_last_empire", effects)
        self.assertIn("ADISCORD_economy_mark_dirty = yes", effects)
        self.assertIn(
            "RUS_last_empire = {",
            (ROOT / "common/countries/cosmetic.txt").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "ADISCORD_vorkerland_rus_can_open_sla_front = {", read(TRIGGER_FILE)
        )
        self.assertIn(
            "ADISCORD_vorkerland_rus_campaign_target_still_open = {", read(TRIGGER_FILE)
        )
        self.assertNotIn(
            "fire_only_once = yes",
            decisions[
                decisions.index("RUS_campaign_sla") : decisions.index(
                    "RUS_proclaim_the_last_empire"
                )
            ],
        )

    def test_triggers_are_boolean_calls(self) -> None:
        triggers = read(TRIGGER_FILE)
        for name in (
            "ADISCORD_vorkerland_rus_dirty_campaign_idle",
            "ADISCORD_vorkerland_rus_can_proclaim_last_empire",
            "ADISCORD_vorkerland_rus_borders_dirty_sla",
        ):
            self.assertIn(f"{name} = {{", triggers)
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_can_proclaim_last_empire = {", read(FOCUS_FILE)
        )

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
        self.assertTrue(
            raw.startswith(b"\xef\xbb\xbf"),
            "Russian Vorkerland loc must keep a UTF-8 BOM",
        )
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
            found = tuple(
                int(value)
                for value in re.findall(r"controls_state = (\d+)", block.group(1))
            )
            self.assertEqual(found, states, suffix)

    def test_claimant_rewards_hide_dispatchers_and_keep_focus_unlocks_compact(
        self,
    ) -> None:
        focus = read(ROOT / "common/national_focus/ADISCORD_vorkerland_focus.txt")
        self.assertNotRegex(focus, r"(?m)^\t\t\tcountry_event =")
        self.assertNotIn("show_effect_tooltip = yes", focus)
        self.assertIn("ADISCORD_vorkerland_wkr_war_economy_dummy", focus)
        self.assertIn(
            "ADISCORD_vorkerland_wkr_war_economy_strip",
            read(ROOT / "common/ideas/ADISCORD_vorkerland_ideas.txt"),
        )
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
        self.effects = entries(
            "common/scripted_effects/ADISCORD_vorkerland_effects.txt"
        )
        self.triggers = entries(
            "common/scripted_triggers/ADISCORD_vorkerland_triggers.txt"
        )
        definitions = {e.key: e.value for e in self.triggers}

        def expand(items, parameters=None):
            parameters = parameters or {}
            result = []
            for entry in items:
                key = parameters.get(entry.key, entry.key)
                value = (
                    expand(entry.value, parameters)
                    if isinstance(entry.value, list)
                    else parameters.get(entry.value, entry.value)
                )
                if key in definitions:
                    if entry.value not in ("yes", "no"):
                        raise AssertionError(
                            f"Unsupported native scripted trigger call: {key}"
                        )
                    value = expand(definitions[key], parameters)
                    result.append(
                        Entry(
                            "AND" if entry.value != "no" else "NOT", value, entry.line
                        )
                    )
                else:
                    result.append(Entry(key, value, entry.line, entry.quoted))
            return result

        self.expand = expand

    def _hold_sla(self, held: bool) -> dict:
        return {("RUS", "controls_state", str(state)): held for state in SLA_STATES}

    def _active(self, target=1, extra=None) -> dict:
        facts = {
            ("RUS", "tag", "RUS"): True,
            (
                "RUS",
                "has_country_flag",
                "ADISCORD_vorkerland_rus_dirty_campaign_active",
            ): True,
            ("RUS", "variable", "ADISCORD_vorkerland_rus_campaign_target"): target,
            ("RUS", "has_capitulated", "yes"): False,
            (
                "RUS",
                "has_country_flag",
                "ADISCORD_vorkerland_rus_last_empire_proclaimed",
            ): False,
        }
        facts.update(self._hold_sla(False))
        if extra:
            facts.update(extra)
        return facts

    def _run(self, name, facts):
        return list(
            self.selected(self.expand(self.block(self.effects, name)), facts, "RUS")
        )

    def _calls(self, chosen):
        return [e.key for _, e in chosen]

    def test_normal_victory_requires_territory_and_counts_the_neighbor_once(
        self,
    ) -> None:
        held = self._active(extra=self._hold_sla(True))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", held)
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check)
        )
        settle = self._run(
            "ADISCORD_vorkerland_rus_settle_dirty_target",
            {
                **held,
                ("RUS", "country_exists", "SLA"): True,
            },
        )
        self.assertIn("ADISCORD_vorkerland_rus_annex_dirty_target", self._calls(settle))
        annex = self._run(
            "ADISCORD_vorkerland_rus_annex_dirty_target",
            {
                **held,
                ("RUS", "country_exists", "SLA"): True,
            },
        )
        self.assertTrue(any(e.key == "annex_country" for _, e in annex))
        self.assertIn(
            ("RUS", "ADISCORD_vorkerland_rus_sla_absorbed"),
            [(s, e.value) for s, e in settle if e.key == "set_country_flag"],
        )
        self.assertIn(
            ("RUS", "ADISCORD_vorkerland_rus_sla_counted"),
            [(s, e.value) for s, e in settle if e.key == "set_country_flag"],
        )
        self.assertTrue(any(e.key == "add_to_variable" for _, e in settle))
        self.assertIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(settle)
        )
        repeat = self._run(
            "ADISCORD_vorkerland_rus_settle_dirty_target",
            {
                **held,
                ("RUS", "country_exists", "SLA"): True,
                (
                    "RUS",
                    "has_country_flag",
                    "ADISCORD_vorkerland_rus_sla_counted",
                ): True,
            },
        )
        self.assertFalse(
            any(e.key == "add_to_variable" for _, e in repeat),
            "repeat occupation must not increment again",
        )
        self.assertIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(repeat)
        )

    def test_third_party_or_vanished_target_aborts_without_credit(self) -> None:
        still_open = self.expand(
            self.block(
                self.triggers, "ADISCORD_vorkerland_rus_campaign_target_still_open"
            )
        )
        vanished = self._active()
        self.assertTrue(self.matches(still_open, vanished, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", vanished)
        self.assertIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check)
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check)
        )
        settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", vanished)
        self.assertFalse(
            any(e.key in {"add_to_variable", "annex_country"} for _, e in settle)
        )

    def test_live_war_without_control_waits_instead_of_hanging_or_awarding(
        self,
    ) -> None:
        waiting = self._active(extra={("RUS", "has_war_with", "SLA"): True})
        still_open = self.expand(
            self.block(
                self.triggers, "ADISCORD_vorkerland_rus_campaign_target_still_open"
            )
        )
        holds = self.expand(
            self.block(self.triggers, "ADISCORD_vorkerland_rus_holds_current_target")
        )
        ready = self.expand(
            self.block(self.triggers, "ADISCORD_vorkerland_rus_current_target_ready")
        )
        self.assertFalse(self.matches(still_open, waiting, "RUS"))
        self.assertFalse(self.matches(holds, waiting, "RUS"))
        self.assertFalse(self.matches(ready, waiting, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", waiting)
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check)
        )
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check)
        )

    def test_capitulated_target_settles_without_full_occupation(self) -> None:
        capitulated = self._active(
            extra={
                ("RUS", "has_war_with", "SLA"): True,
                ("RUS", "country_exists", "SLA"): True,
                ("SLA", "has_capitulated", "yes"): True,
                ("SLA", "capital"): "170",
                ("170", "is_controlled_by", "RUS"): True,
            }
        )
        ready = self.expand(
            self.block(self.triggers, "ADISCORD_vorkerland_rus_current_target_ready")
        )
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
            facts = self._active(
                target,
                {
                    ("RUS", "has_war_with", tag): True,
                    ("RUS", "country_exists", tag): True,
                    (tag, "has_capitulated", "yes"): True,
                    (tag, "capital"): "999",
                    ("999", "is_controlled_by", "VAL"): True,
                },
            )
            ready = self.expand(
                self.block(
                    self.triggers, "ADISCORD_vorkerland_rus_current_target_ready"
                )
            )
            self.assertFalse(self.matches(ready, facts, "RUS"), tag)
            settle = self._run("ADISCORD_vorkerland_rus_settle_dirty_target", facts)
            self.assertNotIn(
                "ADISCORD_vorkerland_rus_annex_dirty_target", self._calls(settle), tag
            )
            won = {**facts, ("999", "is_controlled_by", "RUS"): True}
            self.assertTrue(self.matches(ready, won, "RUS"), tag)
            self.assertIn(
                "ADISCORD_vorkerland_rus_annex_dirty_target",
                self._calls(
                    self._run("ADISCORD_vorkerland_rus_settle_dirty_target", won)
                ),
                tag,
            )

    def test_border_war_absorbs_a_fully_occupied_republic(self) -> None:
        occupied = {
            (
                "RUS",
                "has_global_flag",
                "ADISCORD_vorkerland_khan_border_war_started",
            ): True,
            (
                "RUS",
                "has_country_flag",
                "ADISCORD_vorkerland_rus_dirty_campaign_active",
            ): False,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_war_with", "SLA"): True,
            ("RUS", "variable", "ADISCORD_vorkerland_rus_campaign_target"): 0,
            **self._hold_sla(True),
        }
        check = self._run("ADISCORD_vorkerland_check_khan_border_war", occupied)
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))
        self.assertNotIn(
            "ADISCORD_vorkerland_resolve_khan_border_war", self._calls(check)
        )

    def test_border_war_belt_still_white_peaces(self) -> None:
        belt = {
            (
                "RUS",
                "has_global_flag",
                "ADISCORD_vorkerland_khan_border_war_started",
            ): True,
            (
                "RUS",
                "has_country_flag",
                "ADISCORD_vorkerland_rus_dirty_campaign_active",
            ): False,
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
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check)
        )
        resolve = self._run("ADISCORD_vorkerland_resolve_khan_border_war", belt)
        self.assertTrue(any(e.key == "white_peace" for _, e in resolve))
        self.assertTrue(
            any(scope == "49" and e.key == "set_state_owner_to" for scope, e in resolve)
        )
        self.assertTrue(
            any(
                scope == "176" and e.key == "set_state_owner_to" for scope, e in resolve
            )
        )
        white_peace_pos = next(
            i for i, (_, e) in enumerate(resolve) if e.key == "white_peace"
        )
        first_transfer = next(
            i
            for i, (scope, e) in enumerate(resolve)
            if scope in {"49", "176"} and e.key == "set_state_owner_to"
        )
        self.assertLess(first_transfer, white_peace_pos)

    def test_border_capitulation_annexes_before_partial_peace(self):
        facts = {
            (
                "RUS",
                "has_global_flag",
                "ADISCORD_vorkerland_khan_border_war_started",
            ): True,
            ("RUS", "country_exists", "SLA"): True,
            ("RUS", "has_war_with", "SLA"): True,
            ("SLA", "has_capitulated", "yes"): True,
            ("SLA", "capital"): "51",
            ("51", "is_controlled_by", "RUS"): True,
            **self._hold_sla(False),
        }
        calls = self._calls(
            self._run("ADISCORD_vorkerland_check_khan_border_war", facts)
        )
        self.assertIn("ADISCORD_vorkerland_rus_settle_dirty_target", calls)
        self.assertNotIn("ADISCORD_vorkerland_resolve_khan_border_war", calls)

    def test_invalid_target_or_own_capitulation_clears_the_operation(self) -> None:
        invalid = self._active(target=0)
        self.assertTrue(
            self.matches(
                self.expand(
                    self.block(
                        self.triggers,
                        "ADISCORD_vorkerland_rus_campaign_target_still_open",
                    )
                ),
                invalid,
                "RUS",
            )
        )
        self.assertIn(
            "ADISCORD_vorkerland_rus_abort_dirty_campaign",
            self._calls(
                self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", invalid)
            ),
        )
        own_loss = self._active(
            extra={
                ("RUS", "has_capitulated", "yes"): True,
                ("RUS", "has_war_with", "SLA"): True,
            }
        )
        lost = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", own_loss)
        self.assertIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(lost))
        self.assertNotIn(
            "ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(lost)
        )

    def test_liberation_clears_absorbed_and_allows_a_repeat_campaign(self) -> None:
        liberated = {
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_sla_absorbed"): True,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_sla_counted"): True,
            ("RUS", "has_war_with", "SLA"): False,
            **self._hold_sla(False),
        }
        released = self._run(
            "ADISCORD_vorkerland_rus_release_lost_absorptions", liberated
        )
        self.assertIn(
            ("RUS", "ADISCORD_vorkerland_rus_sla_absorbed"),
            [(s, e.value) for s, e in released if e.key == "clr_country_flag"],
        )
        self.assertNotIn(
            ("RUS", "ADISCORD_vorkerland_rus_sla_counted"),
            [(s, e.value) for s, e in released if e.key == "clr_country_flag"],
        )
        decisions = read(DECISION_FILE)
        sla = decisions[
            decisions.index("\tRUS_campaign_sla = {") : decisions.index(
                "\tRUS_campaign_rza = {"
            )
        ]
        self.assertIn(
            "NOT = { has_country_flag = ADISCORD_vorkerland_rus_sla_absorbed }", sla
        )
        rza = decisions[
            decisions.index("\tRUS_campaign_rza = {") : decisions.index(
                "\tRUS_campaign_mlr = {"
            )
        ]
        self.assertIn(
            "NOT = { has_country_flag = ADISCORD_vorkerland_rus_rza_absorbed }", rza
        )

    def test_empire_gate_accepts_three_held_belts_or_no_independent_republics(
        self,
    ) -> None:
        from tools.lib.vorkerland_collapse_manifest import DIRTY_GROUPS

        gate = self.expand(
            self.block(self.triggers, "ADISCORD_vorkerland_rus_has_empire_territory")
        )
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
        gate_body = source[gate_start : source.index("\n}", gate_start) + 2]
        self.assertNotIn("dirty_neighbors_taken", gate_body)


class RusCrisisFixture:
    """Execute the new scripted branches against a small explicit world.

    White peace may erase the entire coalition's war relations, and annexation
    may leave an impassable state. These are adversarial fixtures, not an
    assertion about native callback timing or game UI behaviour.
    """

    def __init__(self, hegemon="VAL"):
        from tools.tests.test_adiscord_stp_preparation import entries

        self.effects = {e.key: e.value for e in entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt")}
        self.triggers = {
            e.key: e.value
            for e in entries("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
            if e.key.startswith("RUS_crisis_")
        }
        self.countries = {"RUS", "VAL", "STS", "NOD", "SLA", "RZA", "MLR", "ERT", "IRT", "SCA", "WKR"}
        self.owners = {
            "66": "RUS", "49": "RUS", "51": "RUS", "177": "RUS",
            "152": "RUS", "169": "RUS", "181": "RUS", "173": "RUS",
            "330": "RUS", "168": "VAL", "1": "STS", "10": "NOD", "40": "WKR",
        }
        self.controllers = dict(self.owners)
        self.cores = {
            "66": {"RUS"}, "49": {"RUS", "SLA"}, "51": {"RUS", "SLA"},
            "177": {"RUS", "RZA"}, "152": {"RUS", "MLR"},
            "169": {"RUS", "ERT"}, "181": {"RUS", "IRT"},
            "173": {"RUS", "SCA"}, "330": {"RUS", "IRT"}, "168": {"VAL", "ERT"},
        }
        self.flags = {tag: set() for tag in self.countries}
        self.flags["RUS"].add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        self.state_flags = {}
        self.variables = {("RUS", "RUS_crisis_phase"): 2}
        self.targets = {"event_target:RUS_crisis_hegemon": hegemon}
        self.arrays = {}
        self.subjects = {}
        self.factions = {}
        self.capitulated = set()
        self.majors = {hegemon}
        self.wars = {frozenset(("RUS", tag)) for tag in (hegemon, "NOD")}
        self.events = []
        self.missions = []
        self.annexed = []
        self.retired = []
        self.autonomy = {}
        self.outside_predicates = {}
        self.root = "RUS"
        self.from_country = hegemon
        self.run("RUS_crisis_register_defender", hegemon)
        self.run("RUS_crisis_register_defender", "NOD")

    def resolve(self, token, stack):
        return {
            "THIS": stack[-1],
            "PREV": stack[-2] if len(stack) > 1 else None,
            "ROOT": self.root,
            "FROM": self.from_country,
            **self.targets,
        }.get(token, token)

    def exists(self, tag):
        return tag in self.owners.values()

    def matches(self, rows, stack):
        from tools.tests.test_adiscord_stp_preparation import scalar

        current = stack[-1]

        def one(entry):
            key, value = entry.key, entry.value
            if key in ("AND", "hidden_trigger"):
                return self.matches(value, stack)
            if key == "custom_trigger_tooltip":
                return self.matches([e for e in value if e.key != "tooltip"], stack)
            if key == "OR":
                return any(one(e) for e in value)
            if key == "NOT":
                return not any(one(e) for e in value)
            if key in self.triggers:
                result = self.matches(self.triggers[key], stack)
                return result == (value == "yes")
            if key == "any_country":
                return any(self.exists(tag) and self.matches(value, stack + [tag]) for tag in self.countries)
            if isinstance(value, list) and (
                key in self.countries or key in ("ROOT", "FROM", "PREV") or key.startswith("event_target:")
            ):
                return self.matches(value, stack + [self.resolve(key, stack)])
            if key == "check_variable":
                left = self.variables.get((current, scalar(value, "var")), 0)
                right = float(scalar(value, "value"))
                return {
                    "equals": left == right,
                    "less_than": left < right,
                    "greater_than": left > right,
                }[scalar(value, "compare")]
            if key == "has_variable":
                return (current, value) in self.variables
            if key == "has_country_flag":
                return value in self.flags[current]
            if key == "has_state_flag":
                return value in self.state_flags.get(current, set())
            if key == "has_capitulated":
                return (current in self.capitulated) == (value == "yes")
            if key == "is_major":
                return (current in self.majors) == (value == "yes")
            if key == "is_subject":
                return (current in self.subjects) == (value == "yes")
            if key == "is_subject_of":
                return self.subjects.get(current) == self.resolve(value, stack)
            if key == "exists":
                return self.exists(current) == (value == "yes")
            if key == "is_in_faction":
                return (current in self.factions) == (value == "yes")
            if key == "is_in_faction_with":
                other = self.resolve(value, stack)
                return current in self.factions and self.factions[current] == self.factions.get(other)
            if key == "has_war":
                return any(current in war for war in self.wars) == (value == "yes")
            if key == "has_war_with":
                return frozenset((current, self.resolve(value, stack))) in self.wars
            if key == "tag":
                return current == self.resolve(value, stack)
            if key == "is_core_of":
                return self.resolve(value, stack) in self.cores.get(current, set())
            if key == "always":
                return value == "yes"
            if key in ("VAL_campaign_objectives_met", "STP_heg_northern_final_resolved"):
                return self.outside_predicates.get((current, key), False) == (value == "yes")
            raise AssertionError(f"Unsupported crisis condition {key} in {current}")

        return all(one(e) for e in rows)

    def run(self, name, country="RUS"):
        self.execute(self.effects[name], [country])

    def execute(self, rows, stack):
        from tools.tests.test_adiscord_stp_preparation import scalar

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
            elif key in ("hidden_effect",):
                self.execute(value, stack)
            elif key == "effect_tooltip":
                continue
            elif key in ("ADISCORD_economy_mark_dirty", "ADISCORD_vorkerland_rus_abort_dirty_campaign"):
                continue
            elif key in self.effects:
                self.execute(self.effects[key], stack)
            elif key in self.countries or key in ("ROOT", "FROM", "PREV") or key.startswith("event_target:"):
                self.execute(value, stack + [self.resolve(key, stack)])
            elif key == "overlord":
                self.execute(value, stack + [self.subjects[current]])
            elif key in ("every_owned_state", "every_country", "every_subject_country", "every_enemy_country"):
                candidates = {
                    "every_owned_state": [s for s, owner in self.owners.items() if owner == current],
                    "every_country": [tag for tag in sorted(self.countries) if self.exists(tag)],
                    "every_subject_country": [tag for tag, owner in self.subjects.items() if owner == current],
                    "every_enemy_country": [
                        tag for tag in sorted(self.countries)
                        if frozenset((current, tag)) in self.wars
                    ],
                }[key]
                gate = next((e.value for e in value if e.key == "limit"), [])
                for candidate in candidates:
                    if self.matches(gate, stack + [candidate]):
                        self.execute([e for e in value if e.key != "limit"], stack + [candidate])
            elif key == "for_each_scope_loop":
                for item in list(self.arrays.get(scalar(value, "array"), [])):
                    self.execute([e for e in value if e.key != "array"], stack + [item])
            elif key in ("clear_array", "clear_temp_array"):
                self.arrays[value] = []
            elif key in ("add_to_array", "add_to_temp_array"):
                self.arrays.setdefault(scalar(value, "array"), []).append(self.resolve(scalar(value, "value"), stack))
            elif key == "set_variable":
                self.variables[current, scalar(value, "var")] = float(scalar(value, "value"))
            elif key == "set_country_flag":
                flag = scalar(value, "flag") if isinstance(value, list) else value
                self.flags[current].add(flag)
            elif key == "clr_country_flag":
                self.flags[current].discard(value)
            elif key == "set_state_flag":
                self.state_flags.setdefault(current, set()).add(value)
            elif key == "set_major":
                if value == "yes":
                    self.majors.add(current)
                else:
                    self.majors.discard(current)
            elif key == "save_global_event_target_as":
                self.targets["event_target:" + value] = current
            elif key == "activate_mission":
                self.missions.append((current, value))
            elif key == "country_event":
                self.events.append((current, scalar(value, "id")))
            elif key == "declare_war_on":
                self.wars.add(frozenset((current, self.resolve(scalar(value, "target"), stack))))
            elif key == "add_to_war":
                self.wars.add(frozenset((current, self.resolve(scalar(value, "enemy"), stack))))
            elif key == "white_peace":
                # The snapshot must survive loss of every war relation.
                self.wars = {w for w in self.wars if "RUS" not in w}
            elif key == "annex_country":
                target = self.resolve(scalar(value, "target"), stack)
                self.annexed.append((current, target))
                for state, owner in list(self.owners.items()):
                    if owner == target and state != "330":
                        self.owners[state] = current
                for subject, overlord in list(self.subjects.items()):
                    if overlord == target:
                        self.subjects[subject] = current
            elif key == "set_state_owner_to":
                self.owners[current] = self.resolve(value, stack)
            elif key == "set_state_controller_to":
                self.controllers[current] = self.resolve(value, stack)
            elif key == "add_core_of":
                self.cores.setdefault(current, set()).add(self.resolve(value, stack))
            elif key == "remove_core_of":
                self.cores.setdefault(current, set()).discard(self.resolve(value, stack))
            elif key == "set_autonomy":
                target = self.resolve(scalar(value, "target"), stack)
                autonomy = scalar(value, "autonomy_state")
                self.autonomy[target] = autonomy
                if autonomy == "autonomy_free":
                    self.subjects.pop(target, None)
                else:
                    self.subjects[target] = current
            elif key == "leave_faction":
                self.factions.pop(current, None)
            elif key == "retire_character":
                self.retired.append(value)
            elif key in ("remove_ideas", "remove_claim_by", "custom_effect_tooltip", "unlock_decision_tooltip"):
                continue
            else:
                raise AssertionError(f"Unsupported crisis effect {key} in {current}")


class RusCrisisContracts(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar
        self.block = block
        self.entries = entries
        self.scalar = scalar

    def test_later_hegemon_and_duplicate_start_preserve_one_deadline(self):
        world = RusCrisisFixture()
        world.variables.clear()
        world.wars.clear()
        world.run("RUS_crisis_clear_roster")
        world.run("RUS_crisis_check_start")
        self.assertFalse(world.missions)
        world.outside_predicates["VAL", "VAL_campaign_objectives_met"] = True
        world.run("RUS_crisis_check_start")
        world.run("RUS_crisis_check_start")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)
        self.assertEqual(len(world.missions), 2)
        self.assertEqual(len(world.events), 2)

    def test_stelander_is_selected_when_only_its_final_victory_is_valid(self):
        world = RusCrisisFixture()
        world.variables.clear()
        world.wars.clear()
        world.run("RUS_crisis_clear_roster")
        world.flags["STS"].add("STP_heg_kefreyt_final_won")
        world.outside_predicates["STS", "STP_heg_northern_final_resolved"] = True
        world.run("RUS_crisis_check_start")
        self.assertEqual(world.targets["event_target:RUS_crisis_hegemon"], "STS")
        self.assertIn(("STS", "RUS_crisis_defence_countdown"), world.missions)

    def test_occupied_or_subject_hegemon_is_not_selected(self):
        for capitulated, subject in ((True, False), (False, True)):
            world = RusCrisisFixture()
            world.variables.clear()
            world.wars.clear()
            world.outside_predicates["VAL", "VAL_campaign_objectives_met"] = True
            if capitulated:
                world.capitulated.add("VAL")
            if subject:
                world.subjects["VAL"] = "WKR"
            world.run("RUS_crisis_check_start")
            self.assertFalse(world.missions)

    def test_mission_timeout_starts_war_without_responding_to_events(self):
        world = RusCrisisFixture()
        world.run("RUS_crisis_clear_roster")
        world.variables["RUS", "RUS_crisis_phase"] = 1
        world.wars.clear()
        world.factions = {"VAL": "league", "NOD": "league"}
        category = self.block(self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"), "RUS_last_empire_crisis")
        mission = self.block(category, "RUS_crisis_invasion_countdown")
        world.execute(self.block(mission, "timeout_effect"), ["RUS"])
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertIn(frozenset(("RUS", "VAL")), world.wars)
        self.assertIn(frozenset(("RUS", "NOD")), world.wars)
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"VAL", "NOD"})
        before = list(world.events)
        world.execute(self.block(mission, "timeout_effect"), ["RUS"])
        self.assertEqual(world.events, before)

    def test_warning_cannot_launch_after_target_becomes_subject(self):
        world = RusCrisisFixture()
        world.variables["RUS", "RUS_crisis_phase"] = 1
        world.wars.clear()
        world.subjects["VAL"] = "WKR"
        world.run("RUS_crisis_launch")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 5)
        self.assertFalse(world.wars)
        self.assertNotIn("NOD", world.majors)

    def test_living_or_liberated_ally_blocks_final_annexation(self):
        world = RusCrisisFixture()
        world.capitulated.add("VAL")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertFalse(world.annexed)
        world.capitulated.add("NOD")
        self.assertTrue(world.matches(world.triggers["RUS_crisis_all_defenders_defeated"], ["RUS"]))
        world.capitulated.remove("NOD")
        self.assertFalse(world.matches(world.triggers["RUS_crisis_all_defenders_defeated"], ["RUS"]))

    def test_immediate_capitulation_reserves_late_fallback_and_consumes_roster(self):
        from tools.lib.on_actions import read_scripted_peace
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        shared = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
        hooks = self.block(parse_clausewitz(read_scripted_peace(shared, "vorkerland_collapse")), "on_actions")
        immediate = self.block(self.block(hooks, "on_capitulation_immediate"), "effect")
        world = RusCrisisFixture()
        world.capitulated.add("NOD")
        world.root = "VAL"
        world.from_country = "RUS"
        # The current native defeat may not yet be exposed by has_capitulated.
        world.execute(immediate, ["VAL"])
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 3)
        self.assertIn("RUS_crisis_capitulation_reserved", world.flags["VAL"])
        self.assertNotIn("RUS_crisis_capitulation_current", world.flags["VAL"])
        self.assertEqual(set(world.annexed), {("RUS", "VAL"), ("RUS", "NOD")})
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertIn("VAL", world.majors)
        self.assertNotIn("NOD", world.majors)

    def test_imperial_victory_transfers_snapshot_after_total_native_peace(self):
        world = RusCrisisFixture()
        world.owners["330"] = "NOD"
        world.capitulated.update(("VAL", "NOD"))
        world.run("RUS_crisis_resolve_capitulation")
        for state in ("168", "10", "330"):
            self.assertEqual(world.owners[state], "RUS")
            self.assertEqual(world.controllers[state], "RUS")
            self.assertIn("RUS_crisis_conquered_state", world.state_flags[state])
        self.assertEqual(world.owners["40"], "WKR")
        self.assertEqual(world.owners["1"], "STS")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(len(world.annexed), 2)

    def test_khan_defeat_restores_only_imperial_lands_for_either_winner(self):
        for hegemon in ("VAL", "STS"):
            with self.subTest(hegemon=hegemon):
                world = RusCrisisFixture(hegemon)
                world.capitulated.add("RUS")
                world.run("RUS_crisis_resolve_capitulation")
                self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 4)
                self.assertNotIn("RUS", world.owners.values())
                self.assertIn("RUS_Mark_Rustan", world.retired)
                self.assertEqual(world.owners["66"], "SLA")
                self.assertEqual(world.owners["330"], "IRT")
                self.assertEqual(world.owners["168"], "VAL")
                self.assertEqual(world.owners["40"], "WKR")
                self.assertIn("RUS_crisis_settlement_rights", world.flags[hegemon])
                other = "STS" if hegemon == "VAL" else "VAL"
                self.assertNotIn("RUS_crisis_settlement_rights", world.flags[other])
                self.assertFalse(world.subjects)
                for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
                    self.assertIn("RUS_crisis_fragment", world.flags[tag])

    def test_full_authored_partition_keeps_every_peripheral_state_and_val_claim(self):
        from tools.lib.vorkerland_collapse_manifest import DIRTY_GROUPS, EXZ_REMAINDER_GROUPS

        world = RusCrisisFixture()
        expected = {}
        for tag, states in DIRTY_GROUPS.items():
            for number in (*states, *EXZ_REMAINDER_GROUPS.get(tag, ())):
                if number == 168:
                    continue
                state = str(number)
                world.owners[state] = "RUS"
                world.controllers[state] = "RUS"
                world.cores[state] = {tag, "RUS"}
                expected[state] = tag
        world.capitulated.add("RUS")
        world.run("RUS_crisis_resolve_capitulation")
        for state, tag in expected.items():
            self.assertEqual(world.owners[state], tag, state)
            self.assertEqual(world.controllers[state], tag, state)
            self.assertNotIn("RUS", world.cores[state])
        self.assertEqual(world.owners["168"], "VAL")
        self.assertEqual(world.owners["66"], "SLA")

    def test_former_subjects_and_dormant_faction_members_are_independent(self):
        world = RusCrisisFixture()
        world.owners["181"] = "IRT"
        world.subjects["IRT"] = "RUS"
        world.factions = {"IRT": "old", "MLR": "old", "WKR": "old"}
        world.subjects["MLR"] = "WKR"
        world.capitulated.add("RUS")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertNotIn("IRT", world.subjects)
        self.assertNotIn("MLR", world.subjects)
        self.assertNotIn("IRT", world.factions)
        self.assertNotIn("MLR", world.factions)
        self.assertEqual(world.factions["WKR"], "old")

    def test_surviving_neighbour_does_not_become_a_free_puppet_target(self):
        world = RusCrisisFixture()
        world.owners["173"] = "SCA"
        world.subjects["SCA"] = "WKR"
        world.capitulated.add("RUS")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertNotIn("RUS_crisis_fragment", world.flags["SCA"])
        self.assertEqual(world.subjects["SCA"], "WKR")

    def test_each_winner_can_select_one_existing_special_zone_only_once(self):
        category = self.block(self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"), "RUS_last_empire_crisis")
        decision = self.block(category, "RUS_crisis_establish_special_zone")
        transaction = self.block(self.block(decision, "complete_effect"), "if")
        self.assertEqual([e.key for e in self.block(transaction, "limit")], ["hidden_trigger"])
        self.assertIn("set_autonomy", [e.key for e in transaction])
        for hegemon in ("VAL", "STS"):
            world = RusCrisisFixture(hegemon)
            world.capitulated.add("RUS")
            world.run("RUS_crisis_resolve_capitulation")
            world.root = hegemon
            world.from_country = "MLR"
            self.assertTrue(world.matches(self.block(decision, "available"), [hegemon]))
            world.execute(self.block(decision, "complete_effect"), [hegemon])
            self.assertEqual(world.subjects, {"MLR": hegemon})
            self.assertEqual(world.autonomy["MLR"], "autonomy_vorkerland_sanitary_gate")
            world.subjects.clear()
            self.assertFalse(world.matches(self.block(decision, "visible"), [hegemon]))
            world.execute(self.block(decision, "complete_effect"), [hegemon])
            self.assertFalse(world.subjects)

    def test_outside_partial_peace_closes_without_rewards_or_stale_majors(self):
        world = RusCrisisFixture()
        world.wars.remove(frozenset(("RUS", "NOD")))
        world.run("RUS_crisis_check_external_end")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 5)
        self.assertFalse(world.annexed)
        self.assertNotIn("NOD", world.majors)
        self.assertIn("VAL", world.majors)
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertFalse(any("RUS_crisis_settlement_rights" in flags for flags in world.flags.values()))

    def test_external_removal_of_hegemon_closes_even_with_a_living_ally(self):
        for outcome in ("annexed", "subjugated"):
            world = RusCrisisFixture()
            if outcome == "annexed":
                for state, owner in list(world.owners.items()):
                    if owner == "VAL":
                        world.owners[state] = "WKR"
            else:
                world.subjects["VAL"] = "WKR"
            world.run("RUS_crisis_check_external_end")
            self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 5)
            self.assertFalse(world.annexed)
            self.assertNotIn("NOD", world.majors)

    def test_missions_and_preparations_share_a_realistic_deadline(self):
        category = self.block(self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"), "RUS_last_empire_crisis")
        tree = self.block(self.entries("common/national_focus/ADISCORD_national_focus_RUS.txt"), "focus_tree")
        focuses = {self.scalar(e.value, "id"): e.value for e in tree if e.key == "focus"}
        preparation = ("RUS_imperial_general_staff", "RUS_western_supply_lines", "RUS_imperial_arsenals", "RUS_aimaq_reserve")
        duration = sum(int(self.scalar(focuses[key], "cost")) * 7 for key in preparation)
        self.assertEqual(duration, 77)
        for name in ("RUS_crisis_invasion_countdown", "RUS_crisis_defence_countdown"):
            mission = self.block(category, name)
            self.assertGreater(int(self.scalar(mission, "days_mission_timeout")), duration)
            self.assertEqual(self.scalar(mission, "selectable_mission"), "no")
            gate = self.block(self.block(mission, "available"), "hidden_trigger")
            self.assertEqual(self.scalar(gate, "always"), "no")
            self.assertIn(name, read(ROOT / "common/synchronized_dynamic_tokens/ADISCORD_tokens.txt"))

    def test_new_localisation_is_single_line_bom_and_complete(self):
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            source = read(path).split("# --- rus_crisis_l_" + language + " ---", 1)[1]
            if language == "russian":
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            lines = [line for line in source.splitlines() if line.strip()]
            for line in lines:
                self.assertRegex(line, r'^ [A-Za-z0-9_.]+: "(?:[^"\\]|\\.)*"$')
                rendered = line.split('"', 1)[1].rsplit('"', 1)[0].replace("\\n", "\n")
                self.assertLessEqual(len(rendered), 3000)
                self.assertLessEqual(len(rendered.encode("utf-8")), 5500)
            self.assertNotIn("§Y", source.split(" ADISCORD_rus_crisis.1.d:", 1)[1])


if __name__ == "__main__":
    unittest.main()
