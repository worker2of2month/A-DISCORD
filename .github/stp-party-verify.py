"""Isolated workbench checks. This file is not part of the gameplay commit."""
import collections
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path.cwd()
OUT = Path('/tmp/party-result')
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))
ALLOWED = {
    'common/ai_strategy_plans/ADISCORD_STP_plans.txt',
    'common/decisions/ADISCORD_STP_decisions.txt',
    'common/dynamic_modifiers/ADISCORD_dynamic_modifiers_STP.txt',
    'common/ideas/ADISCORD_STP_civil_war_ideas.txt',
    'common/national_focus/ADISCORD_national_focus_STP.txt',
    'common/scripted_effects/ADISCORD_STP_scripted_effects.txt',
    'common/scripted_localisation/ADISCORD_STP_scripted_loc.txt',
    'docs/development/focus-effects.md',
    'docs/superpowers/plans/2026-09-19-stp-party-route.md',
    'events/ADISCORD_STP_events.txt',
    'localisation/russian/ADISCORD_STP_l_russian.yml',
    'tools/data/adiscord_event_ids.json',
    'tools/tests/test_adiscord_stp_civil_war.py',
    'tools/tests/test_adiscord_stp_party_route.py',
    'tools/tests/test_adiscord_stp_preparation.py',
}
CHANGED_FOCUSES = set('''STP_Govern_In_His_Name STP_PRESIDENT_REMAINS_IN_OFFICE STP_GUARANTEE_MINISTERS STP_PARTY_DISCIPLINE STP_defense_budget STP_ROTATE_DISTRICT_COMMAND STP_DISTRICT_GOVERNMENT STP_cw_capital_reserve STP_cw_protect_congress STP_EMERGENCY_PRESIDIUM STP_THE_PARTY_CLOSES_RANKS STP_cw_security_collegium STP_cw_counter_network STP_cw_protocol_office STP_cw_public_lists STP_cw_quiet_registers STP_cw_press_office STP_cw_capital_oath STP_cw_party_mandate STP_cw_congress_in_session STP_cw_guard_the_pier STP_cw_capital_counteroffensive STP_cw_inner_ring STP_cw_assault_columns STP_cw_harbour_batteries STP_pw_party_new_republic STP_pw_party_district_authority STP_pw_party_civil_records STP_pw_party_open_settlement STP_pw_party_firm_settlement STP_pw_party_civil_charter STP_pw_party_restore_roads STP_pw_party_homes_for_returnees STP_pw_party_civil_workshops STP_pw_party_accountable_arsenals STP_pw_party_industrial_settlement STP_pw_party_army_register STP_pw_party_officer_school STP_pw_party_supply_service STP_pw_party_professional_service STP_pw_party_settled_state STP_pw_party_northern_protocol STP_pw_party_protectorate STP_pw_party_sovereignty STP_pw_party_border_staff STP_pw_party_southern_defence'''.split())

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

def source_contract():
    from tools.validators.validate_adiscord_division_templates import parse_clausewitz
    def parsed(path):
        return parse_clausewitz(Path(path).read_text(encoding='utf-8-sig'))
    def signature(items):
        return [(e.key, signature(e.value) if isinstance(e.value,list) else e.value) for e in items]
    def digest(items):
        return hashlib.sha256(json.dumps(signature(items),ensure_ascii=False).encode()).hexdigest()
    focuses = {}
    for tree in parsed('common/national_focus/ADISCORD_national_focus_STP.txt'):
        if tree.key != 'focus_tree': continue
        for focus in tree.value:
            if focus.key == 'focus':
                fid = next(e.value for e in focus.value if e.key == 'id')
                focuses[fid] = digest(focus.value)
    plans = {e.key:digest(e.value) for e in parsed('common/ai_strategy_plans/ADISCORD_STP_plans.txt')}
    effects = {e.key:digest(e.value) for e in parsed('common/scripted_effects/ADISCORD_STP_scripted_effects.txt')}
    return {'focuses':focuses,'plans':plans,'effects':effects}

