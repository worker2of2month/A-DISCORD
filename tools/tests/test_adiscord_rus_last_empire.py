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
# The strike stands on the reactor landmark; the ash veil stands at the map centre.
ORBITAL_ACTOR_POSITIONS = {
    "ADISCORD_orbital_laser_strike_entity": ("3536.24", "906.55"),
    "ADISCORD_orbital_laser_world_ash_entity": ("2816", "1024"),
}
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
    def test_proclamation_names_the_empire_after_the_leading_faction(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar

        effect = block(
            entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt"),
            "ADISCORD_vorkerland_rus_proclaim_last_empire",
        )
        payload = block(effect, "if")
        branches = [
            entry
            for entry in payload
            if isinstance(entry.value, list)
            and any(child.key == "set_cosmetic_tag" for child in entry.value)
        ]
        expected = (
            ("if", ">", "0.10", "RUS_black_banner_empire"),
            ("else_if", "<", "-0.10", "RUS_restoration_state"),
            ("else", None, None, "RUS_last_empire"),
        )
        self.assertEqual(len(branches), len(expected))
        for branch, (key, operator, threshold, cosmetic) in zip(branches, expected):
            with self.subTest(cosmetic=cosmetic):
                self.assertEqual(branch.key, key)
                self.assertEqual(scalar(branch.value, "set_cosmetic_tag"), cosmetic)
                self.assertFalse(any(entry.key in ("set_politics", "promote_character", "retire_character") for entry in branch.value))
                if operator:
                    balance = block(block(branch.value, "limit"), "power_balance_value")
                    self.assertEqual(scalar(balance, "id"), "RUS_state_balance")
                    self.assertEqual([row.value for row in balance if not row.key][1:], [operator, threshold])
        self.assertEqual(scalar(block(payload, "set_politics"), "ruling_party"), "etatism")
        portraits = block(payload, "set_portraits")
        self.assertEqual(scalar(portraits, "character"), "RUS_Mark_Rustan")
        self.assertEqual(scalar(block(portraits, "civilian"), "large"), "GFX_portrait_RUS_Mark_Rustan_dictator")
        self.assertEqual(scalar(block(payload, "set_country_leader_portrait"), "ideology"), "etatism")
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
        body = plan[start:].split("ADISCORD_rus_last_sky_plan = {", 1)[0]
        ordered = tuple(re.findall(r"(?m)^\s*(RUS_[A-Za-z0-9_]+)\s*$", body))
        self.assertEqual(tuple(name for name in ordered if name in RUS_FOCUS_IDS), RUS_FOCUS_IDS)
        self.assertIn("is_ai = yes", body)

    def test_decisions_are_scripted_wars_with_one_campaign_escrow(self) -> None:
        from tools.validators.validate_adiscord_vorkerland_collapse import named_block

        decisions = read(DECISION_FILE)
        categories = read(CATEGORY_FILE)
        self.assertIn("ADISCORD_vorkerland_rus_dirty_campaign_category", categories)
        self.assertIn("allowed = { tag = RUS }", categories)
        for decision_id in RUS_DECISIONS:
            self.assertIn(f"{decision_id} = {{", decisions)
            block = named_block(decisions, decision_id)
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


SLA_STATES = (49, 51, 155, 176, 187, 191, 710, 711, 712)


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

    def _proclamation_facts(self) -> dict:
        facts = {
            ("RUS", "is_ai", "yes"): True,
            ("RUS", "has_war", "no"): True,
            ("RUS", "is_subject", "no"): True,
            ("RUS", "has_capitulated", "no"): True,
            ("RUS", "ruling_leader"): "RUS_Mark_Rustan",
        }
        for focus in (
            "RUS_seat_the_khan_chancery",
            "RUS_arm_the_border_hosts",
            "RUS_aimaq_reserve",
        ):
            facts[("RUS", "has_completed_focus", focus)] = True
        for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
            facts[("RUS", "country_exists", tag)] = True
            belt = self.block(
                self.triggers,
                f"ADISCORD_vorkerland_rus_holds_{tag.lower()}_playable",
            )
            for entry in belt:
                facts[("RUS", "controls_state", entry.value)] = tag in (
                    "SLA", "MLR", "IRT"
                )
        return facts

    def test_ai_saves_for_proclamation_only_while_its_live_conditions_hold(self):
        from tools.tests.test_adiscord_stp_preparation import scalar

        gate = self.expand(self.block(self.triggers, "RUS_ai_proclamation_pending"))
        category = self.block(
            self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"),
            "ADISCORD_vorkerland_rus_dirty_campaign_category",
        )
        decision = self.block(category, "RUS_proclaim_the_last_empire")
        available = self.expand(self.block(decision, "available"))
        ready = self._proclamation_facts()
        self.assertEqual(scalar(decision, "cost"), "75")
        for power in (0, 21.75066, 74.999, 75, 200):
            facts = {**ready, ("RUS", "numeric", "has_political_power"): power}
            with self.subTest(power=power):
                self.assertTrue(self.matches(gate, facts, "RUS"))
                self.assertTrue(self.matches(available, facts, "RUS"))
        blockers = {
            ("RUS", "has_war", "no"): False,
            ("RUS", "is_subject", "no"): False,
            ("RUS", "has_capitulated", "no"): False,
            ("RUS", "ruling_leader"): "RUS_Varlam_Oskol",
            ("RUS", "controls_state", "49"): False,
            ("RUS", "has_completed_focus", "RUS_seat_the_khan_chancery"): False,
            ("RUS", "has_completed_focus", "RUS_arm_the_border_hosts"): False,
            ("RUS", "has_completed_focus", "RUS_aimaq_reserve"): False,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_last_empire_proclaimed"): True,
        }
        for key, value in blockers.items():
            with self.subTest(blocker=key):
                facts = {**ready, key: value}
                self.assertFalse(self.matches(gate, facts, "RUS"))
                self.assertFalse(self.matches(available, facts, "RUS"))
        human = {**ready, ("RUS", "is_ai", "yes"): False}
        self.assertFalse(self.matches(gate, human, "RUS"))
        self.assertTrue(self.matches(available, human, "RUS"))

    def test_paid_ai_projects_yield_to_proclamation_and_resume_afterwards(self):
        from tools.tests.test_adiscord_stp_preparation import walk

        effects = {entry.key: entry.value for entry in self.effects}

        def field(rows, name, default=None):
            return next((entry.value for entry in rows if entry.key == name), default)

        def spends_power(rows, seen=None):
            seen = set() if seen is None else seen
            for entry in walk(rows):
                if entry.key == "add_political_power":
                    try:
                        if float(entry.value) < 0:
                            return True
                    except ValueError:
                        pass
                if entry.key in effects and entry.key not in seen:
                    seen.add(entry.key)
                    if spends_power(effects[entry.key], seen):
                        return True
            return False

        ready = self._proclamation_facts()
        proclaimed = {
            **ready,
            ("RUS", "has_country_flag", "ADISCORD_vorkerland_rus_last_empire_proclaimed"): True,
        }
        guarded = set()
        for category in self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"):
            for decision in category.value:
                name, rows = decision.key, decision.value
                if not name.startswith("RUS_") or name.startswith("RUS_crisis_"):
                    continue
                if name in ("RUS_proclaim_the_last_empire", "RUS_imperial_frontier_campaign"):
                    continue
                ai = field(rows, "ai_will_do", [])
                positive_weight = float(field(ai, "base", field(ai, "factor", "0"))) > 0
                positive_weight |= any(
                    entry.key == "add" and float(entry.value) > 0 for entry in walk(ai)
                )
                paid = float(field(rows, "cost", "0")) > 0 or spends_power(
                    field(rows, "complete_effect", [])
                )
                if not positive_weight or not paid:
                    continue
                with self.subTest(decision=name):
                    reservations = [
                        entry.value for entry in ai
                        if entry.key == "modifier"
                        and field(entry.value, "RUS_ai_proclamation_pending") == "yes"
                    ]
                    self.assertEqual(len(reservations), 1)
                    self.assertEqual(field(reservations[0], "factor"), "0")
                    conditions = self.expand([
                        entry for entry in reservations[0] if entry.key != "factor"
                    ])
                    self.assertTrue(self.matches(conditions, ready, "RUS"))
                    self.assertFalse(self.matches(conditions, proclaimed, "RUS"))
                    guarded.add(name)
        self.assertTrue({
            "RUS_engineering_order", "RUS_market_surplus", "RUS_bop_relief",
            "RUS_bop_mediation", "RUS_campaign_sca", "RUS_restore_reactor_works",
        }.issubset(guarded))

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

    def __init__(self, hegemon="VAL", ruler="RUS_Mark_Rustan", cosmetic="RUS_last_empire"):
        from tools.tests.test_adiscord_stp_preparation import entries

        self.effects = {e.key: e.value for e in entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt")}
        self.effects.update({
            e.key: e.value
            for e in entries("common/scripted_effects/ADISCORD_shared_action_effects.txt")
            if e.key == "ADISCORD_campaign_slot_release"
        })
        self.triggers = {
            e.key: e.value
            for e in entries("common/scripted_triggers/ADISCORD_vorkerland_triggers.txt")
            if e.key.startswith(("RUS_crisis_", "RUS_imperial_frontier_")) or e.key == "RUS_lab_reactor_access"
        }
        self.triggers.update({
            e.key: e.value
            for e in entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt")
            if e.key == "VAL_nw_special_zone_permitted"
        })
        self.countries = {"RUS", "VAL", "STP", "STS", "NOD", "SLA", "RZA", "MLR", "ERT", "IRT", "SCA", "WKR", "TMR", "VEL", "RLY", "SHL", "NAM", "WRK", "IVN", "MON", "VLD", "EXZ"}
        self.owners = {
            "66": "RUS", "49": "RUS", "51": "RUS", "177": "RUS",
            "152": "RUS", "169": "RUS", "181": "RUS", "173": "RUS",
            "330": "RUS", "168": "VAL", "1": "STS", "46": "STP", "10": "NOD", "40": "WKR",
        }
        self.controllers = dict(self.owners)
        self.cores = {
            "66": {"RUS"}, "49": {"RUS", "SLA"}, "51": {"RUS", "SLA"},
            "177": {"RUS", "RZA"}, "152": {"RUS", "MLR"},
            "169": {"RUS", "ERT"}, "181": {"RUS", "IRT"},
            "173": {"RUS", "SCA"}, "330": {"RUS", "IRT"}, "168": {"VAL", "ERT"},
        }
        self.flags = {tag: set() for tag in self.countries}
        self.global_flags = set()
        self.ai_countries = set(self.countries)
        self.flags["RUS"].add("ADISCORD_vorkerland_rus_last_empire_proclaimed")
        self.state_flags = {}
        self.variables = {("RUS", "RUS_crisis_phase"): 2}
        self.temp_variables = {}
        self.targets = {"event_target:RUS_crisis_hegemon": hegemon}
        self.arrays = {}
        self.subjects = {}
        self.factions = {}
        self.faction_leaders = set()
        self.ideas = set()
        self.equipment = {}
        self.army_experience = 0
        self.command_power = 0
        self.capitulated = set()
        self.majors = {hegemon}
        self.wars = {frozenset(("RUS", tag)) for tag in (hegemon, "NOD")}
        self.war_sides = [{hegemon, "NOD"}]
        self.peace_mode = "whole"
        self.events = []
        self.missions = []
        self.active_decisions = set()
        self.completed_focuses = set()
        self.neighbours = set()
        self.state_neighbours = {}
        self.released_minors = []
        self.annexed = []
        self.declarations = []
        self.joins = []
        self.visuals = []
        self.retired = []
        self.rulers = {"RUS": ruler}
        self.cosmetic_tags = {"RUS": cosmetic}
        self.power_balances = {"RUS": "RUS_state_balance"}
        self.dynamic_modifiers = {("RUS", "RUS_black_army"), ("RUS", "RUS_bunker_complex")}
        self.autonomy = {}
        self.player_handoffs = []
        self.units = {tag: 3 for tag in self.countries}
        self.destroyed_ships = []
        self.demilitarized = set()
        self.state_categories = {}
        self.buildings = {(state, "industrial_complex"): 3 for state in self.owners}
        self.province_buildings = {}
        self.building_mutations = []
        self.country_settings = {}
        self.outside_predicates = {}
        self.root = "RUS"
        self.from_country = hegemon
        self.run("RUS_crisis_register_defender", hegemon)
        self.run("RUS_crisis_register_defender", "NOD")

    def resolve(self, token, stack):
        if token.startswith("var:"):
            return self.temp_variables[self.variable_key(token[4:], stack[-1])]
        return {
            "THIS": stack[-1],
            "PREV": stack[-2] if len(stack) > 1 else None,
            "ROOT": self.root,
            "FROM": self.from_country,
            **self.targets,
        }.get(token, token)

    def exists(self, tag):
        return tag in self.owners.values()

    def variable_key(self, name, current):
        return ("global" if name.startswith("global.") else current, name)

    def array_key(self, name, current):
        if name == "RUS_crisis_annexed_states":
            return (current, name)
        return name

    def numeric_or_scope_value(self, token, current):
        if "^" in token:
            name, index = token.rsplit("^", 1)
            values = self.arrays.get(self.array_key(name, current), [])
            return len(values) if index == "num" else values[int(index)]
        try:
            return float(token)
        except ValueError:
            return self.variables.get(self.variable_key(token, current), 0)

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
            if key == "any_of_scopes":
                name = self.array_key(scalar(value, "array"), current)
                gate = [e for e in value if e.key != "array"]
                return any(self.matches(gate, stack + [item]) for item in self.arrays.get(name, []))
            if key == "capital_scope":
                capital = next((s for s, owner in self.owners.items() if owner == current), None)
                return capital is not None and self.matches(value, stack + [capital])
            if key == "controller":
                owner = self.controllers.get(current)
                return owner is not None and self.matches(value, stack + [owner])
            if key == "is_controlled_by":
                return self.controllers.get(current) == self.resolve(value, stack)
            if key == "has_event_target":
                return "event_target:" + value in self.targets
            if key == "OVERLORD":
                return current in self.subjects and self.matches(value, stack + [self.subjects[current]])
            if key == "is_in_array":
                name = self.array_key(scalar(value, "array"), current)
                return self.resolve(scalar(value, "value"), stack) in self.arrays.get(name, [])
            if isinstance(value, list) and (
                key in self.countries or key in ("ROOT", "FROM", "PREV") or key.startswith("event_target:")
            ):
                if key.startswith("event_target:") and key not in self.targets:
                    return False
                return self.matches(value, stack + [self.resolve(key, stack)])
            if key == "check_variable":
                left = self.numeric_or_scope_value(scalar(value, "var"), current)
                right = float(scalar(value, "value"))
                return {
                    "equals": left == right,
                    "less_than": left < right,
                    "greater_than": left > right,
                    "greater_than_or_equals": left >= right,
                }[scalar(value, "compare")]
            if key == "has_variable":
                return (current, value) in self.variables
            if key == "has_dynamic_modifier":
                return (current, scalar(value, "modifier")) in self.dynamic_modifiers
            if key == "has_power_balance":
                assert isinstance(value, list), value
                return self.power_balances.get(current) == scalar(value, "id")
            if key == "has_country_leader":
                assert isinstance(value, list), value
                assert scalar(value, "ruling_only") == "yes", value
                return self.rulers.get(current) == scalar(value, "character")
            if key == "has_cosmetic_tag":
                return self.cosmetic_tags.get(current) == value
            if key == "controls_state":
                return self.controllers.get(value) == current
            if key == "has_country_flag":
                return value in self.flags[current]
            if key == "has_global_flag":
                return value in self.global_flags
            if key == "is_owned_by":
                return self.owners.get(current) == self.resolve(value, stack)
            if key == "has_decision":
                return (current, value) in self.active_decisions
            if key == "has_active_mission":
                return (current, value) in self.missions
            if key == "has_completed_focus":
                return (current, value) in self.completed_focuses
            if key == "is_neighbor_of":
                return frozenset((current, self.resolve(value, stack))) in self.neighbours
            if key == "has_state_flag":
                return value in self.state_flags.get(current, set())
            if key == "has_capitulated":
                return (current in self.capitulated) == (value == "yes")
            if key == "is_ai":
                return (current in self.ai_countries) == (value == "yes")
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
            if key == "is_faction_leader":
                return (current in self.faction_leaders) == (value == "yes")
            if key == "is_in_faction_with":
                other = self.resolve(value, stack)
                return current in self.factions and self.factions[current] == self.factions.get(other)
            if key == "has_war":
                return any(current in war for war in self.wars) == (value == "yes")
            if key == "has_war_with":
                return frozenset((current, self.resolve(value, stack))) in self.wars
            if key == "has_war_together_with":
                other = self.resolve(value, stack)
                return any(current in side and other in side for side in self.war_sides)
            if key == "tag":
                return current == self.resolve(value, stack)
            if key == "state":
                return current == value
            if key == "is_core_of":
                return self.resolve(value, stack) in self.cores.get(current, set())
            if key == "always":
                return value == "yes"
            if key in (
                "VAL_campaign_objectives_met", "STP_heg_northern_final_resolved",
                "STP_pw_party_external_order_resolved", "STP_pw_party_northern_march_resolved",
                "RUS_khan_governing", "ADISCORD_west_final_active", "ADISCORD_south_final_active",
            ):
                return self.outside_predicates.get((current, key), False) == (value == "yes")
            raise AssertionError(f"Unsupported crisis condition {key} in {current}")

        index = 0
        while index < len(rows):
            entry = rows[index]
            if not entry.key:
                kind, operator, amount = [row.value for row in rows[index:index + 3]]
                assert operator == ">", (kind, operator, amount)
                result = self.buildings.get((current, kind), 0) > float(amount)
                index += 3
            else:
                result = one(entry)
                index += 1
            if not result:
                return False
        return True

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
            elif key == "ADISCORD_release_non_participating_minor_optimization":
                self.released_minors.append(current)
            elif key in ("VAL_frontier_close", "VAL_close_northern_coalition_campaign", "VAL_close_northern_aid", "VAL_close_stelander_support", ) and key not in self.effects:
                continue
            elif key in self.effects:
                self.execute(self.effects[key], stack)
            elif key in self.countries or key in ("ROOT", "FROM", "PREV") or key.startswith(("event_target:", "var:")):
                self.execute(value, stack + [self.resolve(key, stack)])
            elif key in ("overlord", "OVERLORD"):
                self.execute(value, stack + [self.subjects[current]])
            elif key in ("every_state", "every_neighbor_state", "every_owned_state", "every_country", "every_subject_country", "every_enemy_country", "every_allied_country"):
                candidates = {
                    "every_state": list(self.owners),
                    "every_neighbor_state": self.state_neighbours.get(current, []),
                    "every_owned_state": [s for s, owner in self.owners.items() if owner == current],
                    "every_country": [tag for tag in sorted(self.countries) if self.exists(tag)],
                    "every_subject_country": [tag for tag, owner in self.subjects.items() if owner == current],
                    "every_allied_country": [tag for tag, faction in self.factions.items() if tag != current and faction == self.factions.get(current)],
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
                name = self.array_key(scalar(value, "array"), current)
                for item in list(self.arrays.get(name, [])):
                    self.execute([e for e in value if e.key != "array"], stack + [item])
            elif key in ("clear_array", "clear_temp_array"):
                self.arrays[self.array_key(value, current)] = []
            elif key in ("add_to_array", "add_to_temp_array"):
                name = self.array_key(scalar(value, "array"), current)
                self.arrays.setdefault(name, []).append(self.resolve(scalar(value, "value"), stack))
            elif key == "remove_from_array":
                name = self.array_key(scalar(value, "array"), current)
                index = next((e.value for e in value if e.key == "index"), None)
                if index is not None:
                    self.arrays[name].pop(int(index))
                else:
                    item = self.resolve(scalar(value, "value"), stack)
                    self.arrays[name] = [value for value in self.arrays.get(name, []) if value != item]
            elif key == "clear_global_event_target":
                self.targets.pop("event_target:" + value, None)
            elif key == "set_variable":
                self.variables[self.variable_key(scalar(value, "var"), current)] = float(scalar(value, "value"))
            elif key == "set_temp_variable":
                self.temp_variables[self.variable_key(scalar(value, "var"), current)] = self.numeric_or_scope_value(scalar(value, "value"), current)
            elif key == "add_to_variable":
                variable = self.variable_key(scalar(value, "var"), current)
                self.variables[variable] = self.variables.get(variable, 0) + float(scalar(value, "value"))
            elif key == "clear_variable":
                self.variables.pop(self.variable_key(value, current), None)
            elif key == "remove_mission":
                self.missions = [mission for mission in self.missions if mission != (current, value)]
            elif key == "remove_decision":
                self.active_decisions.discard((current, value))
            elif key == "add_ideas":
                self.ideas.add((current, value))
            elif key == "swap_ideas":
                self.ideas.discard((current, scalar(value, "remove_idea")))
                self.ideas.add((current, scalar(value, "add_idea")))
            elif key == "remove_ideas":
                names = [row.value for row in value] if isinstance(value, list) else [value]
                self.ideas.difference_update((current, name) for name in names)
            elif key == "add_equipment_to_stockpile":
                equipment = (current, scalar(value, "type"))
                self.equipment[equipment] = self.equipment.get(equipment, 0) + float(scalar(value, "amount"))
            elif key == "army_experience":
                self.army_experience += float(value)
            elif key == "add_command_power":
                self.command_power += float(value)
            elif key == "remove_dynamic_modifier":
                self.dynamic_modifiers.remove((current, scalar(value, "modifier")))
            elif key == "remove_power_balance":
                assert isinstance(value, list), value
                assert self.power_balances.get(current) == scalar(value, "id"), value
                del self.power_balances[current]
            elif key == "set_country_flag":
                flag = scalar(value, "flag") if isinstance(value, list) else value
                self.flags[current].add(flag)
            elif key == "clr_global_flag":
                self.global_flags.discard(value)
            elif key == "set_global_flag":
                self.global_flags.add(value)
            elif key == "clr_country_flag":
                self.flags[current].discard(value)
            elif key == "set_state_flag":
                self.state_flags.setdefault(current, set()).add(value)
            elif key == "clr_state_flag":
                self.state_flags.setdefault(current, set()).discard(value)
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
                self.declarations.append((current, self.resolve(scalar(value, "target"), stack)))
                self.wars.add(frozenset((current, self.resolve(scalar(value, "target"), stack))))
                self.war_sides.append({current})
            elif key == "add_to_war":
                host = self.resolve(scalar(value, "targeted_alliance"), stack)
                self.joins.append((current, host, self.resolve(scalar(value, "enemy"), stack)))
                self.wars.add(frozenset((current, self.resolve(scalar(value, "enemy"), stack))))
                next(side for side in self.war_sides if host in side).add(current)
            elif key == "white_peace":
                # The snapshot must survive loss of every war relation.
                if self.peace_mode == "pair":
                    self.wars.discard(frozenset((current, self.resolve(value, stack))))
                else:
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
            elif key == "end_puppet":
                self.subjects.pop(self.resolve(value, stack), None)
            elif key == "delete_unit":
                self.units[current] = 0
            elif key == "destroy_ships":
                self.destroyed_ships.append((current, scalar(value, "type")))
            elif key == "set_equipment_fraction":
                for equipment in list(self.equipment):
                    if equipment[0] == current:
                        self.equipment[equipment] *= float(value)
            elif key == "change_tag_from":
                previous = self.resolve(value, stack)
                self.ai_countries.add(previous)
                self.ai_countries.discard(current)
                self.player_handoffs.append((previous, current))
            elif key == "set_demilitarized_zone":
                if value == "yes":
                    self.demilitarized.add(current)
                else:
                    self.demilitarized.discard(current)
            elif key == "set_state_category":
                self.state_categories[current] = value
            elif key == "set_building_level":
                kind = scalar(value, "type")
                level = int(scalar(value, "level"))
                assert scalar(value, "instant_build") == "yes", value
                province = next((row.value for row in value if row.key == "province"), None)
                if province is None:
                    assert self.buildings.get((current, kind), 0) > 0, (current, kind)
                    self.buildings[current, kind] = level
                else:
                    assert scalar(province, "all_provinces") == "yes", province
                    assert [row.value for row in province if not row.key] == ["level", ">", "0"], province
                    for building in list(self.province_buildings):
                        if building[0] == current and building[2] == kind and self.province_buildings[building] > 0:
                            self.province_buildings[building] = level
                self.building_mutations.append((current, kind))
            elif key == "set_cosmetic_tag":
                self.cosmetic_tags[current] = value
            elif key in ("set_capital", "set_research_slots", "set_stability", "set_war_support", "set_political_power", "country_lock_all_division_template", "load_focus_tree"):
                self.country_settings[current, key] = value
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
            elif key == "random_other_country":
                gate = next((e.value for e in value if e.key == "limit"), [])
                eligible = [tag for tag in sorted(self.countries) if tag != current and self.exists(tag) and self.matches(gate, stack + [tag])]
                if eligible:
                    self.execute([e for e in value if e.key != "limit"], stack + [eligible[0]])
            elif key == "dismantle_faction":
                faction = self.factions.get(current)
                self.factions = {tag: item for tag, item in self.factions.items() if item != faction}
                self.faction_leaders.discard(current)
            elif key == "create_faction_from_template":
                self.factions[current] = scalar(value, "name")
                self.faction_leaders.add(current)
            elif key == "add_to_faction":
                self.factions[self.resolve(value, stack)] = self.factions[current]
            elif key in ("create_entity", "destroy_entity", "set_entity_animation", "goto_province", "goto_state"):
                self.visuals.append((current, key, value))
            elif key.isdigit() and isinstance(value, list):
                self.execute(value, stack + [key])
            elif key == "leave_faction":
                self.factions.pop(current, None)
            elif key == "retire_character":
                assert self.rulers.get(current) == value, (current, value)
                self.retired.append(value)
                del self.rulers[current]
            elif key in ("remove_claim_by", "custom_effect_tooltip", "unlock_decision_tooltip", "mark_focus_tree_layout_dirty", "log", "force_update_dynamic_modifier", "set_rule"):
                continue
            else:
                raise AssertionError(f"Unsupported crisis effect {key} in {current}")


class QueuedRusCrisisFixture(RusCrisisFixture):
    """Native diplomacy becomes visible on the next tick, before due events."""

    def __init__(self):
        self.hour = 0
        self.delayed_declaration = True
        self.queued_relations = []
        self.entry_events = []
        self.rejected = set()
        super().__init__()

    def matches(self, rows, stack):
        for entry in rows:
            if entry.key.startswith("event_target:") and isinstance(entry.value, list):
                if entry.key not in self.targets:
                    raise AssertionError("Unresolved native event target: " + entry.key)
        return super().matches(rows, stack)

    def execute(self, rows, stack):
        from tools.tests.test_adiscord_stp_preparation import scalar

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
            elif key == "declare_war_on" and self.delayed_declaration:
                enemy = self.resolve(scalar(value, "target"), stack)
                self.declarations.append((stack[-1], enemy))
                self.queued_relations.append((stack[-1], enemy, None))
            elif key == "add_to_war":
                host = self.resolve(scalar(value, "targeted_alliance"), stack)
                enemy = self.resolve(scalar(value, "enemy"), stack)
                if frozenset((host, enemy)) not in self.wars:
                    raise AssertionError("Invitation before its native war exists")
                self.joins.append((stack[-1], host, enemy))
                self.queued_relations.append((stack[-1], enemy, host))
            elif key == "country_event" and scalar(value, "id") in (
                "ADISCORD_rus_crisis.9", "ADISCORD_rus_crisis.11", "ADISCORD_rus_crisis.13",
            ):
                self.entry_events.append((
                    self.hour + int(scalar(value, "hours")),
                    stack[-1], scalar(value, "id"),
                ))
            else:
                super().execute([entry], stack)

    def tick(self):
        self.hour += 1
        for country, enemy, host in self.queued_relations:
            if country in self.rejected or not self.exists(country):
                continue
            self.wars.add(frozenset((country, enemy)))
            if host is None:
                self.war_sides.append({country})
            else:
                next(side for side in self.war_sides if host in side).add(country)
        self.queued_relations.clear()
        due = [event for event in self.entry_events if event[0] <= self.hour]
        self.entry_events = [event for event in self.entry_events if event[0] > self.hour]
        for _, country, event in due:
            if not self.exists(country):
                continue
            effect = {
                "ADISCORD_rus_crisis.9": "RUS_crisis_retry_intervention_entry",
                "ADISCORD_rus_crisis.11": "RUS_crisis_settle_intervention_entry",
                "ADISCORD_rus_crisis.13": "RUS_crisis_cancel_pending_intervention",
            }[event]
            self.run(effect, country)


class RusCrisisContracts(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar
        self.block = block
        self.entries = entries
        self.scalar = scalar

    def peaceful_empire(self, fixture=RusCrisisFixture):
        world = fixture()
        world.run("RUS_crisis_clear_roster")
        world.variables.clear()
        world.wars.clear()
        world.released_minors.clear()
        world.war_sides.clear()
        world.outside_predicates["RUS", "RUS_khan_governing"] = True
        for tag in ("MON", "VLD", "TMR"):
            world.owners[tag + "_capital"] = tag
            world.controllers[tag + "_capital"] = tag
        return world

    def complete_hegemon_victory(self, world, target):
        if target == "VAL":
            world.completed_focuses.add((target, "VAL_Campaign_Secured"))
            world.outside_predicates[target, "VAL_campaign_objectives_met"] = True
        elif target == "STS":
            world.completed_focuses.add((target, "STP_pc_heg_final_kefreyt"))
            world.flags[target].add("STP_heg_kefreyt_final_won")
            world.outside_predicates[target, "STP_heg_northern_final_resolved"] = True
        elif target == "STP":
            world.completed_focuses.add((target, "STP_pw_party_great_stelander"))
            world.outside_predicates[target, "STP_pw_party_external_order_resolved"] = True
            world.outside_predicates[target, "STP_pw_party_northern_march_resolved"] = True
        else:
            self.assertEqual(target, "NOD")
            world.variables[target, "STP_cw_northern_campaign_status"] = 2
            for member in ("VAL", "STS", "STP"):
                world.subjects[member] = target

    def crisis_decision(self, name):
        category = self.block(
            self.entries("common/decisions/ADISCORD_vorkerland_decisions.txt"),
            "RUS_last_empire_crisis",
        )
        return self.block(category, name)

    def regional_victor(self, world, target):
        region = "south" if target in ("SHL", "NAM") else "west"
        world.owners[target + "_capital"] = target
        world.controllers[target + "_capital"] = target
        world.global_flags.update((
            f"ADISCORD_{region}_final_resolved",
            f"ADISCORD_{region}_hegemon_{target}",
        ))

    def test_queued_declaration_and_allied_entries_preserve_the_whole_roster(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.factions = {"MON": "montar", "WKR": "montar"}
        world.subjects = {"NOD": "WKR", "STS": "MON"}
        expected = {"MON", "VLD", "TMR", "WKR", "NOD", "STS"}
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        self.assertEqual(world.declarations, [("MON", "RUS")])
        self.assertFalse(world.joins)
        self.assertFalse(world.wars)
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "VLD", "TMR"})
        world.run("RUS_crisis_check_external_end")
        self.assertEqual(world.targets["event_target:RUS_crisis_war_anchor"], "MON")
        for _ in range(5):
            world.tick()
            world.run("RUS_crisis_check_external_end")
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), expected)
        self.assertEqual(world.war_sides, [expected])
        self.assertEqual(world.declarations, [("MON", "RUS")])
        self.assertFalse(world.entry_events)
        self.assertTrue(all("RUS_crisis_entry_pending" not in world.flags[tag] for tag in expected))
        self.assertTrue(expected <= world.majors)

    def test_first_defeat_cannot_settle_before_delayed_invitations(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.delayed_declaration = False
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.capitulated.add("MON")
        world.controllers["MON_capital"] = "RUS"
        world.run("RUS_crisis_check_external_end")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertFalse(world.annexed)
        world.tick()
        world.run("RUS_crisis_resolve_capitulation")
        self.assertFalse(world.annexed)
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "VLD", "TMR"})
        for tag in ("VLD", "TMR"):
            world.capitulated.add(tag)
            world.controllers[tag + "_capital"] = "RUS"
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(set(world.annexed), {("RUS", tag) for tag in ("MON", "VLD", "TMR")})

    def test_rejected_entry_releases_only_its_receipt_after_bounded_callbacks(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.rejected.add("VLD")
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        for _ in range(4):
            world.tick()
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "TMR"})
        self.assertNotIn("VLD", world.majors)
        self.assertNotIn("RUS_crisis_entry_pending", world.flags["VLD"])
        self.assertEqual(world.wars, {frozenset(("RUS", tag)) for tag in ("MON", "TMR")})
        self.assertFalse(world.entry_events)

    def test_pending_host_defeat_keeps_its_native_war_for_later_invitations(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.queued_relations.clear()
        world.wars.add(frozenset(("MON", "RUS")))
        world.war_sides.append({"MON"})
        world.capitulated.add("MON")
        world.controllers["MON_capital"] = "RUS"
        world.root, world.from_country = "MON", "RUS"
        world.run("RUS_crisis_record_capitulation", "MON")
        self.assertFalse(world.annexed)
        for _ in range(3):
            world.tick()
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "TMR", "VLD"})
        self.assertEqual(world.war_sides, [{"MON", "TMR", "VLD"}])
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertFalse(world.entry_events)
        self.assertFalse(world.annexed)

    def test_cancelled_entry_callbacks_do_not_restart_the_campaign(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.peace_mode = "pair"
        world.wars.add(frozenset(("MON", "WKR")))
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.run("RUS_crisis_close")
        before = list(world.declarations), list(world.joins)
        for _ in range(3):
            world.tick()
        self.assertEqual((world.declarations, world.joins), before)
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 5)
        self.assertEqual(world.wars, {frozenset(("MON", "WKR"))})
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertFalse(world.entry_events)
        self.assertTrue(all("RUS_crisis_entry_pending" not in flags for flags in world.flags.values()))
        self.assertTrue(all("RUS_crisis_entry_cancelled" not in flags for flags in world.flags.values()))

    def test_failed_first_declaration_does_not_open_unrelated_replacement_wars(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.rejected.add("MON")
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        for _ in range(4):
            world.tick()
        self.assertFalse(world.wars)
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertFalse(world.entry_events)
        self.assertEqual(world.declarations, [("MON", "RUS")])
        self.assertIn(("RUS", "RUS_crisis_laser_countdown"), world.missions)

    def test_annexed_pending_candidate_is_removed_without_its_country_callback(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.owners["VLD_capital"] = "WKR"
        world.controllers["VLD_capital"] = "WKR"
        world.run("RUS_crisis_check_external_end")
        self.assertNotIn("VLD", world.arrays["global.RUS_crisis_defenders"])
        self.assertNotIn("RUS_crisis_entry_pending", world.flags["VLD"])
        self.assertNotIn("VLD", world.majors)
        for _ in range(3):
            world.tick()
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "TMR"})
        self.assertEqual(world.war_sides, [{"MON", "TMR"}])

    def test_prewar_reconciliation_does_not_read_an_absent_anchor(self):
        world = self.peaceful_empire(QueuedRusCrisisFixture)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_check_external_end")
        self.assertNotIn("event_target:RUS_crisis_war_anchor", world.targets)
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)

    def test_ally_subject_is_mandatory_and_all_roster_members_are_annexed(self):
        for target in ("VAL", "STS", "STP", "NOD", "SHL", "NAM", "MON", "VLD", "TMR"):
            for last in (target, "WKR", "RLY"):
                with self.subTest(target=target, last=last):
                    world = self.peaceful_empire()
                    world.owners["ally_subject"] = "RLY"
                    world.owners["main_subject"] = "VEL"
                    world.owners["target"] = target
                    world.factions = {target: "defenders", "WKR": "defenders"}
                    world.subjects = {"RLY": "WKR", "VEL": target}
                    if target in ("VAL", "STS", "STP", "NOD"):
                        self.complete_hegemon_victory(world, target)
                    elif target in ("SHL", "NAM"):
                        self.regional_victor(world, target)
                    world.variables["RUS", "RUS_crisis_phase"] = 1
                    world.run("RUS_crisis_launch")
                    expected = {"MON", "VLD", "TMR", target, "WKR", "RLY", "VEL"}
                    if target == "NOD":
                        expected.update(("VAL", "STP", "STS"))
                    self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), expected)
                    self.assertTrue(all(frozenset(("RUS", tag)) in world.wars for tag in expected))
                    world.capitulated.update(expected - {last})
                    for state, owner in world.owners.items():
                        if owner in expected - {last}:
                            world.controllers[state] = "RUS"
                    world.run("RUS_crisis_resolve_capitulation")
                    self.assertFalse(world.annexed)
                    world.root, world.from_country = last, "RUS"
                    world.run("RUS_crisis_record_capitulation", last)
                    self.assertEqual(set(world.annexed), {("RUS", tag) for tag in expected})
                    self.assertTrue(all(world.owners[state] == "RUS" for state in ("ally_subject", "main_subject", "target")))
                    self.assertFalse(world.majors - {"VAL"})

    def test_project_exposure_preserves_wars_factions_and_never_restarts_timers(self):
        from copy import deepcopy

        world = self.peaceful_empire()
        world.peace_mode = "pair"
        world.wars.update((frozenset(("VAL", "STP")), frozenset(("STS", "NOD"))))
        world.subjects["NOD"] = "VAL"
        world.factions = {"VAL": "old_east", "NOD": "old_east", "STS": "old_north"}
        before = dict(world.owners), set(world.wars), dict(world.factions), set(world.majors)
        world.run("RUS_crisis_check_start")
        self.assertEqual((world.owners, world.wars, world.factions, world.majors), before)
        self.assertFalse(world.declarations)
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertEqual({tag for tag, flags in world.flags.items() if "RUS_crisis_warned" in flags}, {"MON", "VLD", "TMR"})
        missions = list(world.missions)
        loaded = deepcopy(world)
        loaded.run("RUS_crisis_check_start")
        loaded.run("RUS_crisis_begin")
        self.assertEqual(loaded.missions, missions)
        self.assertEqual(loaded.variables["RUS", "RUS_crisis_phase"], 1)

    def test_only_one_host_declares_and_existing_blocs_share_the_war(self):
        world = self.peaceful_empire()
        world.factions = {"MON": "montar", "WKR": "montar", "VLD": "vald", "TMR": "timer"}
        world.wars.add(frozenset(("VLD", "STS")))
        factions, wars = dict(world.factions), set(world.wars)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        self.assertEqual(world.declarations, [("MON", "RUS")])
        self.assertEqual(set(world.joins), {("VLD", "MON", "RUS"), ("TMR", "MON", "RUS"), ("WKR", "MON", "RUS")})
        self.assertEqual(world.factions, factions)
        self.assertTrue(wars <= world.wars)
        before = list(world.declarations), list(world.joins)
        world.run("RUS_crisis_launch")
        self.assertEqual((world.declarations, world.joins), before)
        world.run("RUS_crisis_close")
        self.assertEqual(world.factions, factions)

    def test_reactor_loss_is_permanent_but_does_not_end_the_coalition_war(self):
        world = self.peaceful_empire()
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        wars = set(world.wars)
        world.controllers["177"] = "VAL"
        world.run("RUS_crisis_disable_laser")
        self.assertIn("RUS_crisis_laser_disabled", world.flags["RUS"])
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertEqual(world.wars, wars)
        self.assertTrue(world.arrays["global.RUS_crisis_defenders"])
        events = list(world.events)
        world.controllers["177"] = "RUS"
        world.run("RUS_crisis_disable_laser")
        world.run("RUS_crisis_end_world")
        world.run("RUS_crisis_check_start")
        self.assertEqual(world.events, events)
        self.assertNotIn("RUS_crisis_world_ended", world.global_flags)

    def test_hostile_allies_and_prior_separate_wars_do_not_enter_common_roster(self):
        world = self.peaceful_empire()
        world.factions = {"VLD": "vald", "WKR": "vald", "TMR": "vald"}
        world.subjects["NOD"] = "WKR"
        world.wars.update((frozenset(("MON", "WKR")), frozenset(("TMR", "RUS"))))
        wars, factions = set(world.wars), dict(world.factions)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        self.assertEqual(set(world.arrays["global.RUS_crisis_defenders"]), {"MON", "VLD"})
        self.assertTrue(wars <= world.wars)
        self.assertEqual(world.factions, factions)
        self.assertFalse(world.matches(world.triggers["RUS_crisis_defending_bloc"], ["TMR"]))
        self.assertNotIn("RUS_crisis_added_major", world.flags["TMR"])

    def test_foreign_capitulation_preserves_the_loser_and_its_external_war(self):
        world = RusCrisisFixture()
        world.peace_mode = "whole"
        world.wars.add(frozenset(("NOD", "WKR")))
        world.wars.add(frozenset(("STS", "WKR")))
        world.factions = {"NOD": "north", "STS": "north"}
        world.capitulated.add("VAL")
        world.controllers["168"] = "RUS"
        world.controllers["10"] = "WKR"
        world.root, world.from_country = "NOD", "WKR"
        world.run("RUS_crisis_record_capitulation", "NOD")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 3)
        self.assertEqual(world.annexed, [("RUS", "VAL")])
        self.assertEqual(world.owners["10"], "NOD")
        self.assertEqual(world.controllers["10"], "WKR")
        self.assertEqual(world.wars, {frozenset(("NOD", "WKR")), frozenset(("STS", "WKR"))})
        self.assertEqual(world.factions, {"NOD": "north", "STS": "north"})
        self.assertNotIn("RUS_crisis_capitulation_reserved", world.flags["NOD"])

    def test_external_annexation_rechecks_already_defeated_remaining_members(self):
        world = RusCrisisFixture()
        world.capitulated.add("VAL")
        world.controllers["168"] = "RUS"
        world.owners["10"] = "WKR"
        world.controllers["10"] = "WKR"
        world.wars.discard(frozenset(("NOD", "RUS")))
        world.run("RUS_crisis_check_external_end")
        self.assertEqual(world.annexed, [("RUS", "VAL")])
        self.assertEqual(world.owners["10"], "WKR")

    def test_southern_entry_requires_actual_independent_peaceful_winner(self):
        for tag in ("SHL", "NAM"):
            world = self.peaceful_empire()
            self.regional_victor(world, tag)
            gate = world.triggers["RUS_crisis_coalition_candidate"]
            self.assertTrue(world.matches(gate, [tag]))
            world.wars.add(frozenset((tag, "WKR")))
            self.assertFalse(world.matches(gate, [tag]))
            world.wars.clear()
            world.subjects[tag] = "WKR"
            self.assertFalse(world.matches(gate, [tag]))

    def test_val_can_prepare_and_join_late_without_restarting_the_clock(self):
        world = self.peaceful_empire()
        self.complete_hegemon_victory(world, "VAL")
        world.triggers.update({row.key: row.value for row in self.entries("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt") if row.key.startswith("VAL_nw_")})
        world.run("RUS_crisis_begin")
        self.assertTrue(world.matches(world.triggers["VAL_nw_khan_threat"], ["VAL"]))
        world.wars.add(frozenset(("VAL", "STS")))
        world.run("RUS_crisis_launch")
        self.assertNotIn("VAL", world.arrays["global.RUS_crisis_defenders"])
        world.wars.discard(frozenset(("VAL", "STS")))
        self.assertTrue(world.matches(world.triggers["VAL_nw_can_join_khan_intervention"], ["VAL"]))
        clocks = list(world.missions)
        category = self.block(self.entries("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_new_world_category")
        decision = self.block(category, "VAL_nw_challenge_khan")
        world.execute(self.block(decision, "complete_effect"), ["VAL"])
        self.assertIn("VAL", world.arrays["global.RUS_crisis_defenders"])
        self.assertEqual(world.missions, clocks)
        self.assertEqual(world.declarations, [("MON", "RUS")])

    def test_late_join_uses_surviving_war_side_after_original_host_is_annexed(self):
        world = self.peaceful_empire()
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        clocks = list(world.missions)
        world.owners["MON_capital"] = "WKR"
        world.controllers["MON_capital"] = "WKR"
        world.wars.discard(frozenset(("MON", "RUS")))
        world.run("RUS_crisis_check_external_end")
        host = world.targets["event_target:RUS_crisis_war_anchor"]
        self.assertIn(host, ("VLD", "TMR"))
        self.complete_hegemon_victory(world, "VAL")
        world.run("RUS_crisis_start_intervention", "VAL")
        self.assertIn(("VAL", host, "RUS"), world.joins)
        self.assertEqual(world.declarations, [("MON", "RUS")])
        self.assertEqual(world.missions, clocks)

    def test_last_remaining_reactor_zone_is_enough_and_timeout_rechecks_capture(self):
        world = self.peaceful_empire()
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_disable_laser")
        self.assertNotIn("RUS_crisis_laser_disabled", world.flags["RUS"])
        world.controllers["177"] = "VAL"
        world.run("RUS_crisis_end_world")
        self.assertNotIn("RUS_crisis_world_ended", world.global_flags)

    def load_regional_lifecycle(self, world, region):
        from tools.tests.test_adiscord_stp_preparation import walk

        effects = self.entries(f"common/scripted_effects/ADISCORD_{region}_final_war_effects.txt")
        triggers = self.entries(f"common/scripted_triggers/ADISCORD_{region}_final_war_triggers.txt")
        world.effects.update({row.key: row.value for row in effects})
        world.triggers.update({row.key: row.value for row in triggers})
        for row in walk(effects + triggers):
            if re.fullmatch(r"[A-Z]{3}", row.key) and isinstance(row.value, list):
                world.countries.add(row.key)
                world.flags.setdefault(row.key, set())
        # Furnace equipment cleanup has its own tests; this scenario exercises
        # actual regional war closure, major ownership and deferred deadlines.
        world.effects["SHL_clean_campaign"] = []

    def test_parallel_major_owners_release_in_every_order(self):
        from itertools import permutations

        for order in permutations(("west", "south", "rus")):
            world = self.peaceful_empire()
            for region in ("west", "south"):
                self.load_regional_lifecycle(world, region)
            world.majors.discard("MON")
            world.flags["MON"].add("ADISCORD_west_added_major")
            world.majors.add("MON")
            world.run("RUS_crisis_register_defender", "MON")
            self.assertIn("RUS_crisis_added_major", world.flags["MON"])
            register = world.effects["ADISCORD_south_prepare_champion"][-1]
            world.execute([register], ["MON"])
            self.assertIn("ADISCORD_south_added_major", world.flags["MON"])
            for index, owner in enumerate(order):
                if owner == "rus":
                    world.run("RUS_crisis_clear_defender", "MON")
                else:
                    effect_name = "ADISCORD_" + owner + "_close_member_state"
                    world.execute([world.effects[effect_name][0]], ["MON"])
                self.assertEqual("MON" in world.majors, index < 2, order)
            self.assertFalse(world.flags["MON"] & {"RUS_crisis_added_major", "ADISCORD_west_added_major", "ADISCORD_south_added_major"})

    def test_independent_regional_crises_continue_until_the_epilogue(self):
        for region in ("west", "south"):
            world = self.peaceful_empire()
            self.load_regional_lifecycle(world, region)
            world.global_flags.update(("ADISCORD_fresh_campaign_contract_v1", "ADISCORD_vorkerland_collapse_finished", "ADISCORD_nam_resource_war_resolved"))
            world.owners["wrk_capital"] = "WRK"
            world.flags["WRK"].add("ADISCORD_vorkerland_central_unifier")
            gate = world.triggers[f"ADISCORD_{region}_crisis_open"]
            for phase in (1, 2, 4):
                world.variables["RUS", "RUS_crisis_phase"] = phase
                self.assertTrue(world.matches(gate, ["RUS"]))
            world.global_flags.add("RUS_crisis_world_ended")
            self.assertFalse(world.matches(gate, ["RUS"]))

    def test_eastern_hegemon_must_finish_its_wars_and_remain_sovereign_at_entry(self):
        for target in ("VAL", "STP", "STS", "NOD"):
            for invalidation in ("war", "subject", "capitulated", None):
                with self.subTest(target=target, invalidation=invalidation):
                    world = self.peaceful_empire()
                    gate = world.triggers["RUS_crisis_coalition_candidate"]
                    self.assertFalse(world.matches(gate, [target]))
                    self.complete_hegemon_victory(world, target)
                    self.assertTrue(world.matches(gate, [target]))
                    world.run("RUS_crisis_begin")
                    if invalidation == "war":
                        world.wars.add(frozenset((target, "WKR")))
                    elif invalidation == "subject":
                        world.subjects[target] = "WKR"
                    elif invalidation == "capitulated":
                        world.capitulated.add(target)
                    world.run("RUS_crisis_launch")
                    self.assertEqual(frozenset((target, "RUS")) in world.wars, invalidation is None)
                    self.assertEqual("RUS_crisis_defender" in world.flags[target], invalidation is None)

    def test_pending_ainholm_colony_keeps_the_shared_faction(self):
        world = self.peaceful_empire()
        world.countries.add("AIN")
        world.flags["AIN"] = {"VAL_ainholm_colony_pending", "RUS_crisis_defender"}
        world.owners["ain_capital"] = "AIN"
        world.controllers["ain_capital"] = "AIN"
        world.factions = {tag: "coalition" for tag in ("AIN", "VAL", "STP")}
        world.faction_leaders = {"AIN"}
        world.effects.update({row.key: row.value for row in self.entries("common/scripted_effects/ADISCORD_VAL_effects.txt")})
        world.run("VAL_complete_ainholm_colony", "AIN")
        world.run("VAL_complete_ainholm_colony", "AIN")
        self.assertEqual(world.subjects["AIN"], "VAL")
        self.assertEqual(world.factions, {tag: "coalition" for tag in ("AIN", "VAL", "STP")})
        self.assertNotIn("VAL_ainholm_colony_pending", world.flags["AIN"])

    def test_peace_callbacks_preserve_the_other_war_of_two_interveners(self):
        bus = self.block(self.entries("common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"), "on_actions")
        world = self.peaceful_empire()
        world.root, world.from_country = "STP", "VAL"
        for name in ("on_peace", "on_peaceconference_ended"):
            guard = self.block(self.block(self.block(bus, name), "effect"), "if")
            gate = self.block(guard, "limit")
            self.assertTrue(world.matches(gate, ["STP"]))
            world.flags["STP"].add("RUS_crisis_defender")
            world.flags["VAL"].add("RUS_crisis_defender")
            self.assertTrue(world.matches(gate, ["STP"]))
            world.flags["STP"].clear()
            world.flags["VAL"].clear()
            world.global_flags.add("RUS_crisis_world_ended")
            self.assertFalse(world.matches(gate, ["STP"]))
            world.global_flags.clear()

    def test_unrelated_pending_treaty_and_empty_roster_do_not_stop_the_programme(self):
        world = self.peaceful_empire()
        for tag in ("MON", "VLD", "TMR"):
            world.subjects[tag] = "WKR"
        world.flags["VAL"].add("ADISCORD_south_settlement_pending")
        world.run("RUS_crisis_check_start")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 1)
        world.run("RUS_crisis_launch")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertFalse(world.annexed)
        world.run("RUS_crisis_end_world")
        self.assertIn("RUS_crisis_world_ended", world.global_flags)

    def test_only_terminal_epilogue_rejects_new_wars(self):
        world = self.peaceful_empire()
        world.peace_mode = "pair"
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.root, world.from_country = "VAL", "STP"
        world.wars.add(frozenset(("VAL", "STP")))
        world.run("RUS_crisis_enforce_truce", "VAL")
        self.assertIn(frozenset(("VAL", "STP")), world.wars)
        self.assertIn(frozenset(("MON", "RUS")), world.wars)
        world.global_flags.add("RUS_crisis_world_ended")
        world.run("RUS_crisis_enforce_truce", "VAL")
        self.assertNotIn(frozenset(("VAL", "STP")), world.wars)
        self.assertNotIn("RUS_crisis_truce_in_progress", world.global_flags)

    def test_terminal_scene_leaves_only_bunker_and_anarchy_and_cannot_fire_twice(self):
        world = self.peaceful_empire()
        world.peace_mode = "pair"
        world.ai_countries.remove("VAL")
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.factions = {"MON": "montar", "VLD": "vald"}
        world.faction_leaders = {"MON", "VLD"}
        world.subjects["NOD"] = "MON"
        living = set(world.owners.values())
        world.buildings["66", "air_base"] = 2
        world.run("RUS_crisis_end_world")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 6)
        self.assertEqual(world.demilitarized, {"125"})
        self.assertEqual(world.buildings["66", "air_base"], 0)
        self.assertEqual(world.buildings["66", "industrial_complex"], 3)
        self.assertNotIn(("RUS", "ADISCORD_rus_crisis.12"), world.events)
        for _ in range(60):
            if "RUS_crisis_world_ruins_complete" in world.global_flags:
                break
            world.run("RUS_crisis_ruin_next_wave")
        self.assertIn("RUS_crisis_world_ruins_complete", world.global_flags)
        self.assertEqual(set(world.owners.values()), {"RUS", "EXZ"})
        self.assertEqual([state for state, owner in world.owners.items() if owner == "RUS"], ["66"])
        self.assertEqual(world.owners, world.controllers)
        self.assertEqual(world.demilitarized, set(world.owners) - {"66"})
        self.assertTrue(all(level == 0 for (state, _), level in world.buildings.items() if state != "66"))
        self.assertTrue(all(world.units[tag] == 0 for tag in living))
        self.assertFalse(world.subjects)
        self.assertFalse(world.factions)
        self.assertEqual(world.player_handoffs, [("VAL", "EXZ")])
        self.assertEqual(world.cosmetic_tags["RUS"], "RUS_last_bunker")
        self.assertEqual(world.cosmetic_tags["EXZ"], "RUS_world_anarchy")
        self.assertFalse(world.wars)
        self.assertFalse(world.arrays["global.RUS_crisis_defenders"])
        self.assertEqual(world.majors, {"VAL"})
        self.assertIn(("EXZ", "ADISCORD_rus_crisis.8"), world.events)
        self.assertEqual(len([row for row in world.visuals if row[1] == "create_entity"]), 2)
        before = list(world.visuals), list(world.events)
        world.run("RUS_crisis_end_world")
        self.assertEqual((world.visuals, world.events), before)
        world.run("RUS_crisis_epilogue_next", "EXZ")
        self.assertEqual(world.variables["EXZ", "RUS_crisis_epilogue_page"], 2)
        self.assertFalse([row for row in world.visuals if row[1] == "destroy_entity"])
        world.run("RUS_crisis_epilogue_finish", "EXZ")
        world.run("RUS_crisis_epilogue_next", "EXZ")
        self.assertEqual(world.variables["EXZ", "RUS_crisis_epilogue_page"], 5)

    def test_destruction_waves_are_bounded_survive_loading_and_outlive_reading(self):
        from copy import deepcopy

        world = self.peaceful_empire()
        for state in range(500, 600):
            key = str(state)
            world.owners[key] = "WKR"
            world.controllers[key] = "WKR"
            world.buildings[key, "industrial_complex"] = 3
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_end_world")
        self.assertEqual(world.demilitarized, {"125"})
        world.run("RUS_crisis_epilogue_finish", "RUS")
        state_queue = "global.RUS_world_state_queue"
        country_queue = "global.RUS_world_country_queue"
        cleanup_queue = "global.RUS_world_cleanup_queue"
        initial_states = len(world.arrays[state_queue])
        for wave in range(initial_states + len(world.arrays[country_queue]) + len(world.arrays[cleanup_queue])):
            states_before = set(world.demilitarized)
            countries_before = len(world.arrays[country_queue])
            cleanup_before = len(world.arrays[cleanup_queue])
            world.run("RUS_crisis_ruin_next_wave")
            self.assertLessEqual(len(world.demilitarized - states_before), 1)
            self.assertLessEqual(countries_before - len(world.arrays[country_queue]), 1)
            self.assertLessEqual(cleanup_before - len(world.arrays[cleanup_queue]), 1)
            self.assertEqual(world.owners["66"], "RUS")
            if world.arrays[state_queue] or world.arrays[country_queue]:
                self.assertEqual(len(world.arrays[cleanup_queue]), cleanup_before)
                self.assertFalse(world.annexed)
            if wave == 0:
                self.assertEqual(len(world.arrays[state_queue]), initial_states - 1)
                queues = deepcopy(world.arrays)
                world.run("RUS_crisis_end_world")
                self.assertEqual(world.arrays, queues)
                world = deepcopy(world)
            if "RUS_crisis_world_ruins_complete" in world.global_flags:
                break
        else:
            self.fail("Persistent destruction queues failed to drain")
        self.assertEqual(set(world.owners.values()), {"RUS", "EXZ"})
        self.assertEqual(world.demilitarized, set(world.owners) - {"66"})
        self.assertTrue(all(level == 0 for (state, _), level in world.buildings.items() if state != "66"))
        self.assertEqual(world.variables["RUS", "RUS_crisis_epilogue_page"], 5)
        scheduled = list(world.events)
        world.run("RUS_crisis_ruin_next_wave")
        self.assertEqual(world.events, scheduled)

    def test_destruction_dispatch_has_one_hourly_event_chain_and_stops_when_complete(self):
        from tools.tests.test_adiscord_stp_preparation import walk

        world = self.peaceful_empire()
        hooks = self.block(self.entries("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        self.assertFalse([row for row in walk(hooks) if row.key == "RUS_crisis_ruin_next_wave"])
        event_id = "ADISCORD_rus_crisis.14"
        events = self.entries("events/ADISCORD_vorkerland_events.txt")
        event = next(row.value for row in events if row.key == "country_event" and self.scalar(row.value, "id") == event_id)
        payload = self.block(event, "immediate")
        gate = self.block(event, "trigger")
        self.assertEqual(self.scalar(event, "hidden"), "yes")
        self.assertEqual(self.scalar(event, "is_triggered_only"), "yes")
        self.assertEqual(self.scalar(gate, "tag"), "RUS")
        for source in (world.effects["RUS_crisis_reduce_world_to_ruins"], payload):
            calls = [row.value for row in walk(source) if row.key == "country_event"]
            self.assertEqual(len(calls), 1)
            self.assertEqual(self.scalar(calls[0], "id"), event_id)
            self.assertEqual(self.scalar(calls[0], "hours"), "1")
            self.assertNotIn("days", {row.key for row in calls[0]})
        for effect in ("RUS_crisis_ruin_next_wave", "RUS_crisis_ruin_next_state", "RUS_crisis_enqueue_ruin_neighbors"):
            self.assertFalse([row for row in walk(world.effects[effect]) if row.key in ("country_event", "for_loop_effect")])
            self.assertFalse([row for row in walk(world.effects[effect]) if row.key in ("every_state", "every_country")])
        self.assertFalse(world.matches(gate, ["RUS"]))
        world.run("RUS_crisis_ruin_next_wave")
        self.assertFalse(world.events)
        self.assertFalse(world.demilitarized)
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_end_world")
        self.assertEqual(world.events.count(("RUS", event_id)), 1)
        self.assertFalse(world.matches(gate, ["EXZ"]))
        before = len(world.arrays["global.RUS_world_state_queue"])
        self.assertTrue(world.matches(gate, ["RUS"]))
        world.events.remove(("RUS", event_id))
        world.execute(payload, ["RUS"])
        self.assertEqual(len(world.arrays["global.RUS_world_state_queue"]), before - 1)
        for _ in range(60):
            if not world.matches(gate, ["RUS"]):
                break
            self.assertEqual(world.events.count(("RUS", event_id)), 1)
            world.events.remove(("RUS", event_id))
            world.execute(payload, ["RUS"])
        self.assertIn("RUS_crisis_world_ruins_complete", world.global_flags)
        self.assertNotIn(("RUS", event_id), world.events)
        mutations = list(world.building_mutations)
        world.execute(payload, ["RUS"])
        self.assertEqual(world.building_mutations, mutations)
        self.assertNotIn(("RUS", event_id), world.events)

    def test_destruction_spreads_from_reactor_without_duplicates_and_reaches_islands(self):
        from copy import deepcopy

        world = self.peaceful_empire()
        # A diamond and a cycle meet at 169; 40 is an isolated island.
        edges = (("125", "49"), ("125", "51"), ("49", "169"), ("51", "169"), ("169", "177"), ("177", "49"), ("125", "66"))
        for first, second in edges:
            world.state_neighbours.setdefault(first, []).append(second)
            world.state_neighbours.setdefault(second, []).append(first)
        world.run("RUS_crisis_begin")
        world.owners["49"] = "EXZ"
        world.controllers["49"] = "EXZ"
        world.run("RUS_crisis_end_world")
        self.assertEqual(world.arrays["global.RUS_world_frontier_queue"], ["49", "51"])
        order = []
        total = len(world.arrays["global.RUS_world_state_queue"])
        for index in range(total):
            before = set(world.demilitarized)
            world.run("RUS_crisis_ruin_next_wave")
            added = world.demilitarized - before
            self.assertEqual(len(added), 1)
            order.extend(added)
            frontier = world.arrays["global.RUS_world_frontier_queue"]
            self.assertEqual(len(frontier), len(set(frontier)))
            self.assertTrue(set(frontier).issubset(world.arrays["global.RUS_world_state_queue"]))
            self.assertNotIn("66", frontier)
            if index == 1:
                world = deepcopy(world)
        self.assertEqual(order[:4], ["49", "51", "169", "177"])
        self.assertGreater(order.index("40"), 3)
        self.assertEqual(len(order), len(set(order)))
        self.assertFalse(world.arrays["global.RUS_world_frontier_queue"])
        self.assertEqual(world.owners["66"], "RUS")

    def test_ruin_state_clears_existing_buildings_and_every_port_without_creating_any(self):
        world = self.peaceful_empire()
        world.buildings["40", "infrastructure"] = 4
        world.province_buildings = {
            ("40", "4001", "naval_base"): 2,
            ("40", "4002", "naval_base"): 5,
            ("40", "4003", "naval_base"): 0,
            ("46", "4601", "naval_base"): 3,
        }
        building_keys = set(world.buildings)
        port_keys = set(world.province_buildings)
        world.run("RUS_crisis_ruin_state", "40")
        self.assertEqual(world.buildings["40", "industrial_complex"], 0)
        self.assertEqual(world.buildings["40", "infrastructure"], 0)
        self.assertEqual([level for (state, _, _), level in world.province_buildings.items() if state == "40"], [0, 0, 0])
        self.assertEqual(world.province_buildings["46", "4601", "naval_base"], 3)
        world.run("RUS_crisis_ruin_state", "40")
        self.assertEqual(set(world.buildings), building_keys)
        self.assertEqual(set(world.province_buildings), port_keys)

    def test_bunker_and_anarchy_observer_have_separate_reading_pages(self):
        from copy import deepcopy

        world = self.peaceful_empire()
        world.ai_countries.difference_update(("RUS", "VAL"))
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_end_world")
        self.assertEqual(world.player_handoffs, [("VAL", "EXZ")])
        self.assertEqual(world.countries - world.ai_countries, {"RUS", "EXZ"})
        visible = world.triggers["RUS_crisis_strike_visible"]
        self.assertTrue(world.matches(visible, ["EXZ"]))
        self.assertTrue(world.matches(visible, ["RUS"]))
        world.run("RUS_crisis_epilogue_next", "EXZ")
        self.assertFalse(world.matches(visible, ["EXZ"]))
        self.assertTrue(world.matches(visible, ["RUS"]))
        world.run("RUS_crisis_epilogue_finish", "EXZ")
        loaded = deepcopy(world)
        loaded.run("RUS_crisis_epilogue_next", "RUS")
        self.assertEqual(loaded.variables["RUS", "RUS_crisis_epilogue_page"], 2)
        self.assertEqual(loaded.variables["EXZ", "RUS_crisis_epilogue_page"], 5)
        for page in (3, 4, 5):
            loaded.run("RUS_crisis_epilogue_next", "RUS")
            self.assertEqual(loaded.variables["RUS", "RUS_crisis_epilogue_page"], page)
        self.assertFalse([row for row in loaded.visuals if row[1] == "destroy_entity"])

    def test_camera_and_particle_use_the_real_reactor_and_existing_entity(self):
        source = read(EFFECT_FILE)
        scene = self.block(self.entries(str(EFFECT_FILE.relative_to(ROOT))), "RUS_crisis_play_strike")
        actors = [row.value for row in self.block(scene, "125") if row.key == "create_entity"]
        self.assertEqual([self.scalar(row, "id") for row in actors], ["610792", "610793"])
        for actor in actors:
            self.assertEqual(ORBITAL_ACTOR_POSITIONS[self.scalar(actor, "entity")], (self.scalar(actor, "x"), self.scalar(actor, "y")))
            self.assertEqual(self.scalar(actor, "z"), "0")
            self.assertFalse([row for row in actor if row.key == "visible"])
        event = next(row.value for row in self.entries("events/ADISCORD_vorkerland_events.txt") if row.key == "country_event" and self.scalar(row.value, "id") == "ADISCORD_rus_crisis.8")
        self.assertEqual(self.scalar(self.block(event, "immediate"), "goto_province"), "5228")
        self.assertNotIn("goto_province", source[source.index("RUS_crisis_end_world = {"):source.index("RUS_crisis_play_strike = {")])
        self.assertIn("5228", read(ROOT / "history/states/125-Reactor.txt"))

    def test_military_victory_story_distinguishes_live_and_disabled_laser(self):
        event = next(row.value for row in self.entries("events/ADISCORD_vorkerland_events.txt") if row.key == "country_event" and self.scalar(row.value, "id") == "ADISCORD_rus_campaign.11")
        world = self.peaceful_empire()
        world.variables["RUS", "RUS_crisis_phase"] = 3
        descriptions = [row.value for row in event if row.key == "desc"]
        for disabled, expected in ((False, "ADISCORD_rus_campaign.11.active_project"), (True, "ADISCORD_rus_campaign.11.d")):
            if disabled:
                world.flags["RUS"].add("RUS_crisis_laser_disabled")
            selected = [self.scalar(row, "text") for row in descriptions if world.matches(self.block(row, "trigger"), ["RUS"])]
            self.assertEqual(selected, [expected])
        world.global_flags.add("RUS_crisis_world_ended")
        self.assertFalse(world.matches(self.block(event, "trigger"), ["RUS"]))

    def test_every_epilogue_page_is_localised_bounded_and_has_no_author_credits(self):
        for language in ("russian", "english"):
            source = read(ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml")
            for page in (2, 3, 4, 5):
                for part in ("title", "body"):
                    key = f"RUS_crisis_epilogue_{page}_{part}"
                    matches = re.findall(r'(?m)^ ' + key + r': "((?:[^"\\]|\\.)*)"$', source)
                    self.assertEqual(len(matches), 1, key)
                    rendered = matches[0].replace("\\n", "\n")
                    self.assertLess(len(rendered), 900)
                    self.assertLess(len(rendered.encode("utf-8")), 1800)

    def test_restoring_conquests_does_not_take_foreign_owned_land(self):
        world = RusCrisisFixture()
        world.capitulated.update(("VAL", "NOD"))
        world.controllers.update({"168": "RUS", "10": "RUS"})
        world.run("RUS_crisis_resolve_capitulation")
        world.owners["168"] = "WKR"
        world.controllers["168"] = "WKR"
        world.run("RUS_crisis_restore_conquests")
        self.assertEqual(world.owners["168"], "WKR")
        self.assertEqual(world.controllers["168"], "WKR")
        self.assertEqual(world.owners["10"], "NOD")

    def test_empire_defeat_outside_active_crisis_also_dissolves(self):
        for phase in (None, 1, 3, 5):
            with self.subTest(phase=phase):
                world = self.peaceful_empire()
                if phase is not None:
                    world.variables["RUS", "RUS_crisis_phase"] = phase
                world.wars.add(frozenset(("RUS", "WKR")))
                world.root = "RUS"
                world.from_country = "WKR"
                world.run("RUS_crisis_record_capitulation")
                self.assertNotIn("RUS", world.owners.values())
                self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 4)
                self.assertEqual(world.targets["event_target:RUS_crisis_hegemon"], "WKR")
                self.assertIn("RUS_crisis_capitulation_reserved", world.flags["RUS"])

    def test_new_regional_winners_have_defence_ui_and_a_single_defeat_description(self):
        category = self.block(self.entries("common/decisions/categories/ADISCORD_vorkerland_categories.txt"), "RUS_last_empire_crisis")
        events = self.entries("events/ADISCORD_vorkerland_events.txt")
        event = next(row.value for row in events if row.key == "country_event" and self.scalar(row.value, "id") == "ADISCORD_rus_crisis.4")
        for target in ("SHL", "NAM", "WRK", "IVN"):
            world = self.peaceful_empire()
            for rows in (category, self.crisis_decision("RUS_crisis_defence_countdown"), self.crisis_decision("RUS_crisis_establish_special_zone")):
                self.assertTrue(world.matches(self.block(rows, "allowed"), [target]))
            for course in (1, 2, 3):
                world.variables[target, "RUS_crisis_defeated_course"] = course
                descriptions = [row.value for row in event if row.key == "desc" and world.matches(self.block(row.value, "trigger"), [target])]
                self.assertEqual(len(descriptions), 1, (target, course))

    def test_late_hook_without_immediate_callback_settles_and_reserves_generic_peace(self):
        from tools.lib.on_actions import read_scripted_peace
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        shared = ROOT / "common/on_actions/09_ADISCORD_scripted_peace_on_actions.txt"
        hooks = self.block(parse_clausewitz(read_scripted_peace(shared, "vorkerland_collapse")), "on_actions")
        late = self.block(self.block(hooks, "on_capitulation"), "effect")[2:4]
        for loser, victor in (("VAL", "RUS"), ("RUS", "VAL")):
            world = RusCrisisFixture()
            world.capitulated.add("NOD")
            world.controllers.update({"168": "RUS", "10": "RUS"})
            world.root = loser
            world.from_country = victor
            world.execute(late, [loser])
            self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 3 if loser == "VAL" else 4)
            self.assertIn("skip_default_capitulation", world.global_flags)
            self.assertNotIn("RUS_crisis_capitulation_reserved", world.flags[loser])

    def test_late_war_entrant_subject_of_an_ally_joins_roster_once(self):
        hooks = self.block(self.entries("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        register = self.block(self.block(hooks, "on_war_relation_added"), "effect")[1:2]
        for reverse in (False, True):
            world = RusCrisisFixture()
            world.subjects["WKR"] = "NOD"
            world.targets["event_target:RUS_crisis_war_anchor"] = "VAL"
            world.war_sides[0].add("WKR")
            world.root, world.from_country = ("WKR", "RUS") if reverse else ("RUS", "WKR")
            world.wars.add(frozenset(("RUS", "WKR")))
            world.execute(register, [world.root])
            world.execute(register, [world.root])
            self.assertEqual(world.arrays["global.RUS_crisis_defenders"].count("WKR"), 1)
            world.capitulated.update(("VAL", "NOD"))
            world.controllers.update({"168": "RUS", "10": "RUS"})
            self.assertFalse(world.matches(world.triggers["RUS_crisis_all_defenders_defeated"], ["RUS"]))

    def test_native_ally_entry_expands_its_own_subjects_once(self):
        hooks = self.block(self.entries("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_actions")
        register = self.block(self.block(hooks, "on_war_relation_added"), "effect")[1:2]
        for reverse in (False, True):
            world = self.peaceful_empire()
            world.run("RUS_crisis_begin")
            world.run("RUS_crisis_launch")
            world.factions = {"MON": "montar", "WKR": "montar"}
            world.subjects["NOD"] = "WKR"
            world.wars.add(frozenset(("WKR", "RUS")))
            next(side for side in world.war_sides if "MON" in side).add("WKR")
            world.root, world.from_country = ("WKR", "RUS") if reverse else ("RUS", "WKR")
            world.execute(register, [world.root])
            world.run("RUS_crisis_confirm_intervention_entry", "MON")
            world.execute(register, [world.root])
            self.assertEqual(world.arrays["global.RUS_crisis_defenders"].count("WKR"), 1)
            self.assertEqual(world.arrays["global.RUS_crisis_defenders"].count("NOD"), 1)
            self.assertEqual([row for row in world.joins if row[0] == "NOD"], [("NOD", "WKR", "RUS")])

    def test_rejected_pending_member_cannot_peace_out_the_active_coalition(self):
        world = self.peaceful_empire()
        world.run("RUS_crisis_begin")
        world.run("RUS_crisis_launch")
        world.run("RUS_crisis_register_defender", "WKR")
        world.flags["WKR"].add("RUS_crisis_entry_pending")
        world.run("RUS_crisis_remove_defender", "WKR")
        self.assertNotIn("RUS_crisis_entry_cancelled", world.flags["WKR"])
        world.wars.add(frozenset(("WKR", "RUS")))
        before = set(world.wars)
        world.run("RUS_crisis_cancel_pending_intervention", "WKR")
        self.assertEqual(world.wars, before)

    def test_dissolution_closes_subject_war_pairs_and_preserves_their_other_war(self):
        world = RusCrisisFixture()
        world.peace_mode = "pair"
        world.subjects["WKR"] = "RUS"
        world.factions = {"RUS": "empire", "WKR": "empire"}
        world.wars.update((frozenset(("WKR", "VAL")), frozenset(("WKR", "NOD")), frozenset(("WKR", "STS"))))
        world.capitulated.add("RUS")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(world.wars, {frozenset(("WKR", "STS"))})
        self.assertNotIn("WKR", world.factions)
        self.assertNotIn("WKR", world.subjects)

    def test_war_focus_is_available_before_warning_and_during_campaign(self):
        tree = self.block(self.entries(str(FOCUS_FILE.relative_to(ROOT))), "focus_tree")
        focus = next(
            entry.value for entry in tree
            if entry.key == "focus" and self.scalar(entry.value, "id") == "RUS_break_the_hegemon"
        )
        gate = self.block(focus, "available")
        for phase in (None, 1, 2, 3, 4, 5):
            with self.subTest(phase=phase):
                world = self.peaceful_empire()
                if phase is not None:
                    world.variables["RUS", "RUS_crisis_phase"] = phase
                self.assertEqual(world.matches(gate, ["RUS"]), phase in (None, 1, 2, 3))
                self.assertNotIn("bypass", [row.key for row in focus])
        world = self.peaceful_empire()
        world.flags["RUS"].clear()
        self.assertFalse(world.matches(gate, ["RUS"]))
        reward = self.block(focus, "completion_reward")
        self.assertNotIn("RUS_crisis_challenge_hegemon", str(reward))

    def test_ai_prepares_for_each_selected_hegemon_and_stops_at_campaign_end(self):
        strategies = [row.value for row in self.entries("common/ai_strategy/ADISCORD_vorkerland_ai.txt") if "_crisis_" in row.key]

        def enabled(world, country, kind):
            targets = []
            for strategy in strategies:
                self.assertEqual(self.scalar(strategy, "abort_when_not_enabled"), "yes")
                order = self.block(strategy, "ai_strategy")
                if self.scalar(order, "type") != kind:
                    continue
                if world.matches(self.block(strategy, "allowed"), [country]) and world.matches(self.block(strategy, "enable"), [country]):
                    targets.append(self.scalar(order, "id"))
            return targets

        for target in ("VAL", "STS", "STP", "NOD"):
            with self.subTest(target=target):
                world = self.peaceful_empire()
                self.complete_hegemon_victory(world, target)
                world.run("RUS_crisis_check_start")
                self.assertCountEqual(enabled(world, "RUS", "prepare_for_war"), (target, "MON", "VLD", "TMR"))
                self.assertEqual(enabled(world, target, "prepare_for_war"), ["RUS"])
                for neutral in {"VAL", "STS", "STP", "NOD"} - {target}:
                    self.assertEqual(enabled(world, neutral, "prepare_for_war"), [])
                world.run("RUS_crisis_launch")
                enemies = {target, "MON", "VLD", "TMR"}
                if target == "NOD":
                    enemies.update(("VAL", "STP", "STS"))
                self.assertCountEqual(enabled(world, "RUS", "conquer"), enemies)
                self.assertEqual(enabled(world, "RUS", "prepare_for_war"), [])
                self.assertEqual(enabled(world, target, "prepare_for_war"), [])
                world.variables["RUS", "RUS_crisis_phase"] = 3
                self.assertEqual(enabled(world, "RUS", "conquer"), [])

    def frontier_world(self, target):
        world = self.peaceful_empire()
        world.countries.add(target)
        world.flags.setdefault(target, set())
        world.owners["frontier"] = target
        world.neighbours.add(frozenset(("RUS", target)))
        world.from_country = target
        return world

    def test_six_frontiers_remain_actionable_after_proclamation_and_liberation(self):
        decision = self.crisis_decision("RUS_imperial_frontier_campaign")
        targets = {entry.value for entry in self.block(decision, "targets")}
        self.assertEqual(targets, {"TMR", "VEL", "RLY", "IRT", "ERT", "SCA"})
        self.assertEqual(self.scalar(decision, "cost"), "50")
        self.assertFalse(any(entry.key == "fire_only_once" for entry in decision))
        for target in targets:
            with self.subTest(target=target):
                world = self.frontier_world(target)
                self.assertTrue(world.matches(self.block(decision, "visible"), ["RUS"]))
                self.assertTrue(world.matches(self.block(decision, "available"), ["RUS"]))
                world.execute(self.block(decision, "complete_effect"), ["RUS"])
                self.assertEqual(world.wars, {frozenset(("RUS", target))})
                self.assertEqual(world.released_minors, [target])
                self.assertFalse(world.matches(self.block(decision, "available"), ["RUS"]))
                world.wars.clear()
                self.assertTrue(world.matches(self.block(decision, "available"), ["RUS"]))

    def test_relyn_wakes_when_frontier_wars_unlock_before_any_war_is_chosen(self):
        effect = self.block(
            self.entries(str(EFFECT_FILE.relative_to(ROOT))),
            "ADISCORD_vorkerland_rus_proclaim_last_empire",
        )
        payload = self.block(effect, "if")
        release = self.block(payload, "RLY")
        self.assertEqual(
            self.scalar(release, "ADISCORD_release_non_participating_minor_optimization"),
            "yes",
        )
        keys = [entry.key for entry in payload]
        self.assertLess(keys.index("set_country_flag"), keys.index("RLY"))
        self.assertLess(keys.index("RLY"), keys.index("RUS_crisis_check_start"))

    def test_imperial_defeat_restores_frontiers_without_taking_neutral_land(self):
        decision = self.crisis_decision("RUS_crisis_establish_special_zone")
        targets = {entry.value for entry in self.block(decision, "targets")}
        self.assertTrue({"TMR", "VEL", "RLY"} <= targets)
        for target in ("TMR", "VEL", "RLY"):
            for survived in (False, True):
                with self.subTest(target=target, survived=survived):
                    world = RusCrisisFixture()
                    world.owners["frontier"] = "RUS"
                    world.controllers["frontier"] = "RUS"
                    world.cores["frontier"] = {target}
                    world.owners["neutral_frontier"] = target if survived else "WKR"
                    world.controllers["neutral_frontier"] = world.owners["neutral_frontier"]
                    world.cores["neutral_frontier"] = {target}
                    if survived:
                        world.subjects[target] = "WKR"
                    world.capitulated.add("RUS")
                    world.run("RUS_crisis_resolve_capitulation")
                    self.assertEqual(world.owners["frontier"], target)
                    self.assertEqual(world.controllers["frontier"], target)
                    self.assertEqual(world.owners["neutral_frontier"], target if survived else "WKR")
                    self.assertEqual("RUS_crisis_fragment" in world.flags[target], not survived)
                    self.assertEqual(world.subjects.get(target), "WKR" if survived else None)

    def test_frontier_war_rejects_invalid_target_and_active_hegemon_campaign(self):
        decision = self.crisis_decision("RUS_imperial_frontier_campaign")
        for invalid in ("border", "subject", "faction", "capitulated", "wrong_tag", "rus_war", "unproclaimed", 1, 2, 4):
            with self.subTest(invalid=invalid):
                world = self.frontier_world("TMR")
                if invalid == "border":
                    world.neighbours.clear()
                elif invalid == "subject":
                    world.subjects["TMR"] = "VAL"
                elif invalid == "faction":
                    world.factions["TMR"] = "league"
                elif invalid == "capitulated":
                    world.capitulated.add("TMR")
                elif invalid == "wrong_tag":
                    world.from_country = "WKR"
                    world.neighbours.add(frozenset(("RUS", "WKR")))
                elif invalid == "rus_war":
                    world.wars.add(frozenset(("RUS", "WKR")))
                elif invalid == "unproclaimed":
                    world.flags["RUS"].clear()
                else:
                    world.variables["RUS", "RUS_crisis_phase"] = invalid
                self.assertFalse(world.matches(self.block(decision, "available"), ["RUS"]))
                before = set(world.wars)
                world.execute(self.block(decision, "complete_effect"), ["RUS"])
                self.assertEqual(world.wars, before)
                self.assertFalse(world.released_minors)
        for phase in (3, 5):
            world = self.frontier_world("TMR")
            world.variables["RUS", "RUS_crisis_phase"] = phase
            self.assertFalse(world.matches(self.block(decision, "available"), ["RUS"]))

    def test_mission_timeout_starts_war_without_responding_to_events(self):
        world = RusCrisisFixture()
        world.run("RUS_crisis_clear_roster")
        world.variables["RUS", "RUS_crisis_phase"] = 1
        world.wars.clear()
        world.factions = {"VAL": "league", "NOD": "league"}
        self.complete_hegemon_victory(world, "VAL")
        world.outside_predicates["RUS", "RUS_khan_governing"] = True
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

    def test_living_or_liberated_ally_blocks_final_annexation(self):
        world = RusCrisisFixture()
        world.capitulated.add("VAL")
        world.run("RUS_crisis_resolve_capitulation")
        self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 2)
        self.assertFalse(world.annexed)
        world.capitulated.add("NOD")
        world.controllers.update({"168": "RUS", "10": "RUS"})
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
        world.controllers.update({"168": "RUS", "10": "RUS"})
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
        world.controllers.update({"168": "RUS", "10": "RUS"})
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
        forms = ("RUS_last_empire", "RUS_black_banner_empire", "RUS_restoration_state")
        ruler = "RUS_Mark_Rustan"
        for hegemon in ("VAL", "STS", "STP"):
            for course, cosmetic in enumerate(forms, 1):
                with self.subTest(hegemon=hegemon, cosmetic=cosmetic):
                    world = RusCrisisFixture(hegemon, ruler, cosmetic)
                    world.capitulated.add("RUS")
                    world.run("RUS_crisis_resolve_capitulation")
                    self.assertEqual(world.variables["RUS", "RUS_crisis_phase"], 4)
                    self.assertEqual(world.variables[hegemon, "RUS_crisis_defeated_course"], course)
                    self.assertNotIn("RUS", world.owners.values())
                    self.assertEqual(world.retired, [ruler])
                    self.assertNotIn("RUS", world.rulers)
                    self.assertNotIn("RUS", world.power_balances)
                    self.assertFalse(world.dynamic_modifiers)
                    self.assertEqual(world.owners["66"], "SLA")
                    self.assertEqual(world.owners["330"], "IRT")
                    self.assertEqual(world.owners["168"], "VAL")
                    self.assertEqual(world.owners["40"], "WKR")
                    self.assertIn("RUS_crisis_settlement_rights", world.flags[hegemon])
                    other = "STS" if hegemon == "VAL" else "VAL"
                    self.assertNotIn("RUS_crisis_settlement_rights", world.flags[other])
                    self.assertNotIn((other, "RUS_crisis_defeated_course"), world.variables)
                    self.assertFalse(world.subjects)
                    for tag in ("SLA", "RZA", "MLR", "ERT", "IRT", "SCA"):
                        self.assertIn("RUS_crisis_fragment", world.flags[tag])
                    snapshot = dict(world.owners), list(world.retired), list(world.events)
                    world.run("RUS_crisis_resolve_capitulation")
                    self.assertEqual((world.owners, world.retired, world.events), snapshot)

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
        for hegemon in ("VAL", "STS", "STP"):
            world = RusCrisisFixture(hegemon)
            world.capitulated.add("RUS")
            world.run("RUS_crisis_resolve_capitulation")
            world.root = hegemon
            world.from_country = "MLR"
            if hegemon == "VAL":
                self.assertFalse(world.matches(self.block(decision, "available"), [hegemon]))
                world.completed_focuses.add(("VAL", "VAL_nw_zones"))
            self.assertTrue(world.matches(self.block(decision, "available"), [hegemon]))
            world.execute(self.block(decision, "complete_effect"), [hegemon])
            self.assertEqual(world.subjects, {"MLR": hegemon})
            self.assertEqual(world.autonomy["MLR"], "autonomy_vorkerland_sanitary_gate")
            world.subjects.clear()
            self.assertFalse(world.matches(self.block(decision, "visible"), [hegemon]))
            world.execute(self.block(decision, "complete_effect"), [hegemon])
            self.assertFalse(world.subjects)

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
            from tools.lib.paths import source_section
            source = source_section(read(path), "rus_crisis_l_" + language)
            source = source.split("\n", 1)[1]
            if language == "russian":
                self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            lines = [line for line in source.splitlines() if line.strip()]
            for line in lines:
                self.assertRegex(line, r'^ [A-Za-z0-9_.]+:(?:\d+)? "(?:[^"\\]|\\.)*"$')
                rendered = line.split('"', 1)[1].rsplit('"', 1)[0].replace("\\n", "\n")
                self.assertLessEqual(len(rendered), 3000)
                self.assertLessEqual(len(rendered.encode("utf-8")), 5500)
            self.assertNotIn("§Y", source.split(" ADISCORD_rus_crisis.1.d:", 1)[1])


class RusWorldEndingPresentationContracts(unittest.TestCase):
    def setUp(self):
        from tools.tests.test_adiscord_stp_preparation import block, entries, scalar, walk

        self.block = block
        self.entries = entries
        self.scalar = scalar
        self.walk = walk

    def named_block(self, items, kind, name):
        found = [row.value for row in items if row.key == kind and self.scalar(row.value, "name") == name]
        self.assertEqual(len(found), 1, name)
        return found[0]

    def test_native_ending_buttons_and_fullscreen_backdrop_are_loadable(self):
        gui = self.block(self.entries("interface/ADISCORD_RUS.gui"), "guiTypes")
        windows = {
            self.scalar(row.value, "name"): row.value
            for row in gui
            if row.key == "containerWindowType"
        }
        ending = windows["RUS_crisis_epilogue_window"]
        self.assertEqual(self.scalar(self.block(ending, "size"), "width"), "100%")
        self.assertEqual(self.scalar(self.block(ending, "size"), "height"), "100%")
        self.assertEqual(
            self.scalar(self.block(ending, "background"), "quadTextureSprite"),
            "GFX_RUS_world_ended_screen",
        )
        for name in ("RUS_crisis_strike_window", "RUS_crisis_epilogue_window"):
            buttons = [row.value for row in self.walk(windows[name]) if row.key == "buttonType"]
            self.assertTrue(buttons)
            for button in buttons:
                self.assertEqual({row.key for row in self.block(button, "size")}, {"x", "y"})
                self.assertEqual(self.scalar(button, "quadTextureSprite"), "GFX_RUS_bunker_button")
            containers = [windows[name]] + [
                row.value for row in self.walk(windows[name]) if row.key == "containerWindowType"
            ]
            self.assertTrue(all("alwaystransparent" not in {row.key for row in container} for container in containers))

    def test_epilogue_button_enters_its_viewport_only_after_impact(self):
        from tools.assets.source.build_rus_crisis_audio import IMPACT_START, STRIKE_DURATION

        gui = self.block(self.entries("interface/ADISCORD_RUS.gui"), "guiTypes")
        strike = self.named_block(gui, "containerWindowType", "RUS_crisis_strike_window")
        viewport = self.named_block(strike, "containerWindowType", "epilogue_button_viewport")
        reveal = self.named_block(viewport, "containerWindowType", "epilogue_button_reveal")
        button = self.named_block(reveal, "buttonType", "epilogue_next")
        self.assertEqual(self.scalar(viewport, "clipping"), "yes")
        self.assertEqual(self.scalar(reveal, "show_animation_type"), "linear")
        self.assertFalse([row for row in self.walk(button) if row.key == "shortcut"])

        duration = float(self.scalar(reveal, "animation_time")) / 1000
        start_y = float(self.scalar(self.block(reveal, "position"), "y"))
        end_y = float(self.scalar(self.block(reveal, "show_position"), "y"))
        button_y = float(self.scalar(self.block(button, "position"), "y"))
        height = float(self.scalar(self.block(viewport, "size"), "height"))
        self.assertGreater(start_y + button_y, height)
        self.assertGreater(start_y, end_y)
        first_visible = duration * (start_y + button_y - height) / (start_y - end_y)
        self.assertGreater(first_visible, IMPACT_START + 1)
        self.assertLess(first_visible, duration)
        self.assertLess(duration, STRIKE_DURATION)
        self.assertGreaterEqual(end_y + button_y, 0)
        self.assertLessEqual(
            end_y + button_y + float(self.scalar(self.block(button, "size"), "y")),
            height,
        )

    def test_ending_audio_runs_once_per_scene_not_per_story_page(self):
        gui = self.block(self.entries("interface/ADISCORD_RUS.gui"), "guiTypes")
        windows = {
            self.scalar(row.value, "name"): row.value
            for row in gui
            if row.key == "containerWindowType"
        }
        self.assertFalse([row for row in self.walk(windows["RUS_crisis_strike_window"]) if row.key == "show_sound"])
        sounds = [row.value for row in self.walk(windows["RUS_crisis_epilogue_window"]) if row.key == "show_sound"]
        self.assertEqual(sounds, ["ADISCORD_rus_ruined_world"])

        entities = self.entries("gfx/entities/mapitems_custom.asset")
        actor = self.named_block(entities, "entity", "ADISCORD_orbital_laser_strike_entity")
        state = self.named_block(actor, "state", "strike")
        cues = [row.value for row in state if row.key == "event" and any(child.key == "sound" for child in row.value)]
        self.assertEqual(len(cues), 2)
        effects = self.entries("sound/assets_adiscord_soundeffects.asset")
        samples = self.entries("sound/assets_adiscord_sounds.asset")
        for cue, phase, seconds in zip(cues, ("charge", "impact"), (0, 10)):
            self.assertEqual(float(self.scalar(cue, "time")), seconds)
            self.assertEqual(self.scalar(cue, "trigger_once"), "yes")
            sound = self.scalar(self.block(cue, "sound"), "soundeffect")
            self.assertEqual(sound, f"ADISCORD_rus_reactor_{phase}")
            effect = self.named_block(effects, "soundeffect", sound)
            self.assertEqual(self.scalar(effect, "is3d"), "no")
            self.assertEqual(self.scalar(effect, "loop"), "no")
            sample_name = self.scalar(self.block(effect, "sounds"), "sound")
            sample = self.named_block(samples, "sound", sample_name)
            self.assertEqual(self.scalar(sample, "always_load"), "yes")
            self.assertTrue((ROOT / "sound" / self.scalar(sample, "file")).is_file())
        self.assertEqual(self.scalar(cues[1], "particle"), "ADISCORD_orbital_laser_impact_particle")

    def test_ending_uses_registered_ship_archetypes_and_cosmetic_colours(self):
        effects = self.entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt")
        cleanup = self.block(effects, "RUS_crisis_destroy_country_assets")
        ship_types = {self.scalar(row.value, "type") for row in cleanup if row.key == "destroy_ships"}
        equipment = self.block(self.entries("common/units/equipment/ADISCORD_convoy_equipment.txt"), "equipments")
        naval_archetypes = {
            row.key for row in equipment
            if isinstance(row.value, list) and any(child.key == "is_archetype" and child.value == "yes" for child in row.value) and row.key != "convoy"
        }
        self.assertEqual(ship_types, naval_archetypes)
        cosmetics = self.entries("common/countries/cosmetic.txt")
        country_colours = self.entries("common/countries/colors.txt")
        for tag in ("RUS_world_anarchy", "RUS_last_bunker"):
            self.assertEqual(len([row for row in cosmetics if row.key == tag]), 1)
            self.assertFalse([row for row in country_colours if row.key == tag])

    def test_ending_has_no_technical_progress_or_pause_instructions(self):
        gui = self.block(self.entries("interface/ADISCORD_RUS.gui"), "guiTypes")
        for window in (row.value for row in gui if row.key == "containerWindowType" and self.scalar(row.value, "name") in ("RUS_crisis_strike_window", "RUS_crisis_epilogue_window")):
            labels = [row.value for row in self.walk(window) if row.key == "text"]
            self.assertFalse([label for label in labels if any(word in label.lower() for word in ("progress", "remaining", "wave_status"))])
        for language in ("russian", "english"):
            source = read(ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml")
            ending = {key: value for key, value in localisation_entries(source).items() if key.startswith(("RUS_crisis_strike_", "RUS_crisis_epilogue_"))}
            self.assertFalse([text for text in ending.values() if any(token in text.lower() for token in ("снять паузу", "на паузе", "space to", "game time", "world_state_queue"))])

    def test_strike_audio_peak_and_particle_share_the_slow_charge_timeline(self):
        import wave
        import numpy as np
        from tools.assets.source.build_rus_crisis_audio import BEAM_START, IMPACT_START, STRIKE_DURATION, AFTERMATH_SILENCE

        particles = self.entries("gfx/particles/environment/ADISCORD_orbital_laser_strike.asset")
        strike = self.named_block(particles, "particle", "ADISCORD_orbital_laser_strike_file")
        systems = {self.scalar(row.value, "name"): row.value for row in strike if row.key == "subsystem"}
        for name in ("beam_core_primer", "beam_halo_primer"):
            self.assertEqual(float(self.scalar(systems[name], "start")), BEAM_START)
        for name in ("beam_core", "beam_halo"):
            self.assertEqual(float(self.scalar(systems[name], "start")), BEAM_START + 1.5)
            self.assertEqual(float(self.scalar(systems[name], "start")) + float(self.scalar(systems[name], "duration")), IMPACT_START)
        impact = self.named_block(particles, "particle", "ADISCORD_orbital_laser_impact_file")
        systems = {self.scalar(row.value, "name"): row.value for row in impact if row.key == "subsystem"}
        for name in ("det_flash", "det_fireball", "det_debris"):
            self.assertEqual(float(self.scalar(systems[name], "start")), 0)
        segments = []
        for phase, duration in (("charge", IMPACT_START), ("impact", STRIKE_DURATION - IMPACT_START)):
            with wave.open(str(ROOT / f"sound/RUS/ADISCORD_rus_reactor_{phase}.wav"), "rb") as cue:
                self.assertEqual((cue.getnchannels(), cue.getsampwidth(), cue.getframerate()), (2, 2, 44100))
                self.assertEqual(cue.getnframes() / cue.getframerate(), duration)
                segments.append(np.frombuffer(cue.readframes(cue.getnframes()), dtype="<i2").reshape(-1, 2).astype(float))
        samples = np.concatenate(segments)
        loudest = np.max(np.abs(samples), axis=1).argmax() / 44100
        self.assertLess(abs(loudest - IMPACT_START), 0.1)
        rms = [np.sqrt(np.mean(samples[second * 44100:(second + 1) * 44100] ** 2)) for second in (0, 2, 4, 6, 8)]
        self.assertEqual(rms, sorted(rms))
        self.assertEqual(STRIKE_DURATION + AFTERMATH_SILENCE, 326)

    def test_ending_screens_have_no_technical_progress_or_pause_instructions(self):
        for relative in (
            "interface/ADISCORD_RUS.gui",
            "common/scripted_guis/ADISCORD_RUS_scripted_gui.txt",
            "common/scripted_localisation/ADISCORD_RUS_scripted_loc.txt",
            "localisation/russian/ADISCORD_vorkerland_l_russian.yml",
            "localisation/english/ADISCORD_vorkerland_l_english.yml",
        ):
            source = read(ROOT / relative)
            for token in (
                "GetRUSWorldDestructionStatus",
                "world_destruction_progress",
                "RUS_crisis_ruins_progress",
                "RUS_crisis_ruins_complete",
            ):
                self.assertNotIn(token, source, relative)

    def test_reactor_fire_has_separate_persistent_ignitions_across_the_site(self):
        from tools.assets.source.build_rus_crisis_audio import IMPACT_START, STRIKE_DURATION

        actor = self.named_block(self.entries("gfx/entities/mapitems_custom.asset"), "entity", "ADISCORD_orbital_laser_strike_entity")
        self.assertEqual(self.scalar(actor, "default_state"), "spent")
        self.assertFalse([row for row in self.named_block(actor, "state", "spent") if row.key == "event"])
        strike = self.named_block(actor, "state", "strike")
        self.assertEqual(self.scalar(strike, "next_state"), "burn")
        self.assertEqual(float(self.scalar(strike, "state_time")), STRIKE_DURATION)
        burning = self.named_block(actor, "state", "burn")
        self.assertFalse([row for row in burning if row.key == "next_state"])
        self.assertEqual(self.scalar(burning, "looping"), "no")
        fires = [row.value for row in burning if row.key == "event" and self.scalar(row.value, "particle") == "ADISCORD_orbital_laser_fire_particle"]
        ignitions = [row.value for row in strike if row.key == "event" and self.scalar(row.value, "particle") == "ADISCORD_orbital_laser_fire_particle"]
        self.assertEqual(len(fires), 5)
        self.assertEqual(len(ignitions), 5)
        locators = {self.scalar(row.value, "name") for row in actor if row.key == "locator"}
        nodes = {self.scalar(fire, "node") for fire in fires}
        self.assertEqual(len(nodes), 5)
        self.assertTrue(nodes <= locators)
        self.assertEqual({self.scalar(fire, "node") for fire in ignitions}, nodes)
        for ignition in ignitions:
            self.assertGreater(float(self.scalar(ignition, "time")), IMPACT_START)
            self.assertLess(float(self.scalar(ignition, "time")), IMPACT_START + 1)
            self.assertEqual(self.scalar(ignition, "keep_particle"), "no")
            self.assertEqual(self.scalar(ignition, "trigger_once"), "yes")
        for fire in fires:
            self.assertEqual(float(self.scalar(fire, "time")), 0)
            self.assertEqual(self.scalar(fire, "keep_particle"), "yes")
            self.assertEqual(self.scalar(fire, "trigger_once"), "yes")
            self.assertFalse([row for row in fire if row.key == "sound"])
        definitions = self.block(self.entries("gfx/entities/particles_custom.gfx"), "objectTypes")
        binding = self.named_block(definitions, "pdxparticle", "ADISCORD_orbital_laser_fire_particle")
        self.assertEqual(self.scalar(binding, "type"), "ADISCORD_orbital_laser_fire_file")
        self.assertEqual(self.scalar(binding, "scale"), "1")
        particle = self.named_block(self.entries("gfx/particles/environment/ADISCORD_orbital_laser_strike.asset"), "particle", self.scalar(binding, "type"))
        systems = [row.value for row in particle if row.key == "subsystem"]
        self.assertEqual({self.scalar(system, "name") for system in systems}, {"fire", "bright_fire", "flare", "smoke"})
        for system in systems:
            self.assertLessEqual(float(self.scalar(system, "start")), 0.1)
        self.assertTrue(all(float(self.scalar(system, "duration")) == -1 for system in systems))
        self.assertTrue(all(float(self.scalar(system, "emission")) > 0 for system in systems))
        textures = {self.scalar(self.block(system, "texture"), "file") for system in systems}
        self.assertIn("gfx/particles/fire_08.dds", textures)
        self.assertLessEqual(sum(int(self.scalar(system, "max_amount")) for system in systems) * len(fires), 270)
        self.assertLessEqual(sum(float(self.scalar(system, "emission")) for system in systems) * len(fires), 76)
        for source in (EFFECT_FILE, ROOT / "events/ADISCORD_scenario_debug_events.txt"):
            self.assertNotIn("ADISCORD_orbital_laser_aftermath_entity", read(source))

    def test_reactor_cloud_column_rises_once_into_a_persistent_canopy(self):
        from tools.assets.source.build_rus_crisis_audio import IMPACT_START

        actor = self.named_block(self.entries("gfx/entities/mapitems_custom.asset"), "entity", "ADISCORD_orbital_laser_strike_entity")
        columns = [
            (state_name, row.value)
            for state_name in ("strike", "burn", "spent")
            for row in self.named_block(actor, "state", state_name)
            if row.key == "event" and self.scalar(row.value, "particle") == "ADISCORD_orbital_laser_column_particle"
        ]
        self.assertEqual([state_name for state_name, _ in columns], ["strike"])
        column = columns[0][1]
        self.assertEqual(self.scalar(column, "node"), "impact")
        self.assertGreater(float(self.scalar(column, "time")), IMPACT_START)
        self.assertEqual(self.scalar(column, "keep_particle"), "yes")
        self.assertEqual(self.scalar(column, "trigger_once"), "yes")
        definitions = self.block(self.entries("gfx/entities/particles_custom.gfx"), "objectTypes")
        binding = self.named_block(definitions, "pdxparticle", "ADISCORD_orbital_laser_column_particle")
        particle = self.named_block(self.entries("gfx/particles/environment/ADISCORD_orbital_laser_strike.asset"), "particle", self.scalar(binding, "type"))
        systems = {self.scalar(row.value, "name"): row.value for row in particle if row.key == "subsystem"}
        self.assertEqual(set(systems), {"column_stem", "column_cap", "column_glow"})
        self.assertTrue(all(float(self.scalar(system, "duration")) == -1 for system in systems.values()))
        def base(system, name):
            return float(self.block(system, name)[0].value.split(",")[0])

        def height(system):
            return float(self.scalar(self.block(system, "position"), "y"))

        stem = systems["column_stem"]
        cap = systems["column_cap"]
        self.assertLess(abs(height(stem) + base(stem, "velocity") * base(stem, "life") - height(cap)), 10)
        self.assertLessEqual(height(cap) + base(cap, "size"), float(self.scalar(actor, "cull_radius")))
        self.assertLessEqual(sum(int(self.scalar(system, "max_amount")) for system in systems.values()), 60)

    def test_world_ash_veil_covers_the_map_and_thickens_after_the_strike(self):
        from PIL import Image
        from tools.assets.source.build_rus_crisis_audio import IMPACT_START

        actor = self.named_block(self.entries("gfx/entities/mapitems_custom.asset"), "entity", "ADISCORD_orbital_laser_world_ash_entity")
        veil = self.named_block(actor, "state", self.scalar(actor, "default_state"))
        events = [row.value for row in veil if row.key == "event"]
        self.assertEqual([self.scalar(event, "particle") for event in events], ["ADISCORD_orbital_laser_world_ash_particle"])
        self.assertEqual(self.scalar(events[0], "keep_particle"), "yes")
        definitions = self.block(self.entries("gfx/entities/particles_custom.gfx"), "objectTypes")
        binding = self.named_block(definitions, "pdxparticle", "ADISCORD_orbital_laser_world_ash_particle")
        self.assertEqual(self.scalar(binding, "scale"), "1")
        particle = self.named_block(self.entries("gfx/particles/environment/ADISCORD_orbital_laser_strike.asset"), "particle", self.scalar(binding, "type"))
        layers = [row.value for row in particle if row.key == "subsystem"]
        starts = [float(self.scalar(layer, "start")) for layer in layers]
        self.assertEqual(len(layers), 3)
        self.assertEqual(starts, sorted(starts))
        self.assertGreater(starts[0], IMPACT_START)
        self.assertTrue(all(float(self.scalar(row.value, "start")) == 0 for row in particle if row.key == "animation"))
        self.assertLessEqual(sum(int(self.scalar(layer, "max_amount")) for layer in layers), 150)
        centre_x, centre_y = (float(value) for value in ORBITAL_ACTOR_POSITIONS["ADISCORD_orbital_laser_world_ash_entity"])
        with Image.open(ROOT / "map/provinces.bmp") as provinces:
            width, height = provinces.size
        self.assertEqual((centre_x, centre_y), (width / 2, height / 2))
        self.assertGreaterEqual(float(self.scalar(actor, "cull_radius")), (width ** 2 + height ** 2) ** 0.5 / 2)
        for layer in layers:
            self.assertEqual(float(self.scalar(layer, "duration")), -1)
            self.assertEqual(self.scalar(layer, "local_space"), "no")
            self.assertEqual(float(self.block(layer, "box_emitter_x")[1].value), width / 2)
            self.assertEqual(float(self.block(layer, "box_emitter_z")[1].value), height / 2)

    def test_debug_laser_does_not_cancel_real_time_scene_after_one_game_hour(self):
        events = self.entries("events/ADISCORD_scenario_debug_events.txt")
        launch = next(row.value for row in events if row.key == "country_event" and self.scalar(row.value, "id") == "ADISCORD_orbital_laser_test.1")
        actors = [row.value for row in self.walk(launch) if row.key == "create_entity"]
        self.assertTrue(actors)
        self.assertTrue(all(self.scalar(actor, "z") == "0" for actor in actors))
        self.assertEqual([self.scalar(actor, "entity") for actor in actors], list(ORBITAL_ACTOR_POSITIONS))
        self.assertTrue(all(ORBITAL_ACTOR_POSITIONS[self.scalar(actor, "entity")] == (self.scalar(actor, "x"), self.scalar(actor, "y")) for actor in actors))
        self.assertEqual(self.scalar(self.block(launch, "immediate"), "goto_province"), "5228")
        self.assertFalse([row for row in self.walk(launch) if row.key == "country_event"])
        self.assertFalse([row for row in events if row.key == "country_event" and self.scalar(row.value, "id") == "ADISCORD_orbital_laser_test.2"])

    def test_ending_cosmetic_colours_use_the_native_cosmetic_registry(self):
        colours = self.entries("common/countries/colors.txt")
        cosmetics = self.entries("common/countries/cosmetic.txt")
        for tag in ("RUS_world_anarchy", "RUS_last_bunker"):
            self.assertNotIn(tag, {row.key for row in colours})
            self.assertEqual(len([row for row in cosmetics if row.key == tag]), 1)

    def test_orbital_visibility_covers_camera_range_without_replaying_the_strike(self):
        from math import sqrt
        from PIL import Image

        entities = {
            self.scalar(row.value, "name"): row.value
            for row in self.entries("gfx/entities/mapitems_custom.asset")
            if row.key == "entity"
        }
        strike = entities["ADISCORD_orbital_laser_strike_entity"]
        self.assertEqual(self.scalar(strike, "default_state"), "spent")
        strike_state = next(
            row.value for row in strike
            if row.key == "state" and self.scalar(row.value, "name") == "strike"
        )
        self.assertEqual(self.scalar(strike_state, "looping"), "no")
        self.assertEqual(self.scalar(strike_state, "next_state"), "burn")
        self.assertTrue(all(self.scalar(row.value, "trigger_once") == "yes" for row in strike_state if row.key == "event"))
        scene = self.block(self.entries("common/scripted_effects/ADISCORD_vorkerland_effects.txt"), "RUS_crisis_play_strike")
        actors = [row.value for row in self.block(scene, "125") if row.key == "create_entity"]
        defines = read(ROOT / "common/defines/ADISCORD_defines_changes.lua")
        camera_height = float(re.search(r"CAMERA_MAX_HEIGHT\s*=\s*([0-9.]+)", defines).group(1))
        mesh = next(
            row.value for row in self.walk(self.entries("gfx/entities/mapitems_custom.gfx"))
            if row.key == "pdxmesh" and self.scalar(row.value, "name") == "ADISCORD_orbital_laser_mesh"
        )
        self.assertGreater(float(self.scalar(mesh, "cull_distance")), camera_height)
        with Image.open(ROOT / "map/provinces.bmp") as provinces:
            map_diagonal = sqrt(provinces.width ** 2 + provinces.height ** 2 + camera_height ** 2)
        self.assertGreater(float(self.scalar(mesh, "cull_distance")), map_diagonal)
        for actor in actors:
            self.assertGreater(float(self.scalar(actor, "min_zoom")), camera_height)
            self.assertEqual(self.scalar(actor, "scale"), "1")
            entity = entities[self.scalar(actor, "entity")]
            self.assertGreaterEqual(float(self.scalar(entity, "cull_radius")), 620)

    def test_ruined_world_uses_a_real_opaque_screen_and_localised_surviving_bunker(self):
        from PIL import Image

        with Image.open(ROOT / "gfx/interface/ADISCORD_RUS/world_ended_screen.png") as screen:
            self.assertGreaterEqual(screen.width, 1600)
            self.assertGreaterEqual(screen.height, 900)
            self.assertEqual(screen.mode, "RGB")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_vorkerland_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            entries = localisation_entries(read(path))
            for key in ("RUS_world_anarchy", "RUS_last_bunker", "RUS_crisis_epilogue_5_body"):
                self.assertTrue(entries.get(key))
        self.assertIn("Хан жив", localisation_entries(read(RUSSIAN_LOC))["RUS_crisis_epilogue_5_body"])


if __name__ == "__main__":
    unittest.main()
