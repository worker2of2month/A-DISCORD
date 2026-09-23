"""Ownership and native callback order for the shared scripted-peace bus."""
from pathlib import Path
import re
import unittest
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / 'common/on_actions'
SHARED = DIRECTORY / '09_ADISCORD_scripted_peace_on_actions.txt'
GENERIC = DIRECTORY / 'ZZ_ADISCORD_default_capitulation_on_actions.txt'
ORDER = {
    'on_capitulation_immediate': ['stelander', 'kefreyt', 'frontier', 'northern_reservation'],
    'on_capitulation': ['vorkerland_collapse', 'stelander', 'kefreyt', 'frontier', 'rin', 'nam', 'vorkerland_diplomacy', 'northern_reservation', 'livonn'],
    'on_peace': ['vorkerland_collapse', 'rin', 'vorkerland_diplomacy', 'kefreyt', 'stelander'],
    'on_peaceconference_ended': ['stelander', 'kefreyt'],
    'on_annex': ['stelander', 'kefreyt'],
    'on_state_control_changed': ['livonn', 'frontier'],
    }

def native_hooks(source):
    roots = [e.value for e in parse_clausewitz(source) if e.key == 'on_actions']
    if len(roots) != 1:
        raise AssertionError('Expected exactly one on_actions root')
    return roots[0]