def snapshot(label):
    payload = {'head':git('rev-parse','HEAD'), 'source': source_contract()}
    suite = unittest.defaultTestLoader.discover('tools/tests', pattern='*stp*.py')
    with (OUT/f'{label}-tests.txt').open('w') as log:
        result = unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    payload['tests'] = {'count':result.testsRun, 'failed':[t.id() for t,_ in result.failures],
                        'errors':[t.id() for t,_ in result.errors], 'skipped':[t.id() for t,_ in result.skipped]}
    run = subprocess.run([sys.executable,'-B','tools/validate_tc.py','--limit','300'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    (OUT/f'{label}-validator.txt').write_text(run.stdout)
    payload['validator_exit'] = run.returncode
    sections = {}
    current = None
    for line in run.stdout.splitlines():
        m = re.match(r'^== (.+): (\d+) ==$',line)
        if m:
            current=m[1]; sections[current]={'total':int(m[2]),'issues':[]}
        elif line.startswith('== '):
            current=None
        elif current and line.startswith('- '):
            sections[current]['issues'].append(re.sub(r':\d+(?=:|\b)', ':LINE', line))
    payload['sections'] = sections
    payload['hashes'] = {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sorted(ALLOWED) if Path(p).is_file()}
    (OUT/f'{label}.json').write_text(json.dumps(payload,indent=2))
    print(json.dumps({'label':label,'tests':payload['tests'],'validator_exit':run.returncode}))

def gate():
    before=json.loads((OUT/'baseline.json').read_text())
    after=json.loads((OUT/'candidate.json').read_text())
    issues=[]
    for category in ('failed','errors','skipped'):
        extra=collections.Counter(after['tests'][category])-collections.Counter(before['tests'][category])
        issues += [f'New {category}: {name} x{n}' for name,n in extra.items()]
    if after['tests']['count'] < before['tests']['count'] + 19:
        issues.append('Expected at least nineteen additional party tests')
    for label, data in [('baseline',before),('candidate',after)]:
        if data['validator_exit'] != 0 or len(data['sections'])<20:
            issues.append(f'{label} validator did not complete')
    for name, data in after['sections'].items():
        old=before['sections'].get(name,{'total':0,'issues':[]})
        if data['total']>old['total']:
            issues.append(f'{name}: issue count increased {old["total"]} -> {data["total"]}')
        extra=collections.Counter(data['issues'])-collections.Counter(old['issues'])
        issues += [f'New validator finding in {name}: {v}' for v in extra]
    oldf=before['source']['focuses']; newf=after['source']['focuses']
    for fid, value in oldf.items():
        if fid not in newf: issues.append('Removed focus '+fid)
        elif fid not in CHANGED_FOCUSES and newf[fid]!=value: issues.append('Unrelated focus changed '+fid)
    if len(set(newf)-set(oldf)) != 18: issues.append('Expected eighteen new focuses')
    for fid in set(newf)-set(oldf):
        if not fid.startswith('STP_party_'): issues.append('Unexpected focus '+fid)
    for name,value in before['source']['plans'].items():
        if after['source']['plans'].get(name)!=value: issues.append('Existing AI plan changed '+name)
    for name,value in before['source']['effects'].items():
        if name!='STP_cw_apply_wartime_template_locks' and after['source']['effects'].get(name)!=value:
            issues.append('Unrelated scripted effect changed '+name)
    paths=set(git('diff','--name-only','HEAD').splitlines())
    if paths!=ALLOWED: issues.append('Unexpected changed path set: '+str(paths^ALLOWED))
    for p in paths:
        data=Path(p).read_bytes()
        if p.endswith('.yml') and not data.startswith(b'\xef\xbb\xbf'): issues.append('Missing localisation BOM '+p)
        if p.endswith('.txt') and data.startswith(b'\xef\xbb\xbf'): issues.append('Unexpected script BOM '+p)
    (OUT/'gate.json').write_text(json.dumps({'issues':issues,'changed_paths':sorted(paths),'baseline':before['tests'],'candidate':after['tests']},indent=2))
    print('\n'.join(issues) if issues else 'NO NEW STATIC REGRESSIONS')
    if issues: raise SystemExit(1)

if sys.argv[1]=='gate': gate()
else: snapshot(sys.argv[1])
