from pathlib import Path
import re, sys
ROOT=Path.cwd()
STATES=(24,42,48,54,55,56,57)
def edit(name,fn):
 p=ROOT/name; raw=p.read_bytes(); bom=raw.startswith(b'\xef\xbb\xbf')
 p.write_bytes((b'\xef\xbb\xbf' if bom else b'')+fn(raw.decode('utf-8-sig')).encode('utf-8'))
def span(text,name):
 m=re.search(r'(?m)^\s*'+re.escape(name)+r'\s*=\s*\{',text); assert m,name
 start=text.index(name,m.start()); opening=text.index('{',start)
 depth=0; quoted=escaped=comment=False
 for i in range(opening,len(text)):
  c=text[i]
  if comment:
   if c=='\n':comment=False
   continue
  if quoted:
   if escaped:escaped=False
   elif c=='\\':escaped=True
   elif c=='"':quoted=False
   continue
  if c=='#':comment=True
  elif c=='"':quoted=True
  elif c=='{':depth+=1
  elif c=='}':
   depth-=1
   if depth==0:return start,i+1
 raise AssertionError(name)
def change(text,name,fn):
 a,b=span(text,name); return text[:a]+fn(text[a:b])+text[b:]
def triggers(text):
 gate='''# COUNTRY VAL: all seven home regions must be restored, not lost or occupied.
VAL_reclamation_complete = {
	has_completed_focus = VAL_reclamation_return_home
'''
 for state in STATES:
  gate+=f'''\t{state} = {{
		is_owned_by = VAL
		is_controlled_by = VAL
		check_variable = {{ var = VAL_reclamation_stage value = 3 compare = greater_than_or_equals }}
		NOT = {{
			has_dynamic_modifier = {{ modifier = ADISCORD_vorkerland_dirty_state }}
			has_dynamic_modifier = {{ modifier = VAL_reclamation_stage_1_modifier }}
			has_dynamic_modifier = {{ modifier = VAL_reclamation_stage_2_modifier }}
		}}
	}}
'''
 gate+='}\n\n'
 assert 'VAL_reclamation_complete = {' not in text
 pos=text.index('VAL_reclamation_industry_target_valid = {')
 text=text[:pos]+gate+text[pos:]
 return change(text,'VAL_frontier_postwar',lambda b:b.replace('    has_global_flag = STP_cw_union_wars_finished\n',''))
edit('common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt',triggers)
def effects(text):
 text=change(text,'VAL_reclamation_finish_state_project',lambda b:b.replace('VAL = { ADISCORD_economy_mark_dirty = yes }','VAL = { VAL_complete_reclamation = yes ADISCORD_economy_mark_dirty = yes }'))
 marker='# COUNTRY: only an outstanding receipt opens the fixed seven-state recovery pool.'
 assert marker in text
 return text.replace(marker,'''# COUNTRY VAL: the idea itself is the receipt; preserve the separate focus reward flag.
VAL_complete_reclamation = {
	if = {
		limit = { has_idea = VAL_harvest_of_ash VAL_reclamation_complete = yes }
		remove_ideas = VAL_harvest_of_ash
		ADISCORD_economy_mark_dirty = yes
	}
}

'''+marker)
edit('common/scripted_effects/ADISCORD_VAL_effects.txt',effects)
def actions(text):
 def startup(b):
  needle='\t\t\tif = {\n\t\t\t\tlimit = {\n\t\t\t\t\thas_global_flag = ADISCORD_fresh_campaign_contract_v1'
  assert needle in b
  return b.replace(needle,'\t\t\tVAL = { if = { limit = { exists = yes has_idea = VAL_harvest_of_ash } VAL_complete_reclamation = yes } }\n'+needle)
 return change(text,'on_startup',startup)
edit('common/on_actions/02_ADISCORD_VAL_rework_on_actions.txt',actions)
def focuses(text):
 ids={'VAL_frontier_conference','VAL_frontier_logistics','VAL_frontier_commissioners','VAL_frontier_provincial_offices','VAL_frontier_return_irem','VAL_frontier_security_plan','VAL_frontier_treaty_offices','VAL_New_Supply_Base','VAL_Northern_Settlement','VAL_Stelander_Ultimatum','VAL_Campaign_Secured','VAL_Reopen_Trade_Routes','VAL_Settle_Industrial_Debts','VAL_Return_To_World_Market','VAL_Veterans_Of_The_Campaign'}
 sys.path.insert(0,str(ROOT))
 from tools.tests.test_validate_adiscord_val_rework import named_block_spans
 blocks=named_block_spans(text,'focus')
 for f in reversed(blocks):
  b=f.text; id=re.search(r'\bid\s*=\s*(\w+)',b).group(1)
  if id in ids:
   b=re.sub(r'(?m)^(\s*x\s*=\s*)(-?\d+)',lambda m:m.group(1)+str(int(m.group(2))-8),b,count=1)
   b=re.sub(r'(?m)^(\s*y\s*=\s*)(-?\d+)',lambda m:m.group(1)+str(int(m.group(2))-2),b,count=1)
  if id in {'VAL_Occidian_Registries','VAL_Integrate_Occidia','VAL_Balchansk_Charter','VAL_Balchansk_Clearing_House'}:
   b=re.sub(r'(?m)^(\s*x\s*=\s*)(-?\d+)',lambda m:m.group(1)+str(int(m.group(2))+12),b,count=1)
  if id=='VAL_Bezhaysk_Operation':
   b=re.sub(r'(?m)^(\s*x\s*=\s*)20',r'\g<1>12',b,count=1)
  if id=='VAL_frontier_conference':
   old='prerequisite = { focus = VAL_The_Steel_Contract focus = VAL_Market_Roads_North }'
   assert old in b
   b=b.replace(old,'prerequisite = { focus = VAL_Contracts_Outlive_Kings focus = VAL_The_Steel_Contract focus = VAL_Market_Roads_North }')
  if id in {'VAL_frontier_conference','VAL_frontier_security_plan'}:
   b=b.replace('search_filters = {','search_filters = { FOCUS_FILTER_ANNEXATION',1)
  text=text[:f.start]+b+text[f.end:]
 return text.replace('# Postwar border policy. The three columns separate logistics, government and claims.','# Northern expansion. Logistics, administration and claims have independent columns.')
