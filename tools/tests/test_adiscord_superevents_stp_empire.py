from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NEWS = ROOT / "events/ADISCORD_superevents.txt"
SUPEREVENTS = ROOT / "interface/superevents.gfx"
IMPERIAL_DECISIONS = ROOT / "common/decisions/ADISCORD_STP_decisions.txt"
IMPERIAL_TRIGGERS = ROOT / "common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt"
IMPERIAL_EFFECTS = ROOT / "common/scripted_effects/ADISCORD_STP_scripted_effects.txt"
WORKER_ART = ROOT / "gfx/interface/superevents/WRK/superevent_vorkerland_worker_victory.png"
DIRTY_OPENING_ART = ROOT / "gfx/interface/superevents/WRK/superevent_vorkerland_dirty_opening.png"
UTILITARIAN_ART = ROOT / "gfx/interface/superevents/WRK/superevent_vorkerland_utilitarian_victory.png"
VLAD_ART = ROOT / "gfx/interface/superevents/WRK/superevent_vorkerland_vlad_victory.png"

REQUIRED_IMPERIAL_STATES = (
    4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 24, 30, 31, 41, 42, 48, 54, 55, 56, 57,
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def event_block(text: str, event_id: str) -> str:
    marker = re.search(rf"(?:country|news)_event\s*=\s*\{{(?:(?!\n\}}).)*?\bid\s*=\s*{re.escape(event_id)}\b", text, re.S)
    if marker is None:
        raise AssertionError(f"missing event {event_id}")
    start = marker.start()
    brace = text.find("{", start)
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unterminated event {event_id}")


def named_block(text: str, name: str) -> str:
    marker = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if marker is None:
        raise AssertionError(f"missing block {name}")
    brace = text.find("{", marker.start())
    depth = 0
    for index in range(brace, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[marker.start() : index + 1]
    raise AssertionError(f"unterminated block {name}")


class SupereventAndImperialUnionTests(unittest.TestCase):
    def test_worker_victory_has_dedicated_art(self) -> None:
        gfx = read(SUPEREVENTS)
        self.assertIn(
            'name = "GFX_superevent_vorkerland_worker_victory"',
            gfx,
        )
        self.assertIn(
            'textureFile = "gfx/interface/superevents/WRK/superevent_vorkerland_worker_victory.png"',
            gfx,
        )
        self.assertTrue(WORKER_ART.is_file())

    def test_dirty_opening_and_utilitarian_victory_have_dedicated_art(self) -> None:
        gfx = read(SUPEREVENTS)
        self.assertIn(
            'textureFile = "gfx/interface/superevents/WRK/superevent_vorkerland_dirty_opening.png"',
            gfx,
        )
        self.assertIn(
            'textureFile = "gfx/interface/superevents/WRK/superevent_vorkerland_utilitarian_victory.png"',
            gfx,
        )
        self.assertTrue(DIRTY_OPENING_ART.is_file())
        self.assertTrue(UTILITARIAN_ART.is_file())

    def test_vlad_victory_has_dedicated_art(self) -> None:
        gfx = read(SUPEREVENTS)
        self.assertIn(
            'textureFile = "gfx/interface/superevents/WRK/superevent_vorkerland_vlad_victory.png"',
            gfx,
        )
        self.assertTrue(VLAD_ART.is_file())

    def test_civilwar_console_gateway_runs_the_real_outbreak(self) -> None:
        gateway = event_block(read(NEWS), "ADISCORD_superevent.1")
        self.assertIn("ADISCORD_vorkerland_collapse.1", gateway)
        self.assertIn("superevent_vorkerland_civilwar", gateway)

    def test_stelander_empire_news_is_presentation_only(self) -> None:
        empire = event_block(read(NEWS), "ADISCORD_superevent_news.2")
        for forbidden in (
            "transfer_state",
            "set_politics",
            "add_country_leader_role",
            "set_country_leader_portrait",
        ):
            self.assertNotIn(forbidden, empire)
        self.assertIn("superevent_stelander_empire", empire)
        self.assertIn("ADISCORD_superevent_enqueue = yes", empire)
        self.assertNotIn("limit = { is_ai = no }", empire)

    def test_shabrat_imperial_union_opens_after_kefreyt_defeat_only(self) -> None:
        decisions = named_block(read(IMPERIAL_DECISIONS), "STP_imperial_union_category")
        triggers = read(IMPERIAL_TRIGGERS)
        requirements = named_block(triggers, "STP_imperial_union_requirements_met")

        self.assertIn("STP_proclaim_imperial_union", decisions)
        self.assertIn("tag = STS", decisions)
        self.assertIn("STP_maksim_shabrat", decisions)
        self.assertIn("STP_imperial_union_kefreyt_defeated = yes", decisions)
        self.assertIn("STP_imperial_union_requirements_met = yes", decisions)

        # Kefreyt's defeat is the only campaign-progress gate.
        self.assertIn("STP_imperial_union_kefreyt_defeated = yes", requirements)
        self.assertNotIn("STP_imperial_union_nodrul_defeated", requirements)
        self.assertNotIn("STP_imperial_union_required_states_controlled", requirements)
        self.assertNotIn("STP_imperial_union_client_settlement", requirements)
        self.assertNotIn("has_completed_focus = STP_pc_hegemony_open", requirements)
        self.assertNotIn("STP_pc_founder_rules", requirements)
        self.assertNotIn("has_war = no", requirements)

        # The old full-map checklist must not hide or lock the proclamation.
        self.assertNotIn("highlight_state_targets", decisions)
        self.assertNotIn("has_completed_focus = STP_pc_hegemony_open", decisions)

    def test_postwar_victory_survives_settlement_cleanup(self) -> None:
        triggers = read(IMPERIAL_TRIGGERS)
        val = named_block(triggers, "STP_imperial_union_kefreyt_defeated")
        nod = named_block(triggers, "STP_imperial_union_nodrul_defeated")
        self.assertIn("has_idea = STP_pc_val_client", val)
        self.assertIn("has_idea = STP_pc_nod_client", nod)
        self.assertIn("STP_imperial_union_required_states_controlled = yes", val)
        self.assertIn("STP_imperial_union_required_states_controlled = yes", nod)
        self.assertIn("NOT = { has_war_with = VAL }", val)
        self.assertIn("NOT = { has_war_with = NOD }", nod)

    def test_imperial_union_effect_owns_state_change_not_news(self) -> None:
        effects = named_block(read(IMPERIAL_EFFECTS), "STP_proclaim_imperial_union")
        self.assertIn("STP_proclaim_imperial_union = {", effects)
        self.assertIn("set_cosmetic_tag = STP_empire", effects)
        self.assertIn("ruling_party = chauvinism", effects)
        self.assertIn("character = STP_maksim_shabrat", effects)
        self.assertIn("news_event = { id = ADISCORD_superevent_news.2 }", effects)
        self.assertNotIn("transfer_state", effects)

    def test_direct_proclamation_revalidates_requirements_and_is_idempotent(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, selected_effects
        source = parse_clausewitz(read(IMPERIAL_EFFECTS))
        effect = block(source, "STP_proclaim_imperial_union")
        for eligible in (False, True):
            facts = {("STS", "STP_imperial_union_requirements_met", "yes"): eligible}
            applied = list(selected_effects(effect, facts, "STS"))
            self.assertEqual(any(e.key == "news_event" for _, e in applied), eligible)
            self.assertEqual(any(e.key == "set_cosmetic_tag" for _, e in applied), eligible)
        requirements = block(parse_clausewitz(read(IMPERIAL_TRIGGERS)), "STP_imperial_union_requirements_met")
        self.assertTrue(any(e.key == "NOT" and any(c.key == "has_country_flag" and c.value == "STP_imperial_union_proclaimed" for c in e.value)
                            for e in requirements))

class SupereventObserverTests(unittest.TestCase):
    def machine(self, human=False):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz, scalar
        definitions = {e.key: e.value for e in parse_clausewitz(read(ROOT / 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'))}
        self.assertIn('ADISCORD_superevent_observer_tick', definitions)
        hooks = block(parse_clausewitz(read(ROOT / 'common/on_actions/00_ADISCORD_on_actions.txt')), 'on_actions')
        daily = block(block(hooks, 'on_daily'), 'effect')
        state = {'flags': {}, 'ttl': {}, 'queue': [], 'variables': {}, 'human': human, 'played': [], 'scans': 0}

        def number(value):
            if value == 'global.ADISCORD_superevent_queue^num':
                return len(state['queue'])
            if value == 'global.ADISCORD_superevent_queue^0':
                return state['queue'][0]
            return state['variables'][value] if value in state['variables'] else int(value)

        def condition(entry):
            key, value = entry.key, entry.value
            if key in ('AND', 'OR', 'NOT'):
                values = [condition(e) for e in value]
                return any(values) if key == 'OR' else not any(values) if key == 'NOT' else all(values)
            if key == 'has_global_flag':
                if isinstance(value, str):
                    return value in state['flags']
                flag = scalar(value, 'flag')
                comparison = [e.value for e in value if not e.key]
                self.assertEqual(comparison[:2], ['days', '>'])
                return flag in state['flags'] and state['flags'][flag] > int(comparison[2])
            if key == 'any_country':
                self.assertEqual([(e.key, e.value) for e in value], [('is_ai', 'no')])
                state['scans'] += 1
                return state['human']
            if key == 'is_in_array':
                return number(scalar(value, 'value')) in state['queue']
            if key == 'check_variable':
                fields = {e.key: e.value for e in value}
                if 'var' in fields:
                    left, right = number(fields['var']), number(fields['value'])
                    return {'greater_than': left > right, 'equals': left == right}[fields['compare']]
                variable, expected = next(iter(fields.items()))
                return number(variable) == number(expected)
            self.fail(f'Unhandled observer condition: {key}')

        def execute(body):
            taken = False
            for e in body:
                key, value = e.key, e.value
                if key in ('if', 'else_if', 'else'):
                    if key == 'if':
                        taken = False
                    if not taken and (key == 'else' or all(condition(c) for c in block(value, 'limit'))):
                        execute([c for c in value if c.key != 'limit'])
                        taken = True
                elif key == 'set_global_flag':
                    flag = value if isinstance(value, str) else scalar(value, 'flag')
                    state['flags'][flag] = 0
                    if isinstance(value, list):
                        state['ttl'][flag] = int(scalar(value, 'days'))
                elif key == 'clr_global_flag':
                    state['flags'].pop(value, None)
                    state['ttl'].pop(value, None)
                elif key == 'set_temp_variable':
                    for field in value:
                        state['variables'][field.key] = number(field.value)
                elif key == 'add_to_array':
                    state['queue'].append(number(scalar(value, 'value')))
                elif key == 'remove_from_array':
                    state['queue'].pop(number(scalar(value, 'index')))
                elif key == 'ADISCORD_vorkerland_play_superevent_sound':
                    active = [flag for flag in state['flags'] if flag.startswith('superevent_')]
                    self.assertEqual(len(active), 1)
                    state['played'].append(active[0])
                elif key in definitions and value == 'yes':
                    execute(definitions[key])
                else:
                    self.fail(f'Unhandled observer effect: {key}')

        def advance(days):
            for flag in list(state['flags']):
                state['flags'][flag] += days
                if flag in state['ttl'] and state['flags'][flag] >= state['ttl'][flag]:
                    state['flags'].pop(flag)
                    state['ttl'].pop(flag)

        def request(index):
            state['variables']['ADISCORD_superevent_request'] = index
            execute(definitions['ADISCORD_superevent_enqueue'])

        return state, execute, daily, advance, request

    def test_all_observer_cards_expire_on_day_seven_and_queue_gets_its_own_period(self):
        from tools.validators.validate_adiscord_superevents import PRESENTATIONS
        for index, presentation in enumerate(PRESENTATIONS, 1):
            with self.subTest(presentation=presentation.name):
                state, execute, daily, advance, request = self.machine()
                request(index)
                following = index % len(PRESENTATIONS) + 1
                request(following)
                request(following)
                self.assertEqual(state['queue'], [following])
                advance(6)
                execute(daily)
                self.assertIn(presentation.name, state['flags'])
                advance(1)
                execute(daily)
                self.assertNotIn(presentation.name, state['flags'])
                next_name = PRESENTATIONS[following - 1].name
                self.assertEqual(state['flags'][next_name], 0)
                self.assertEqual(state['queue'], [])
                scans = state['scans']
                execute(daily)
                self.assertEqual(state['scans'], scans)
                self.assertEqual(state['flags'][next_name], 0)
                advance(7)
                execute(daily)
                self.assertFalse(any(f.startswith('superevent_') for f in state['flags']))
                self.assertEqual(len(state['played']), 2)

    def test_human_campaigns_do_not_auto_close_and_switching_to_observer_recovers(self):
        state, execute, daily, advance, request = self.machine(human=True)
        request(1)
        request(2)
        advance(9)
        execute(daily)
        self.assertIn('superevent_vorkerland_civilwar', state['flags'])
        self.assertEqual(state['queue'], [2])
        scans = state['scans']
        for _ in range(10):
            execute(daily)
        self.assertEqual(state['scans'], scans)
        state['human'] = False
        advance(1)
        execute(daily)
        self.assertNotIn('superevent_vorkerland_civilwar', state['flags'])
        self.assertEqual(state['flags']['superevent_vorkerland_dirty_opening'], 0)

    def test_early_manual_close_and_legacy_stacked_flags_cannot_expire_a_fresh_card(self):
        from tools.tests.test_adiscord_stp_preparation import block, parse_clausewitz
        state, execute, daily, advance, request = self.machine()
        gui = block(parse_clausewitz(read(ROOT / 'common/scripted_guis/superevents.txt')), 'scripted_gui')
        window = block(gui, 'superevent_vorkerland_civilwar')
        request(1)
        request(2)
        advance(3)
        execute(block(block(window, 'effects'), 'superevents_button_click'))
        advance(4)
        execute(daily)
        self.assertEqual(state['flags']['superevent_vorkerland_dirty_opening'], 4)
        state['flags']['superevent_vorkerland_civilwar'] = 12
        advance(1)
        execute(daily)
        self.assertNotIn('superevent_vorkerland_civilwar', state['flags'])
        self.assertIn('superevent_vorkerland_dirty_opening', state['flags'])
        self.assertEqual(len(state['played']), 2)

    def test_daily_guard_precedes_the_only_country_scan_and_uses_no_delayed_country_owner(self):
        source = read(ROOT / 'common/on_actions/00_ADISCORD_on_actions.txt')
        self.assertIn('ADISCORD_superevent_observer_tick = yes', source)
        daily = named_block(source, 'on_daily')
        self.assertIn('NOT = { has_global_flag = ADISCORD_superevent_observer_day_checked }', daily)
        effect = named_block(read(ROOT / 'common/scripted_effects/ADISCORD_vorkerland_effects.txt'), 'ADISCORD_superevent_observer_tick')
        self.assertEqual(effect.count('any_country ='), 1)
        self.assertNotIn('every_country', effect)
        self.assertNotIn('country_event', effect)
        self.assertLess(effect.index('set_global_flag'), effect.index('any_country'))

if __name__ == "__main__":
    unittest.main()
