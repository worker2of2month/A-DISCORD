"""Preserve the merged UI/layout pass and add the independent tested gameplay changes."""
import ast
import io
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

BASE='457a8e2732363b61b3e0a5ac0a6de690e05887ee'
FEATURE='4e42badfb80941237d7667f7673116495673c6b4'
NAMES=['tools.tests.test_adiscord_stp_party_route','tools.tests.test_adiscord_stp_party_survival','tools.tests.test_adiscord_stp_party_balance','tools.tests.test_adiscord_stp_preparation','tools.tests.test_adiscord_stp_civil_war']
D='common/decisions/ADISCORD_STP_decisions.txt'
F='common/national_focus/ADISCORD_national_focus_STP.txt'
E='common/scripted_effects/ADISCORD_STP_scripted_effects.txt'
P='tools/tests/test_adiscord_stp_party_qol.py'
OUT=Path('/tmp/stp-party-integration-evidence'); OUT.mkdir(exist_ok=True)

def source(ref,path): return subprocess.check_output(['git','show',ref+':'+path]).decode('utf-8-sig')
def read(path): return Path(path).read_text(encoding='utf-8-sig')
def write(path,text):
    bom=Path(path).exists() and Path(path).read_bytes().startswith(b'\xef\xbb\xbf')
    Path(path).write_text(text,encoding='utf-8-sig' if bom else 'utf-8',newline='')
def spans(text,name):
    clean=re.sub(r'"(?:[^"\\]|\\.)*"|#[^\n]*',lambda m: ''.join('\n' if c=='\n' else ' ' for c in m.group()),text)
    results=[]
    for m in re.finditer(r'\b'+re.escape(name)+r'\s*=\s*\{',clean):
        depth=1; end=m.end()
        while depth:
            assert end<len(clean),name
            depth+=(clean[end]=='{')-(clean[end]=='}');end+=1
        results.append((m.start(),end))
    return results

def section(text,name,focus=False):
    found=spans(text,'focus' if focus else name)
    if focus: found=[(a,b) for a,b in found if re.match(r'focus\s*=\s*\{\s*id\s*=\s*'+re.escape(name)+r'\b',text[a:b])]
    assert len(found)==1,(name,len(found))
    return found[0]

def replace_section(text,name,value,focus=False):
    a,b=section(text,name,focus);return text[:a]+value+text[b:]

def suite_report(label):
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(NAMES))
    data={'tests':result.testsRun,'failures':{str(t):trace for t,trace in result.failures},'errors':{str(t):trace for t,trace in result.errors}}
    (OUT/(label+'.json')).write_text(json.dumps(data))
    print(label,json.dumps({'tests':data['tests'],'failures':len(data['failures']),'errors':len(data['errors'])}),flush=True)
    return data

if sys.argv[1]=='baseline':
    suite_report('baseline');sys.exit(0)
if sys.argv[1]=='updated':
    after=suite_report('updated');before=json.loads((OUT/'baseline.json').read_text());new={}
    for kind in ('failures','errors'):
        for name,trace in after[kind].items():
            if name not in before['failures'] and name not in before['errors']: new[name]=trace
    print('NEW_REGRESSIONS',json.dumps(new),flush=True)
    assert not new
    sys.exit(0)

assert sys.argv[1]=='apply'
# These focus/effect blocks were not changed by the parallel UI work.
focus_ids=('STP_GUARANTEE_MINISTERS','STP_ROTATE_DISTRICT_COMMAND','STP_cw_security_collegium','STP_cw_capital_oath','STP_ps_operational_reserve','STP_ps_route_security','STP_party_war_directorate','STP_ps_counter_supply')
for path,names,is_focus in ((F,focus_ids,True),(E,('STP_ps_refund_nod','STP_ps_deliver_nod'),False)):
    text=read(path);base=source(BASE,path);feature=source(FEATURE,path)
    for name in names:
        a,b=section(text,name,is_focus);c,d=section(base,name,is_focus);e,f=section(feature,name,is_focus)
        assert text[a:b]==base[c:d], 'Concurrent gameplay change requires review: '+name
        text=replace_section(text,name,feature[e:f],is_focus)
    write(path,text)