edit('common/national_focus/ADISCORD_national_focus_VAL.txt',focuses)
goals={
'russian':'Завершите все три этапа решений (дороги, очистка воды, возвращение жителей) во всех семи домашних регионах: '+', '.join(f'[{s}.GetName]' for s in STATES)+'. Когда все они принадлежат Кефрейту, контролируются им и полностью очищены, национальный дух §Y«$VAL_harvest_of_ash$»§! снимается автоматически. Одних фокусов недостаточно; дополнительные промышленные площадки не требуются.',
'english':'Complete all three decision stages (roads, water purification and resettlement) in all seven home regions: '+', '.join(f'[{s}.GetName]' for s in STATES)+'. Once Kefreyt owns and controls all seven fully restored regions, the §Y$VAL_harvest_of_ash$§! national spirit is removed automatically. Focuses alone are not enough; additional industrial-site projects are not required.'
}
texts={
'russian':{
'VAL_frontier_conference_desc':'Северная экспансия — самостоятельное направление внешней политики. Начните её через торговые дороги, стеландские договоры или единый государственный реестр. Завершения гражданской войны в Стеландере ждать не требуется.\\n\\nПуть к ультиматуму: «$VAL_frontier_logistics$» и одна из двух форм управления → «$VAL_frontier_security_plan$» → решение «$VAL_frontier_demand_CIN$» в категории «$VAL_frontier$». Отказ адресата откроет начало наступления. Для отправки ультиматума сам Кефрейт должен находиться в мире.',
'VAL_frontier_postwar_ready_tt':'Кефрейт независим, не капитулировал и не выведен из регионального противостояния условиями поражения. Завершение стеландской гражданской войны не требуется.',
},
'english':{
'VAL_frontier_conference_desc':'Northern expansion is an independent foreign-policy route. Enter it through the northern trade roads, Stelander contracts or the unified state ledger. There is no need to wait for the Stelander civil war to end.\\n\\nRoute to an ultimatum: $VAL_frontier_logistics$ and either administrative model → $VAL_frontier_security_plan$ → the $VAL_frontier_demand_CIN$ decision under $VAL_frontier$. A refusal unlocks the offensive. Kefreyt itself must be at peace to send an ultimatum.',
'VAL_frontier_postwar_ready_tt':'Kefreyt is independent, has not capitulated and is not barred from regional confrontation by its defeat settlement. The Stelander civil war does not have to end.',
}}
for lang in ('russian','english'):
 def loc(text,lang=lang):
  for key,value in texts[lang].items():
   text,count=re.subn(r'(?m)^\s*'+key+r':(?:\d+)?[^\n]*$',lambda m:f' {key}:0 "{value}"',text)
   assert count==1,(lang,key,count)
  for key in ('VAL_reclamation_desc','VAL_reclamation_settlement_result_tt'):
   pattern=r'(?m)^(\s*'+key+r':(?:\d+)?\s*"[^\n]*)"\s*$'
   text,count=re.subn(pattern,lambda m:m.group(1)+'\\n\\n$VAL_reclamation_completion_tt$"',text)
   assert count==1,(lang,key,count)
  assert 'VAL_reclamation_completion_tt:' not in text
  marker=re.search(r'(?m)^\s*VAL_reclamation_settlement_result_tt:[^\n]*$',text)
  return text[:marker.end()]+'\n VAL_reclamation_completion_tt:0 "'+goals[lang]+'"'+text[marker.end():]
 edit(f'localisation/{lang}/ADISCORD_VAL_decisions_l_{lang}.yml',loc)
 def spirit(text):
  pattern=r'(?m)^(\s*VAL_harvest_of_ash_desc:(?:\d+)?\s*"[^\n]*)"\s*$'
  text,n=re.subn(pattern,lambda m:m.group(1)+'\\n\\n$VAL_reclamation_completion_tt$"',text)
  assert n==1,n
  return text
 edit(f'localisation/{lang}/ADISCORD_ideas_l_{lang}.yml',spirit)
