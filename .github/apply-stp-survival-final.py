from pathlib import Path
import json
import re
import subprocess

BASE = '32a3c0ba2b118ade7730028173bdd9e068b808f8'
assert subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip() == BASE
E = 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
T = 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt'
D = 'common/decisions/ADISCORD_STP_decisions.txt'
EV = 'events/ADISCORD_STP_events.txt'

def read(path):
    return Path(path).read_text(encoding='utf-8-sig')

def save(path, text):
    Path(path).write_text(text, encoding='utf-8', newline='')

def endbrace(text, start):
    opening = text.index('{', start)
    depth = 0
    quote = comment = escape = False
    for i in range(opening, len(text)):
        c = text[i]
        if comment:
            if c == '\n': comment = False
            continue
        if quote:
            if escape: escape = False
            elif c == '\\': escape = True
            elif c == '"': quote = False
            continue
        if c == '#': comment = True
        elif c == '"': quote = True
        elif c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0: return i + 1
    raise AssertionError('unclosed block')

def edit(path, name, operation):
    text = read(path)
    hits = list(re.finditer(r'(?m)^[ \t]*' + re.escape(name) + r'\s*=\s*\{', text))
    assert len(hits) == 1, (path, name, len(hits))
    a = hits[0].start()
    b = endbrace(text, a)
    save(path, text[:a] + operation(text[a:b]) + text[b:])

def append(path, text):
    save(path, read(path).rstrip() + '\n\n' + text.strip() + '\n')

edit(T, 'STP_ps_nod_can_host_exiles', lambda b: b[:-1] + '\tany_owned_state = { is_controlled_by = PREV }\n}')
for name in ('STP_ps_accept_exile', 'STP_ps_settle_return'):
    edit(E, name, lambda b: b.replace('limit = { has_character = STP_rufus_hedersett }', 'limit = { has_character = STP_rufus_hedersett STP_rufus_hedersett = { NOT = { has_character_flag = STP_cw_arrested } } }'))

for name in ('STP_ps_clear_nod_receipt', 'STP_ps_clear_val_receipt'):
    edit(E, name, lambda b: re.sub(r'(?m)^\s*remove_mission = [^\n]+\n', '\n', b))
    edit(E, name, lambda b: re.sub(r'\n\s*\n(?:\s*\n)*\}', '\n}', b))
edit(E, 'STP_ps_clear_nod_receipt', lambda b: b.replace('{\n', '{\n\t# Timed callbacks consume the receipt; only external cancellation removes their missions.\n', 1))
edit(E, 'STP_ps_clear_val_receipt', lambda b: b.replace('{\n', '{\n\t# Receipt settlement is also called by the expiring departure and route-wait missions.\n', 1))

settle = 'VAL = { STP_ps_refund_val_supply = yes remove_mission = STP_ps_val_departure remove_mission = STP_ps_val_route_wait }'
edit(E, 'STP_cw_settle_union_victory', lambda b: b.replace('\n\tSTS = { STP_cw_remove_kefreyt_volunteers = yes }', '\n\t' + settle + '\n\tSTS = { STP_cw_remove_kefreyt_volunteers = yes }', 1))
edit(E, 'STP_cw_settle_nod_victory', lambda b: b.replace('\n\t\tSTP_cw_close_nod_after_party_victory = yes', '\n\t\t' + settle + '\n\t\tSTP_cw_close_nod_after_party_victory = yes', 1))
edit(E, 'STP_ps_prepare_exile', lambda b: b.replace('\n\t\tSTP_ps_deliver_nod = yes', '\n\t\tSTP_ps_deliver_nod = yes\n\t\tremove_mission = STP_ps_nod_dispatch\n\t\tremove_mission = STP_ps_nod_route_wait\n\t\tremove_mission = STP_ps_nod_delivery', 1))

for name, effect in [('STP_ps_nod_route_wait', 'STP_ps_dispatch_nod'), ('STP_ps_val_route_wait', 'STP_ps_dispatch_val_supply')]:
    edit(D, name, lambda b: b.replace('timeout_effect = { hidden_effect = { ' + effect + ' = yes } }', 'timeout_effect = { hidden_effect = { country_event = { id = ADISCORD_STP_cw.206 hours = 1 } } }'))