class ScriptedPeaceOwnershipTests(unittest.TestCase):
    def source(self):
        self.assertTrue(SHARED.is_file(), 'Scripted peace has no shared owner')
        return SHARED.read_text(encoding='utf-8')

    def test_one_definition_for_each_shared_native_hook(self):
        names = [e.key for e in native_hooks(self.source())]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), set(ORDER))

    def test_country_sections_preserve_dispatch_order(self):
        source = self.source()
        for hook, expected in ORDER.items():
            with self.subTest(hook=hook):
                actual = re.findall(r'(?m)^\s*# BEGIN ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                ends = re.findall(r'(?m)^\s*# END ([a-z_]+):' + re.escape(hook) + r'\s*$', source)
                self.assertEqual(actual, expected)
                self.assertEqual(ends, expected)

    def test_capitulation_has_no_remaining_country_owner(self):
        self.source()
        for path in DIRECTORY.glob('*.txt'):
            if path in (SHARED, GENERIC):
                continue
            names = {e.key for e in native_hooks(path.read_text(encoding='utf-8-sig'))}
            self.assertFalse(names & {'on_capitulation', 'on_capitulation_immediate', 'on_peaceconference_ended'}, path.name)

    def test_generic_fallback_is_separate_and_last(self):
        self.source()
        self.assertTrue(GENERIC.is_file())
        self.assertLess(SHARED.name, GENERIC.name)
        generic = GENERIC.read_text(encoding='utf-8')
        self.assertIn('NOT = { has_global_flag = skip_default_capitulation }', generic)
        self.assertIn('clr_global_flag = skip_default_capitulation', generic)

    def test_obsolete_guard_and_livonn_files_are_removed(self):
        self.source()
        for name in ('04_ADISCORD_STP_northern_capitulation_guard_on_actions.txt', '09_ADISCORD_VAL_livonn_settlement_on_actions.txt'):
            self.assertFalse((DIRECTORY / name).exists(), name)

    def test_no_war_state_mirrors_or_global_periodic_scan(self):
        source = self.source()
        for flag in ('STP_pc_war_val', 'STP_pc_war_nod', 'STP_pc_war_with_sts'):
            self.assertNotIn(flag, source)
        names = {e.key for e in native_hooks(source)}
        self.assertNotIn('on_weekly', names)
        self.assertNotIn('on_daily', names)
        self.assertFalse(SHARED.read_bytes().startswith(b'\xef\xbb\xbf'))



class GenericPeaceFixture:
    """Execute the generic branch against explicit diplomacy/ownership facts.

    Native peace is deliberately allowed to remove ALL faction war relations.
    Annex can leave an impassable state behind. Neither model assumes engine
    callback timing, which still needs an in-game run.
    """
    def __init__(self, root="APH", survivor=None, neutral=True):
        self.root = root
        self.winner = "VAL"
        self.countries = ["CIN", "OSF", "APH", "VAL", "NOD", "ERT"]
        self.factions = {t: "tribes" for t in ("CIN", "OSF", "APH")}
        if neutral:
            self.factions["NOD"] = "tribes"
        self.wars = {frozenset(("VAL", t)) for t in ("CIN", "OSF", "APH", "ERT")}
        self.capitulated = {"CIN", "OSF", "APH"} - {survivor}
        self.owners = {58: "CIN", 61: "OSF", 64: "APH", 999: "APH", 70: "NOD", 168: "ERT"}
        self.arrays = {}
        self.flags = {t: set() for t in self.countries}
        self.global_flags = set()
        self.annexed = []
        self.log = []

    def resolve(self, token, stack):
        return {"THIS": stack[-1], "PREV": stack[-2] if len(stack) > 1 else None,
                "ROOT": self.root, "FROM": self.winner}.get(token, token)

    def allied(self, a, b):
        return a in self.factions and self.factions.get(a) == self.factions.get(b)

    def enemies(self, country):
        return {next(iter(w - {country})) for w in self.wars if country in w}

    def matches(self, rows, stack):
        from tools.tests.test_adiscord_stp_preparation import scalar
        current = stack[-1]
        def one(e):
            key, value = e.key, e.value
            if key in ("AND", "hidden_trigger"): return self.matches(value, stack)
            if key == "OR": return any(one(x) for x in value)
            if key == "NOT": return not any(one(x) for x in value)
            if key in ("ROOT", "FROM", "PREV"):
                return self.matches(value, stack + [self.resolve(key, stack)])
            if key == "any_other_country":
                return any(t != current and self.matches(value, stack + [t]) for t in self.countries)
            if key == "has_global_flag": return value in self.global_flags
            if key == "has_country_flag": return value in self.flags.get(current, set())
            if key == "is_in_faction": return (current in self.factions) == (value == "yes")
            if key == "is_in_faction_with": return self.allied(current, self.resolve(value, stack))
            if key == "has_capitulated": return (current in self.capitulated) == (value == "yes")
            if key == "has_war_with": return self.resolve(value, stack) in self.enemies(current)
            if key == "has_war_together_with": return bool(self.enemies(current) & self.enemies(self.resolve(value, stack)))
            if key in ("tag", "original_tag"): return current == self.resolve(value, stack)
            if key == "exists": return (current in self.countries) == (value == "yes")
            if key == "is_puppet_of": return False
            if key == "ADISCORD_vorkerland_is_main_claimant": return False
            raise AssertionError("Unsupported generic condition: " + key)
        return all(one(e) for e in rows)

    def execute(self, rows, stack=None):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        stack = stack or [self.root]
        current = stack[-1]
        taken = False
        for e in rows:
            key, value = e.key, e.value
            if key in ("if", "else_if", "else"):
                if key == "if": taken = False
                gate = next((x.value for x in value if x.key == "limit"), [])
                if not taken and self.matches(gate, stack):
                    taken = True
                    self.execute([x for x in value if x.key != "limit"], stack)
            elif key in ("ROOT", "FROM", "PREV"):
                self.execute(value, stack + [self.resolve(key, stack)])
            elif key == "every_enemy_country":
                # Recheck live enemy membership after each mutation, not a Python snapshot.
                for tag in self.countries:
                    if tag in self.enemies(current) and self.matches(block(value, "limit"), stack + [tag]):
                        self.execute([x for x in value if x.key != "limit"], stack + [tag])
            elif key == "every_owned_state":
                for state in list(self.owners):
                    if self.owners[state] == current:
                        self.execute(value, stack + [state])
            elif key == "add_to_temp_array":
                self.arrays.setdefault(scalar(value, "array"), []).append(self.resolve(scalar(value, "value"), stack))
            elif key == "clear_temp_array": self.arrays[value] = []
            elif key == "for_each_scope_loop":
                for scope in list(self.arrays[scalar(value, "array")]):
                    self.execute([x for x in value if x.key != "array"], stack + [scope])
            elif key == "white_peace":
                target = self.resolve(value, stack)
                defeated_side = {target} | {t for t in self.countries if self.allied(t, target)}
                self.wars = {w for w in self.wars if not (current in w and bool(w & defeated_side))}
                self.capitulated -= defeated_side
            elif key == "annex_country":
                target = self.resolve(scalar(value, "target"), stack)
                self.annexed.append(target)
                for state in list(self.owners):
                    if self.owners[state] == target and state != 999:
                        self.owners[state] = current
                # A faction leader may disappear during annexation.
                self.factions.pop(target, None)
            elif key == "transfer_state": self.owners[self.resolve(value, stack)] = current
            elif key == "clr_country_flag": self.flags[current].discard(value)
            elif key == "set_major": pass
            elif key == "log": self.log.append(value)
            else: raise AssertionError("Unsupported generic effect: " + key)

    def run(self):
        from tools.tests.test_adiscord_stp_preparation import block
        hook = block(native_hooks(GENERIC.read_text(encoding="utf-8")), "on_capitulation")
        self.execute([block(hook, "effect")[0]])


class GenericPeaceRegressionTests(unittest.TestCase):
    def test_neutral_faction_member_does_not_block_the_defeated_war(self):
        model = GenericPeaceFixture(neutral=True)
        model.run()
        self.assertEqual(set(model.annexed), {"CIN", "OSF", "APH"})
        self.assertEqual(model.owners[70], "NOD")

    def test_faction_wide_white_peace_cannot_skip_the_remaining_losers(self):
        from itertools import permutations
        for order in permutations(("CIN", "OSF", "APH")):
            with self.subTest(order=order):
                model = GenericPeaceFixture(root=order[-1], neutral=False)
                model.countries[:3] = order
                model.run()
                self.assertEqual(set(model.annexed), set(order))
                self.assertEqual({model.owners[n] for n in (58, 61, 64)}, {"VAL"})
                self.assertEqual(model.owners[168], "ERT", "Unrelated parallel wars must survive")
                self.assertIn(frozenset(("VAL", "ERT")), model.wars)

    def test_living_cobelligerent_and_liberation_block_final_peace(self):
        for tag in ("CIN", "OSF"):
            model = GenericPeaceFixture(survivor=tag)
            before = dict(model.owners), set(model.wars)
            model.run()
            self.assertFalse(model.annexed)
            self.assertEqual(before, (model.owners, model.wars))

    def test_full_annexation_includes_an_impassable_owned_remainder(self):
        model = GenericPeaceFixture(neutral=False)
        model.run()
        self.assertEqual(model.owners[999], "VAL")

    def test_scripted_root_reservation_prevents_generic_mutation(self):
        model = GenericPeaceFixture(neutral=False)
        model.global_flags.add("skip_default_capitulation")
        before = dict(model.owners), set(model.wars)
        model.run()
        self.assertEqual(before, (model.owners, model.wars))
        self.assertFalse(model.annexed)


class WarDebugContractTests(unittest.TestCase):
    def test_war_tools_are_debug_only_human_only_and_free(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        source = ROOT / "common/decisions/ADISCORD_scenario_debug_decisions.txt"
        category = block(parse_clausewitz(source.read_text(encoding="utf-8")), "ADISCORD_scenario_debug_category")
        decisions = [e for e in category if e.key.startswith("ADISCORD_debug_war_")]
        self.assertTrue({
            "ADISCORD_debug_war_log_on", "ADISCORD_debug_war_log_off",
            "ADISCORD_debug_war_snapshot", "ADISCORD_debug_war_val_start",
            "ADISCORD_debug_war_val_check", "ADISCORD_debug_war_val_abort",
            "ADISCORD_debug_war_reserves",
        }.issubset({e.key for e in decisions}))
        for e in decisions:
            with self.subTest(decision=e.key):
                visible = block(e.value, "visible")
                self.assertEqual(scalar(visible, "is_debug"), "yes")
                self.assertEqual(scalar(visible, "is_ai"), "no")
                self.assertEqual(scalar(e.value, "cost"), "0")
                self.assertEqual(scalar(block(e.value, "ai_will_do"), "factor"), "0")

    def test_debug_localisation_covers_each_new_control_in_both_languages(self):
        from tools.tests.test_adiscord_stp_preparation import block
        source = ROOT / "common/decisions/ADISCORD_scenario_debug_decisions.txt"
        category = block(parse_clausewitz(source.read_text(encoding="utf-8")), "ADISCORD_scenario_debug_category")
        controls = [e.key for e in category if e.key.startswith("ADISCORD_debug_war_")]
        self.assertTrue(controls)
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_scenario_debug_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in controls:
                for suffix in ("", "_desc"):
                    self.assertRegex(text, r"(?m)^ " + re.escape(key + suffix) + r":")



class FrontierWarEntryRegressionTests(unittest.TestCase):
    def effects(self):
        return parse_clausewitz((ROOT / "common/scripted_effects/ADISCORD_VAL_effects.txt").read_text())

    def test_war_entry_is_confirmed_after_the_declaration_effect_returns(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        start = block(self.effects(), "VAL_frontier_start_war")
        queued = [e for e in walk(start) if e.key == "country_event" and scalar(e.value, "id") == "val_rework.117"]
        self.assertEqual(len(queued), 1, "Native queued war entry needs a bounded confirmation")
        self.assertEqual(scalar(queued[0].value, "hours"), "1")
        hidden = [e for e in walk(start) if e.key == "hidden_effect"]
        self.assertTrue(any(queued[0] in e.value for e in hidden), "Technical confirmation must not announce an event in the reward")
        for e in walk(start):
            if e.key == "if" and any(x.key == "VAL_frontier_close" for x in e.value):
                self.fail("Do not cancel a just-issued declaration using same-tick has_war")

    def test_kefreyt_declares_on_all_enrolled_tribes_without_waiting_for_ai(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        effects = self.effects()
        start = block(effects, "VAL_frontier_start_war")
        helper_calls = [e for e in walk(start) if e.key == "VAL_frontier_declare_all_tribal_members"]
        self.assertEqual(len(helper_calls), 3, "Each tribal ultimatum branch must use the common simultaneous declaration helper")

        helper = block(effects, "VAL_frontier_declare_all_tribal_members")
        expected = {"CIN": "58", "OSF": "61", "APH": "64"}
        declarations = {}
        for entry in walk(helper):
            if entry.key != "declare_war_on":
                continue
            target = scalar(entry.value, "target")
            generator = block(entry.value, "generator")
            state = next((x.value for x in generator if x.key == "" and isinstance(x.value, str)), None)
            declarations[target] = state

        self.assertEqual(declarations, expected)

    def test_calling_an_ally_never_clears_its_membership_in_the_same_branch(self):
        from tools.tests.test_adiscord_stp_preparation import block, walk
        calls = block(self.effects(), "VAL_frontier_call_members")
        for tag in ("CIN", "OSF", "APH"):
            branches = block(calls, tag)
            addition = next(i for i, e in enumerate(branches) if any(x.key == "add_to_war" for x in walk([e])))
            self.assertEqual(branches[addition+1].key, "else_if", "War relation may be queued, not yet visible")

    def test_native_relation_callback_records_guarantors_that_join_later(self):
        source = (ROOT / "common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt").read_text()
        self.assertIn("VAL_frontier_register_war_participant = yes", source)
        from tools.tests.test_adiscord_stp_preparation import block, scalar, walk
        register = block(self.effects(), "VAL_frontier_register_war_participant")
        gate = block(block(register, "if"), "limit")
        self.assertEqual(scalar(gate, "has_war_with"), "VAL")
        self.assertTrue(any(e.key == "VAL_frontier_guarantor" or (e.key == "set_country_flag" and e.value == "VAL_frontier_guarantor") for e in walk(register)))

    def test_delayed_confirmation_is_bound_to_its_original_target(self):
        from tools.tests.test_adiscord_stp_preparation import block, scalar
        events = parse_clausewitz((ROOT / "events/ADISCORD_VAL_contract_events.txt").read_text())
        found = [e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "val_rework.117"]
        self.assertEqual(len(found), 1)
        self.assertEqual(scalar(found[0], "hidden"), "yes")
        self.assertEqual(scalar(found[0], "is_triggered_only"), "yes")
        gate = block(block(block(found[0], "immediate"), "if"), "limit")
        self.assertEqual(scalar(gate, "VAL_frontier_reply_is_current"), "yes")



class EventDrivenPeaceTests(unittest.TestCase):
    def test_settlement_recovery_has_no_periodic_caller(self):
        from tools.tests.test_adiscord_stp_preparation import walk
        forbidden = {"STP_cw_poll_northern_campaign", "STP_cw_check_union_wars_finished",
                     "VAL_cw_stage_livonn_settlement", "STP_cw_queue_peace_reconciliation",
                     "STP_cw_reconcile_scripted_peace"}
        for path in DIRECTORY.glob("*.txt"):
            for hook in native_hooks(path.read_text(encoding="utf-8-sig")):
                if hook.key.startswith(("on_daily", "on_weekly", "on_monthly", "on_yearly")):
                    self.assertFalse({e.key for e in walk(hook.value)} & forbidden, (path.name, hook.key))

    def test_deferred_recovery_is_one_shot_and_rechecks_live_results(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, scalar, walk, selected_effects
        events = entries("events/ADISCORD_STP_events.txt")
        event = next(e.value for e in events if e.key == "country_event" and scalar(e.value, "id") == "ADISCORD_STP_cw.206")
        self.assertEqual(scalar(event, "hidden"), "yes")
        self.assertEqual(scalar(event, "is_triggered_only"), "yes")
        self.assertEqual(scalar(block(event, "immediate"), "STP_cw_reconcile_scripted_peace"), "yes")
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        recovery = block(effects, "STP_cw_reconcile_scripted_peace")
        for key in ("country_event", "every_country", "every_possible_country", "STP_cw_queue_peace_reconciliation"):
            self.assertNotIn(key, {e.key for e in walk(recovery)})
        for tag in ("STP", "STS"):
            for won in (False, True):
                for postwar in (False, True):
                    for finished in (False, True):
                        facts = {(tag, "has_global_flag", "STP_cw_started"): True,
                                 (tag, "has_global_flag", "STP_cw_union_wars_finished"): finished,
                                 (tag, "has_country_flag", "STP_cw_won_union_battle"): won,
                                 (tag, "has_country_flag", "STP_cw_postwar"): postwar}
                        calls = [e.key for _, e in selected_effects(recovery, facts, tag)]
                        self.assertEqual("STP_cw_check_union_wars_finished" in calls, won and postwar and not finished)
        for status in (0, 1, 2, 3, 4):
            facts = {("NOD", "variable", "STP_cw_northern_campaign_status"): status}
            calls = [e.key for _, e in selected_effects(recovery, facts, "NOD")]
            self.assertEqual("STP_cw_poll_northern_campaign" in calls, status == 1)
        for staged, resolved in ((False, False), (True, False), (False, True)):
            facts = {("VAL", "has_country_flag", "VAL_cw_postwar"): True,
                     ("VAL", "has_country_flag", "VAL_cw_livonn_settlement_staged"): staged,
                     ("VAL", "has_country_flag", "VAL_cw_livonn_settlement_resolved"): resolved}
            calls = [e.key for _, e in selected_effects(recovery, facts, "VAL")]
            self.assertEqual("VAL_cw_stage_livonn_settlement" in calls, not staged and not resolved)

    def test_native_edges_cover_external_peace_annexation_and_control(self):
        from tools.tests.test_adiscord_stp_preparation import block, walk
        hooks = native_hooks(SHARED.read_text(encoding="utf-8"))
        for name in ("on_capitulation", "on_peace", "on_annex", "on_peaceconference_ended", "on_state_control_changed"):
            with self.subTest(hook=name):
                self.assertIn("STP_cw_queue_peace_reconciliation", {e.key for e in walk(block(hooks, name))})
        control = str([(e.key, e.value) for e in walk(block(hooks, "on_state_control_changed"))])
        for state in ("43", "44", "45", "88"):
            self.assertIn("'state', '" + state + "'", control)

    def test_scripted_winners_queue_after_their_final_state_writes(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk
        effects = entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt")
        for name in ("STP_cw_settle_union_victory", "STP_cw_settle_nod_victory", "VAL_cw_settle_republics"):
            rows = list(walk(block(effects, name)))
            queue = next(e.line for e in rows if e.key == "STP_cw_queue_peace_reconciliation")
            check = next(e.line for e in rows if e.key == "STP_cw_check_union_wars_finished")
            self.assertGreater(queue, check)

    def test_queue_requires_pending_work_and_a_surviving_host(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, scalar, selected_effects
        queue = block(entries("common/scripted_effects/ADISCORD_STP_scripted_effects.txt"), "STP_cw_queue_peace_reconciliation")
        for exists in (False, True):
            for status in (0, 1, 2, 3, 4):
                facts = {("NOD", "exists", "yes"): exists,
                         ("NOD", "variable", "STP_cw_northern_campaign_status"): status}
                chosen = list(selected_effects(queue, facts, "WRK"))
                calls = [e.value for _, e in chosen if e.key == "country_event"]
                self.assertTrue(all(scope == "NOD" for scope, e in chosen if e.key == "country_event"))
                self.assertEqual(any(e.key == "STP_cw_poll_northern_campaign" for _, e in chosen), not exists and status == 1)
                self.assertEqual(len(calls), int(exists and status == 1))
                if calls:
                    self.assertEqual(scalar(calls[0], "hours"), "1")
                    self.assertEqual(scalar(calls[0], "id"), "ADISCORD_STP_cw.206")

    def test_annex_and_capitulation_schedule_on_the_survivor(self):
        from dataclasses import replace
        from tools.tests.test_adiscord_stp_preparation import block, selected_effects
        hooks = native_hooks(SHARED.read_text(encoding="utf-8"))
        def scopes(rows, root, victor):
            return [replace(e, key={"ROOT": root, "FROM": victor}.get(e.key, e.key),
                            value=scopes(e.value, root, victor) if isinstance(e.value, list) else e.value)
                    for e in rows]
        # Read only this subsystem's last branch; other countries have separate handlers.
        annex = block(block(hooks, "on_annex"), "effect")
        for loser, expected in (("NOD", True), ("TFF", True), ("SRP", True), ("STP", True), ("RUS", False)):
            calls = [(scope, e.key) for scope, e in selected_effects(scopes(annex, "WRK", loser), {}, "WRK") if e.key == "STP_cw_queue_peace_reconciliation"]
            self.assertEqual(calls, [("WRK", "STP_cw_queue_peace_reconciliation")] if expected else [])
        from tools.lib.on_actions import read_scripted_peace
        country = native_hooks(read_scripted_peace(SHARED, "stelander"))
        late = block(block(country, "on_capitulation"), "effect")[-1:]
        calls = [(scope, e.key) for scope, e in selected_effects(scopes(late, "NOD", "WRK"), {}, "NOD")]
        self.assertEqual(calls, [("WRK", "STP_cw_queue_peace_reconciliation")])

    def test_authored_partial_peaces_notify_without_waiting_for_total_peace(self):
        from tools.tests.test_adiscord_stp_preparation import entries, block, walk
        for path, name in (
            ("common/scripted_effects/ADISCORD_TFF_effects.txt", "ADISCORD_TFF_become_nod_subject"),
            ("common/scripted_effects/ADISCORD_VAL_effects.txt", "VAL_transfer_yubora_administrations"),
        ):
            rows = list(walk(block(entries(path), name)))
            queue = next(e.line for e in rows if e.key == "STP_cw_queue_peace_reconciliation")
            self.assertGreater(queue, max(e.line for e in rows if e.key == "white_peace"))


if __name__ == '__main__':
    unittest.main()
