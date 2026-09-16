from __future__ import annotations

from pathlib import Path
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
    return path.read_text(encoding="utf-8-sig")


def localisation_entries(text: str) -> dict[str, str]:
    return {
        match.group(1): match.group(2)
        for match in re.finditer(r'(?m)^\s+([A-Za-z0-9_]+):(?:\d+)?\s+"(.*)"\s*$', text)
    }


class RusLastEmpireTests(unittest.TestCase):
    def test_focus_tree_is_assigned_to_rus_and_lists_the_ai_branch(self) -> None:
        source = read(FOCUS_FILE)
        self.assertIn("id = RUS_focus", source)
        self.assertIn("original_tag = RUS", source)
        self.assertNotIn("declare_war_on", source)
        self.assertNotIn("create_faction =", source)
        for focus_id in RUS_FOCUS_IDS:
            self.assertIn(f"id = {focus_id}", source)
            self.assertIn("ai_will_do =", source[source.index(f"id = {focus_id}"):])
        self.assertIn("unlock_decision_tooltip = { decision = RUS_campaign_sla show_effect_tooltip = yes }", source)
        self.assertIn("unlock_decision_tooltip = { decision = RUS_proclaim_the_last_empire show_effect_tooltip = yes }", source)
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
        on_actions = read(ON_ACTIONS)
        self.assertIn("on_monthly_RUS", on_actions)
        self.assertIn("ADISCORD_vorkerland_check_rus_dirty_campaign = yes", on_actions)
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
            "rza": DIRTY_GROUPS["RZA"],
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

    def test_claimant_rewards_hide_dispatchers_and_preview_war_economy(self) -> None:
        focus = read(ROOT / "common/national_focus/ADISCORD_vorkerland_focus.txt")
        self.assertNotRegex(focus, r"(?m)^\t\t\tcountry_event =")
        self.assertIn("show_effect_tooltip = yes", focus)
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
        self.assertTrue(any(e.key == "annex_country" for _, e in settle))
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
        self.assertFalse(self.matches(still_open, waiting, "RUS"))
        self.assertFalse(self.matches(holds, waiting, "RUS"))
        check = self._run("ADISCORD_vorkerland_check_rus_dirty_campaign", waiting)
        self.assertNotIn("ADISCORD_vorkerland_rus_abort_dirty_campaign", self._calls(check))
        self.assertNotIn("ADISCORD_vorkerland_rus_settle_dirty_target", self._calls(check))

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

    def test_empire_gate_needs_held_land_not_vanished_tags(self) -> None:
        source = read(TRIGGER_FILE)
        start = source.index("ADISCORD_vorkerland_rus_has_empire_territory = {")
        body = source[start:source.index("\n}", start) + 2]
        self.assertIn("ADISCORD_vorkerland_rus_holds_sla_playable = yes", body)
        self.assertIn("ADISCORD_vorkerland_rus_holds_sca_playable = yes", body)
        self.assertNotIn("dirty_neighbors_taken", body)
        self.assertNotIn("country_exists", body)
        holds = self.expand(self.block(self.triggers, "ADISCORD_vorkerland_rus_holds_sla_playable"))
        self.assertTrue(self.matches(holds, self._hold_sla(True), "RUS"))
        self.assertFalse(self.matches(holds, self._hold_sla(False), "RUS"))


if __name__ == "__main__":
    unittest.main()