assert 'id = ADISCORD_STP_cw.206' not in read(EV)
append(EV, '''# Retry only after the timed mission has left the native decision update.
country_event = {
	id = ADISCORD_STP_cw.206
	hidden = yes
	is_triggered_only = yes
	immediate = {
		if = {
			limit = {
				tag = STP
				check_variable = { var = STP_ps_nod_receipt_stage value = 1 compare = equals }
				NOT = { has_active_mission = STP_ps_nod_dispatch }
				NOT = { has_active_mission = STP_ps_nod_route_wait }
				NOT = { has_active_mission = STP_ps_nod_delivery }
			}
			STP_ps_dispatch_nod = yes
		}
		else_if = {
			limit = {
				tag = VAL
				has_variable = STP_ps_val_receipt_rifles
				check_variable = { var = STP_ps_val_receipt_stage value = 1 compare = equals }
				NOT = { has_active_mission = STP_ps_val_departure }
				NOT = { has_active_mission = STP_ps_val_route_wait }
			}
			STP_ps_dispatch_val_supply = yes
		}
	}
}''')

edit(E, 'STP_ps_begin_return', lambda _: '''STP_ps_begin_return = {
	if = {
		limit = {
			tag = NOD
			has_country_flag = STP_ps_exile_received
			has_completed_focus = STP_ps_return_campaign_focus
			has_country_flag = STP_ps_return_terms_accepted
			has_country_flag = STP_ps_exile_training_completed
			STP_ps_nod_can_host_exiles = yes
			STP = { exists = no }
			STS = { exists = yes has_capitulated = no }
			NOT = { has_country_flag = STP_ps_return_closed }
			OR = {
				has_war_with = STS
				AND = { STS = { is_subject = no } NOT = { is_in_faction_with = STS } }
			}
		}
		if = { limit = { NOT = { has_war_with = STS } } declare_war_on = { target = STS type = annex_everything } }
		if = { limit = { has_war_with = STS } set_country_flag = STP_ps_return_campaign }
	}
}''')
edit(D, 'STP_ps_launch_return', lambda b: b.replace('STS = { exists = yes }', 'STS = { exists = yes has_capitulated = no } OR = { has_war_with = STS AND = { STS = { is_subject = no } NOT = { is_in_faction_with = STS } } }'))

path = 'tools/tests/test_adiscord_stp_party_survival.py'
text = read(path)
old = "('NOD', 'is_ai', 'yes'): ai}"
assert old in text
text = text.replace(old, "('NOD', 'is_ai', 'yes'): ai,\n                     ('NOD', 'owns_state', '17'): True, ('NOD', 'controls_state', '17'): True}")
save(path, text)
append(path, '''class PartySurvivalFinalIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = {e.key:e.value for e in parse_clausewitz(read(EFFECTS))}
        cls.triggers = {e.key:e.value for e in parse_clausewitz(read(TRIGGERS))}
        cls.decisions = {e.key:e.value for c in parse_clausewitz(read(DECISIONS)) for e in c.value if isinstance(e.value,list)}

    def test_host_requires_owned_controlled_land(self):
        host = self.triggers['STP_ps_nod_can_host_exiles']
        facts = {('NOD','tag','NOD'):True,('NOD','exists','yes'):True,('NOD','has_capitulated','no'):True,('NOD','is_subject','no'):True}
        self.assertFalse(matches_conditions(host,facts,'NOD'))
        facts[('NOD','owns_state','17')] = True
        self.assertFalse(matches_conditions(host,facts,'NOD'))
        facts[('NOD','controls_state','17')] = True
        self.assertTrue(matches_conditions(host,facts,'NOD'))

    def test_arrested_hedersett_is_not_evacuated_or_promoted(self):
        for name in ('STP_ps_accept_exile','STP_ps_settle_return'):
            blocks = [e.value for e in walk(self.effects[name]) if e.key == 'if'
                      and any(x.key == 'set_nationality' for x in e.value)]
            self.assertEqual(len(blocks),1,name)
            gate = one(blocks[0],'limit')
            character = one(gate,'STP_rufus_hedersett')
            self.assertEqual(one(one(character,'NOT'),'has_character_flag'),'STP_cw_arrested')

    def test_all_internal_war_settlements_refund_goods_before_the_buyer_is_deleted(self):
        for name in ('STP_cw_settle_union_victory','STP_cw_settle_nod_victory'):
            keys = [e.key for e in walk(self.effects[name])]
            self.assertIn('STP_ps_refund_val_supply',keys,name)
            self.assertLess(keys.index('STP_ps_refund_val_supply'),keys.index('annex_country'),name)

    def test_receipt_consumption_does_not_remove_a_running_mission(self):
        for name in ('STP_ps_clear_val_receipt','STP_ps_clear_nod_receipt'):
            self.assertNotIn('remove_mission',{e.key for e in walk(self.effects[name])},name)

    def test_unavailable_routes_retry_outside_the_expiring_mission(self):
        for mission in ('STP_ps_nod_route_wait','STP_ps_val_route_wait'):
            payload = one(one(self.decisions[mission],'timeout_effect'),'hidden_effect')
            queue = one(payload,'country_event')
            self.assertEqual(one(queue,'hours'),'1')
            self.assertEqual(one(queue,'id'),'ADISCORD_STP_cw.206')
        events = parse_clausewitz(read('events/ADISCORD_STP_events.txt'))
        retry = next(e.value for e in events if e.key == 'country_event' and one(e.value,'id') == 'ADISCORD_STP_cw.206')
        self.assertIn('has_active_mission',str(signature(one(retry,'immediate'))))

    def test_return_requires_a_real_hostile_war_relation(self):
        body = one(self.effects['STP_ps_begin_return'],'if')
        gate = one(body,'limit')
        self.assertIn('STP_ps_exile_training_completed',str(signature(gate)))
        self.assertIn('is_in_faction_with',str(signature(gate)))
        committed = next(e.value for e in body if e.key == 'if' and any(x.key == 'set_country_flag' and x.value == 'STP_ps_return_campaign' for x in e.value))
        self.assertEqual(one(one(committed,'limit'),'has_war_with'),'STS')
''')

