import pathlib, re, subprocess

focus_path='common/national_focus/ADISCORD_national_focus_STP.txt'
# Retain current-main changes outside the reviewed party focuses.
focus_text=subprocess.check_output(['git','show','HEAD:'+focus_path]).decode('utf-8')
def edit_focus(fid, transform):
 global focus_text
 pattern=re.compile(r'^\tfocus = \{\n\t\tid = '+re.escape(fid)+r'\n.*?^\t\}',re.M|re.S)
 match=pattern.search(focus_text)
 assert match is not None,fid
 old=match.group(0);new=transform(old)
 focus_text=focus_text[:match.start()]+new+focus_text[match.end():]

def northern(block):
 old='NOD = { STP_ps_nod_can_host_exiles = yes }'
 new='custom_trigger_tooltip = { tooltip = STP_ps_nod_agreement_ready_tt NOD = { STP_ps_nod_can_host_exiles = yes has_country_flag = STP_ps_aid_agreement } }'
 assert block.count(old)==1
 block=block.replace(old,new)
 fid=re.search(r'\bid = (\w+)',block).group(1)
 rivals={'STP_ps_northern_credit':'STP_ps_northern_arms','STP_ps_northern_arms':'STP_ps_northern_credit'}
 if fid in rivals:
  assert 'mutually_exclusive' not in block
  anchor='\t\tprerequisite = { focus = STP_ps_northern_partner }'
  assert block.count(anchor)==1
  block=block.replace(anchor,anchor+'\n\t\tmutually_exclusive = { focus = '+rivals[fid]+' }')
 return block
for fid in ('STP_ps_northern_credit','STP_ps_northern_arms','STP_ps_northern_engineers','STP_ps_joint_staff','STP_ps_expedition_logistics'):
 edit_focus(fid,northern)

def supply(block):
 replacement='\t\tcompletion_reward = { '+ ' '.join('unlock_decision_tooltip = { decision = '+key+' show_effect_tooltip = yes }' for key in ('STP_ps_val_intelligence','STP_ps_val_intercept','STP_ps_val_pressure'))+' }'
 block,n=re.subn(r'^\t\tcompletion_reward = \{.*\}$',replacement,block,flags=re.M)
 assert n==1
 return block
for fid in ('STP_ps_foreign_supply_desk','STP_ps_counter_supply'):
 edit_focus(fid,supply)
pathlib.Path(focus_path).write_bytes(focus_text.encode('utf-8'))

p=pathlib.Path('tools/tests/test_adiscord_stp_party_survival.py')
s=p.read_text()
old="unlocks=[e.value for e in one(focuses[fid],'completion_reward') if e.key=='unlock_decision_tooltip']"
new="unlocks=[one(e.value,'decision') if isinstance(e.value,list) else e.value for e in one(focuses[fid],'completion_reward') if e.key=='unlock_decision_tooltip']"
assert s.count(old)==1
p.write_text(s.replace(old,new))
subprocess.run(['git','add',focus_path,str(p)],check=True)
assert not subprocess.check_output(['git','diff','--name-only','--diff-filter=U']).strip(),'unresolved conflicts'