# Retain the new main timing gates and public tooltips, adding only duplicate-payment guards.
text=read(D)
for name,marker in (('STP_ps_val_intelligence','STP_ps_val_known_sequence'),('STP_ps_val_intercept','STP_ps_val_intercepted_sequence')):
    a,b=section(text,name);action=text[a:b]
    gate='VAL = { NOT = { check_variable = { var = '+marker+' value = STP_ps_val_sequence compare = equals } } }'
    for part in ('available','complete_effect'):
        c,d=section(action,part);payload=action[c:d]
        if part=='available': payload=payload[:-1]+'\n            '+gate+'\n        }'
        else:
            limits=spans(payload,'limit');assert limits
            e,f=limits[0];payload=payload[:f-1]+' '+gate+' '+payload[f-1:]
        action=action[:c]+payload+action[d:]
    text=text[:a]+action+text[b:]
a,b=section(text,'STP_ps_val_pressure');action=text[a:b]
assert action.count('activate_mission = STP_ps_val_pressure_work')==1
action=action.replace('activate_mission = STP_ps_val_pressure_work','STP_ps_val_pressure_finish = yes')
text=text[:a]+action+text[b:]
write(D,text)

# Keep main's compact UI wording; replace only descriptions for the additional gameplay.
keys=('STP_ps_operational_reserve_desc','STP_ps_route_security_desc','STP_ps_counter_supply_desc','STP_ps_counter_supply_current_tt','STP_ps_policy_faction_4_tt','STP_ps_policy_faction_3_tt','STP_ps_val_pressure_desc','STP_ps_val_pressure_result_tt','STP_ps_fund_nod_desc','STP_ps_arm_nod_desc','STP_ps_engineers_nod_desc','STP_ps_expedition_nod_desc')
for language in ('russian','english'):
    path=f'localisation/{language}/ADISCORD_STP_l_{language}.yml';text=read(path);feature=source(FEATURE,path)
    for key in keys:
        pattern=r'^ '+re.escape(key)+r':\d*[^\n]*$'
        lines=re.findall(pattern,feature,re.M);assert len(lines)==1,key
        if re.search(pattern,text,re.M): text=re.sub(pattern,lambda _: lines[0],text,flags=re.M)
        else: text=text.rstrip()+'\n'+lines[0]+'\n'
    write(path,text)

# Retain all main UI/layout tests and carry the seven independent gameplay regressions.
keep={'test_duplicate_recon_and_interception_cannot_charge_again','test_nod_stale_delivery_refunds_instead_of_consuming_the_order','test_nod_refund_accepts_transit_and_is_idempotent','test_war_policy_is_a_real_choice_without_blocking_the_directorate','test_four_faction_focuses_do_not_also_reward_every_faction','test_counter_supply_focus_identifies_a_real_current_cargo','test_pressure_affects_the_current_shipment_on_purchase'}
test=source(FEATURE,P);lines=test.splitlines(keepends=True);tree=ast.parse(test);remove=[]
for cls in tree.body:
    if isinstance(cls,ast.ClassDef):
        for node in cls.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name.startswith('test_') and node.name not in keep:
                remove.append((node.lineno-1,node.end_lineno))
for a,b in sorted(remove,reverse=True): del lines[a:b]
write(P,''.join(lines))
assert len([n for c in ast.parse(read(P)).body if isinstance(c,ast.ClassDef) for n in c.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')])==7

# Whitespace-only cleanup on changed lines; preserve other authors' content.
import difflib
for path in (D,F,E):
    before=source('origin/main',path).splitlines(keepends=True);after=read(path).splitlines(keepends=True)
    for op,_,__,a,b in difflib.SequenceMatcher(a=before,b=after,autojunk=False).get_opcodes():
        if op in ('insert','replace'):
            for i in range(a,b):after[i]=after[i].rstrip()+ ('\n' if after[i].endswith('\n') else '')
    write(path,''.join(after));parse_clausewitz(read(path))
print('INTEGRATED: preserve main categories, timing predicates, deferred layout refresh and tests; add faction choices, duplicate protection, immediate pressure and transit refunds',flush=True)