path = 'tools/tests/test_adiscord_stp_party_balance.py'
text = read(path)
assert 'multiply_temp_variable' in text
text = text.replace('multiply_temp_variable\\s*=', 'multiply_(?:temp_)?variable\\s*=')
text = text.replace('self.assertTrue(coefficients)', 'self.assertEqual(len(coefficients), 7)')
save(path, text)
path = 'tools/data/adiscord_event_ids.json'
text = read(path)
assert 'ADISCORD_STP_cw.206' not in text
row = {'id':'ADISCORD_STP_cw.206', 'namespace':'ADISCORD_STP_cw', 'number':206, 'owner':EV, 'subsystem':'stp_civil_war', 'status':'active'}
save(path, text.replace('  "events": [', '  "events": [\n    ' + json.dumps(row) + ',', 1))
subprocess.run(['git', 'diff', '--check'], check=True)
expected = {
 'common/decisions/ADISCORD_STP_decisions.txt': 'b2036c66f53adcc5f43d9920e649bb1189716517434642c2382897f167fc2199',
 'common/scripted_effects/ADISCORD_STP_scripted_effects.txt': '55c6837576c60a88df4e91e095f6c471126a96fcd8a5dffd16bc2a0fca2c21e3',
 'common/scripted_triggers/ADISCORD_STP_scripted_triggers.txt': '84783b74d2abfd0d5689c2a3c9e5e437589a49e29a2dd0e22037d868a925e6af',
 'events/ADISCORD_STP_events.txt': '190b8233609c7690b389a274eef175f42fae3940be0c6f38e72183521ed8b991',
 'tools/data/adiscord_event_ids.json': '15ef2fa0124d3d30392e7ac639288a9d1fc8ad5c6deff9cbceb8bbf157f392f1',
 'tools/tests/test_adiscord_stp_party_balance.py': 'f866a82e15d5dbe1a682b8b95c9b322eb4e7967e6d342430b73101a225398f7f',
 'tools/tests/test_adiscord_stp_party_survival.py': 'f5e5fd8713c8317629327535d08f58129d80889a18f3bacd31841d3d9868228b'
}
import hashlib
actual = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in expected}
assert actual == expected, {name: (expected[name], actual[name]) for name in expected if actual[name] != expected[name]}
print('All seven source hashes match the locally reviewed candidate.')
