from pathlib import Path
import ast
import re
import sys
sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

def read(path):
    return Path(path).read_text(encoding='utf-8-sig')

def show_blocks(path, names):
    text=read(path)
    for name in names:
        match=re.search(r'(?m)^'+re.escape(name)+r'\s*=\s*\{', text)
        if not match:
            print('MISSING',path,name)
            continue
        start=text.index('{',match.start()); depth=0
        for pos in range(start,len(text)):
            depth += (text[pos]=='{') - (text[pos]=='}')
            if depth == 0:
                print('SOURCE',path,name,'LINE',text[:match.start()].count('\n')+1)
                print(text[match.start():pos+1]); break

p='tools/tests/test_adiscord_economy_weekly_contracts.py'
t=ast.parse(read(p))
print('RUNTIME_HELPERS')
for node in t.body:
    if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
        print(node.lineno,node.name)
        if isinstance(node,ast.ClassDef) and node.name != 'WeeklyEconomyContracts':
            print(ast.get_source_segment(read(p),node)[:19000])
show_blocks('common/scripted_effects/ADISCORD_economy_effects.txt',[
 'ADISCORD_economy_calculate_building_income','ADISCORD_economy_apply_development_income_multipliers',
 'ADISCORD_economy_light_update','ADISCORD_economy_calculate_treasury_cap','ADISCORD_economy_recount_economic_buildings',
 'ADISCORD_economy_update_ai_state'])
show_blocks('common/scripted_effects/ADISCORD_VAL_effects.txt',[
 'VAL_refresh_industrial_economy','VAL_advance_economic_recovery','VAL_refresh_contract_modifier',
 'VAL_invest_arsenal_industry','VAL_frontier_record_ultimatum'])
show_blocks('common/scripted_effects/ADISCORD_STP_scripted_effects.txt',[
 'STP_pw_refresh_modifier','STP_pw_initialize_variables'])
print('STP_ECONOMY_LOCALISATION')
for line in read('localisation/russian/ADISCORD_STP_l_russian.yml').splitlines():
    if re.match(r'\s*STP_pc_economy_',line): print(line)
print('STATE_TOTALS')
for tag in ['VAL','STP','STS','NOD','WRK','VAD']:
    selected=[]; totals={}
    for p in Path('history/states').glob('*.txt'):
        t=read(p)
        if re.search(r'\bowner\s*=\s*'+tag+r'\b',t):
            selected.append(p.name)
            for key in ['industrial_complex','arms_factory','dockyard','ADISCORD_business_center','ADISCORD_science_center','ADISCORD_industrial_cluster','manpower']:
                totals[key]=totals.get(key,0)+sum(float(v) for v in re.findall(r'\b'+key+r'\s*=\s*([\d.]+)',t))
    print(tag,totals,selected)
    for p in Path('history/countries').glob(tag+'*'):
        print(p,read(p)[:4000])
print('FOCUS_AI_PLANS')
for p in Path('common/ai_strategy_plans').glob('*.txt'):
    t=read(p)
    if 'VAL' in t: print(p,t[:16000])
print('FRONTIER_EVENT_RESPONSE')
for p in Path('events').glob('*VAL*'):
    t=read(p)
    for term in ['id = val_rework.110','id = val_rework.111','id = val_rework.112']:
        pos=t.find(term)
        if pos>=0: print(p,t[max(0,pos-25):pos+7500])
