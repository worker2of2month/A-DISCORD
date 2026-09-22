"""Source-executed staff lifecycle and live availability contracts, not an HOI4 playtest."""
from pathlib import Path
import re
import unittest
from functools import lru_cache

from tools.tests.test_adiscord_stp_preparation import parse_clausewitz, block, scalar, walk

ROOT = Path(__file__).resolve().parents[2]
COUNTRIES = ('STP', 'STS', 'VAL')
MIO_PATH = 'common/military_industrial_organization/organizations/ADISCORD_playable_organizations.txt'
IDEAS = {'STP': 'common/ideas/ADISCORD_STP_civil_war_ideas.txt',
         'VAL': 'common/ideas/ADISCORD_VAL_rework_ideas.txt'}
SLOTS = ('head_of_state', 'minister_of_defense', 'minister_of_economy',
         'minister_of_health', 'minister_of_education', 'chief_of_intelligence')
BASIC_MINISTERS = {
    'STP': ('Pavel_Ruden', 'Elena_Savina', 'Anton_Belik', 'Sofia_Lanskaya', 'Viktor_Kedrov', 'Daria_Orlova'),
    'VAL': ('Roman_Terek', 'Inga_Voss', 'Mark_Sedov', 'Alina_Greif', 'Denis_Krell', 'Lev_Moren'),
}
GENERALS = {
    'STP': ('STP_Pavel_Gromin', 'STP_Elena_Vetrova', 'STP_Oleg_Vershin'),
    'VAL': ('VAL_Anton_Rein', 'VAL_Irina_Karst', 'VAL_Viktor_Bran'),
}


def read(path):
    target = ROOT / path
    return target.read_text(encoding='utf-8-sig') if target.exists() else ''


@lru_cache(maxsize=None)
def parse(path):
    return parse_clausewitz(read(path))


def party_leader_rows():
    return (parse('common/scripted_localisation/ADISCORD_STP_scripted_loc.txt') +
            parse('common/scripted_localisation/ADISCORD_VAL_contract_scripted_loc.txt'))


def optional_block(rows, key):
    found = [e.value for e in rows if e.key == key]
    if not found:
        return []
    if len(found) != 1 or not isinstance(found[0], list):
        raise AssertionError('Expected zero or one block ' + key)
    return found[0]


class World:
    """Evaluate only documented predicates used by this feature; unknowns fail closed."""
    def __init__(self, tag='STP', postwar=False, focuses=(), dlc=True):
        self.tag = tag
        self.flags = {'STP_cw_postwar'} if postwar else set()
        self.global_flags = set()
        self.focuses = set(focuses)
        self.characters = set()
        self.recruited = []
        self.dlc = dlc
        self.government = 'etatism' if tag == 'VAL' else 'hedonism'
        self.roles = {}
        self.leaders = {}
        self.role_writes = []
        self.scripts = {}
        self.triggers = {}
        for country in ('STP', 'VAL'):
            suffix = 'STP_scripted' if country == 'STP' else 'VAL_rework'
            self.triggers.update({e.key:e.value for e in parse(f'common/scripted_triggers/ADISCORD_{suffix}_triggers.txt')})
            effects = 'ADISCORD_STP_scripted_effects.txt' if country == 'STP' else 'ADISCORD_VAL_effects.txt'
            self.scripts.update({e.key:e.value for e in parse('common/scripted_effects/' + effects)})

    def condition(self, rows):
        def one(e):
            k,v=e.key,e.value
            if k in ('AND', 'hidden_trigger', 'FROM', 'ROOT', 'owner'):
                return self.condition(v)
            if k == 'OR': return any(one(x) for x in v)
            if k == 'NOT': return not any(one(x) for x in v)
            if k == 'always': return v == 'yes'
            if k in ('tag', 'original_tag'): return v == self.tag
            if k == 'exists': return v == 'yes'
            if k in ('has_capitulated', 'is_subject'): return v == 'no'
            if k == 'has_country_flag': return v in self.flags
            if k == 'has_global_flag': return v in self.global_flags
            if k == 'has_completed_focus': return v in self.focuses
            if k == 'has_character': return v in self.characters
            if k == 'has_government': return self.government == v
            if k == 'has_country_leader': return scalar(v, 'character') in self.leaders.values()
            if k == 'has_dlc': return self.dlc
            if k in self.triggers: return self.condition(self.triggers[k]) == (v == 'yes')
            raise AssertionError('unsupported staff predicate: ' + k)
        return all(one(e) for e in rows)

    def execute(self, rows, character=None):
        chain = None
        for e in rows:
            k,v=e.key,e.value
            if k == 'if':
                chain=self.condition(block(v,'limit'))
                if chain: self.execute([x for x in v if x.key != 'limit'], character)
            elif k == 'else_if':
                if chain is False:
                    chain=self.condition(block(v,'limit'))
                    if chain: self.execute([x for x in v if x.key != 'limit'], character)
            elif k == 'else':
                if chain is False: self.execute(v, character)
                chain=None
            elif k == 'hidden_effect': self.execute(v, character)
            elif k == 'set_global_flag': self.global_flags.add(v)
            elif k == 'set_country_flag': self.flags.add(v)
            elif k == 'clr_country_flag': self.flags.discard(v)
            elif k == 'recruit_character':
                self.characters.add(v); self.recruited.append(v)
            elif k == 'add_country_leader_role':
                target = scalar(v, 'character') if character is None else character
                if target not in self.characters:
                    raise AssertionError('role requires recruited character')
                ideology = scalar(block(v, 'country_leader'), 'ideology')
                self.roles.setdefault(target, set()).add(ideology)
                self.role_writes.append((target, ideology))
                if scalar(v, 'promote_leader') == 'yes': self.leaders[ideology] = target
            elif k == 'promote_character':
                target, ideology = scalar(v, 'character'), scalar(v, 'ideology')
                assert ideology in self.roles[target]
                self.leaders[ideology] = target
            elif k == 'remove_country_leader_role':
                ideology = scalar(v, 'ideology')
                self.roles.setdefault(character, set()).discard(ideology)
                if self.leaders.get(ideology) == character: self.leaders.pop(ideology)
            elif k in self.characters and isinstance(v, list): self.execute(v, k)
            elif k == 'custom_effect_tooltip': pass
            elif k in self.scripts: self.execute(self.scripts[k])
            else: raise AssertionError('unsupported staff effect: ' + k)


class PlayableStaffTests(unittest.TestCase):
    def test_val_state_party_names_are_plain_in_both_languages(self):
        expected = {
            'russian': 'Государственная партия Кефрейта',
            'english': 'Kefreyt State Party',
        }
        for language, name in expected.items():
            path = ROOT / f'localisation/{language}/parties_l_{language}.yml'
            data = path.read_bytes()
            self.assertTrue(data.startswith(b'\xef\xbb\xbf'), language)
            text = data.decode('utf-8-sig')
            for suffix in ('', '_long'):
                key = 'VAL_etatism_party' + suffix
                with self.subTest(language=language, key=key):
                    values = re.findall(
                        rf'^[ \t]*{key}:(?:\d+)?[ \t]*"([^"\r\n]*)"[ \t]*$',
                        text, re.M,
                    )
                    self.assertEqual(values, ['£GFX_VAL_etatist_party_texticon ' + name])

    def test_basic_ministers_use_all_six_native_slots_and_live_phase_gate(self):
        for country, people in BASIC_MINISTERS.items():
            ideas=block(parse(IDEAS[country]), 'ideas')
            for slot,person in zip(SLOTS,people):
                key=f'minister_{country}_{person}'
                body=block(block(ideas,'political_advisor_'+slot),key)
                self.assertTrue(body, key)
                self.assertEqual(scalar(body,'cost'),'75')
                self.assertTrue(block(body,'traits'),key)
                for tag in COUNTRIES:
                    for postwar in (False,True):
                        w=World(tag,postwar)
                        correct=tag=='VAL' if country=='VAL' else tag in ('STP','STS') and postwar
                        self.assertEqual(w.condition(block(body,'allowed')) and w.condition(block(body,'available')),correct,(key,tag,postwar))

    def test_baseline_generals_wait_for_postwar_and_never_resurrect_on_repeat(self):
        for country in ('STP','VAL'):
            for tag in (('STP','STS') if country=='STP' else ('VAL',)):
                w=World(tag)
                effect=w.scripts.get(country+'_qol_initialize_staff')
                self.assertTrue(effect, country)
                w.execute(effect)
                self.assertEqual(set(w.recruited),set(GENERALS[country][:2]) if country=='VAL' else set())
                w.flags.add('STP_cw_postwar')
                w.execute(effect)
                self.assertEqual(set(w.recruited),set(GENERALS[country][:2]))
                w.characters.clear()
                before=list(w.recruited)
                w.execute(effect)
                self.assertEqual(w.recruited,before,'initialization cannot resurrect retired officers')
                self.assertNotIn(GENERALS[country][2],w.recruited)

    def test_mio_country_registration_is_not_blocked_by_live_focus_or_postwar_state(self):
        rows=parse(MIO_PATH)
        for country in ('STP','VAL'):
            for kind in ('arsenal','airworks','armor_bureau'):
                name=country+'_qol_'+kind
                body=block(rows,name)
                self.assertTrue(body,name)
                self.assertTrue(block(body,'initial_trait'),name)
                self.assertGreaterEqual(sum(e.key=='trait' for e in body),4,name)
                allowed=block(body,'allowed')
                self.assertFalse(any(e.key in ('has_country_flag','has_completed_focus') for e in walk(allowed)),name)
                for tag in COUNTRIES:
                    w=World(tag)
                    expected=tag=='VAL' if country=='VAL' else tag in ('STP','STS')
                    self.assertEqual(w.condition(allowed),expected,(name,tag))

    def test_basic_mios_and_non_dlc_designers_are_complementary_after_phase_gate(self):
        mios=parse(MIO_PATH)
        for country in ('STP','VAL'):
            for kind,slot in (('arsenal','materiel_manufacturer'),('airworks','aircraft_manufacturer')):
                name=country+'_qol_'+kind
                mio=block(mios,name)
                idea=block(block(block(parse(IDEAS[country]),'ideas'),slot),name+'_designer')
                self.assertTrue(mio and idea,name)
                for postwar in (False,True):
                    for dlc in (False,True):
                        w=World(country,postwar,dlc=dlc)
                        enabled=country=='VAL' or postwar
                        self.assertEqual(w.condition(block(mio,'available')),enabled and dlc,(name,postwar,dlc))
                        self.assertEqual(w.condition(block(idea,'available')),enabled and not dlc,(name,postwar,dlc))

    def test_party_labels_use_live_characters_and_disappear_at_split(self):
        rows=party_leader_rows()
        for name,character in (('GetSTPPrewarHumanistLeader','STP_grigory_sotnikov'),('GetSTPPrewarNationalLeader','STP_maksim_shabrat')):
            definition=next((e.value for e in rows if e.key=='defined_text' and scalar(e.value,'name')==name),[])
            self.assertTrue(definition,name)
            texts=[e.value for e in definition if e.key=='text']
            for present in (False,True):
                for split in (False,True):
                    w=World('STP')
                    if present:
                        w.characters.add(character)
                        w.leaders['displayed_party'] = character
                    if split:w.global_flags.add('STP_cw_started')
                    selected=next(scalar(t,'localization_key') for t in texts if w.condition(optional_block(t,'trigger')))
                    self.assertEqual(selected!='ADISCORD_qol_no_party_leader',present and not split,(name,present,split))
            for language in ('russian','english'):
                loc=read(f'localisation/{language}/parties_l_{language}.yml')
                self.assertIn('['+name+']',loc)

    def test_new_general_definitions_exist_and_baseline_cannot_bypass_stp_history(self):
        for country,names in GENERALS.items():
            chars=block(parse('common/characters/'+country+'.txt'),'characters')
            for i,name in enumerate(names):
                body=block(chars,name)
                self.assertTrue(body,name)
                role=block(body,'corps_commander')
                self.assertTrue(role,name)
                self.assertEqual(int(scalar(role,'skill')),4 if i==2 else 2)
        history=read('history/countries/STP - StepanLand.txt')
        for name in GENERALS['STP']:self.assertNotIn('recruit_character = '+name,history)

    def test_elite_routes_unlock_for_party_and_resistance_but_not_early(self):
        routes = {
            'STP': {'administration': ('STP_pc_shabrat_cabinet', 'STP_pw_republic_district_authority', 'STP_pw_party_executive_secretariat'),
                    'industry': ('STP_pc_investment_integrated_economy', 'STP_pw_republic_industrial_settlement', 'STP_pw_party_industrial_settlement'),
                    'army': ('STP_pc_army_staff_doctrine', 'STP_pw_republic_professional_service', 'STP_pw_party_professional_service')},
            'VAL': {'administration': ('VAL_State_Contract',), 'industry': ('VAL_Industrial_Mobilization_Plan',), 'army': ('VAL_Contract_General_Staff',)}
        }
        for country, categories in routes.items():
            for category, focuses in categories.items():
                for focus in focuses:
                    w=World(country,focuses=[focus])
                    gate=w.triggers[country+'_qol_elite_'+category+'_available']
                    self.assertEqual(w.condition(gate),country=='VAL')
                    w.flags.add('STP_cw_postwar')
                    self.assertTrue(w.condition(gate))
                    w.focuses.clear()
                    self.assertFalse(w.condition(gate))

    def test_elite_general_reward_does_not_wait_for_its_own_completed_focus(self):
        for country, focus_ids in {'STP': ('STP_pc_army_staff_doctrine','STP_pw_republic_professional_service','STP_pw_party_professional_service'),
                                  'VAL': ('VAL_Contract_General_Staff',)}.items():
            trees=parse('common/national_focus/ADISCORD_national_focus_'+country+'.txt')
            focuses={scalar(f.value,'id'):f.value for t in trees if t.key=='focus_tree' for f in t.value if f.key=='focus'}
            for fid in focus_ids:
                reward=block(focuses[fid],'completion_reward')
                grant=[e for e in reward if e.key==country+'_qol_grant_elite_officer']
                self.assertEqual(len(grant),1,fid)
                w=World(country,postwar=True)
                w.execute(grant)
                self.assertIn(GENERALS[country][2],w.characters)
                w.characters.clear(); before=list(w.recruited)
                w.execute(grant)
                self.assertEqual(w.recruited,before)

    def test_new_stelander_roster_is_unique_across_revived_claimants(self):
        first=World('STS',True); second=World('STP',True)
        first.execute(first.scripts['STP_qol_initialize_staff'])
        second.global_flags=first.global_flags
        second.execute(second.scripts['STP_qol_initialize_staff'])
        self.assertEqual(second.recruited,[])

    def test_exact_settlement_and_startup_hooks_exist_without_periodic_scans(self):
        w=World()
        settle=w.scripts['STP_cw_finish_mobilization']
        calls=[e.key for e in settle]
        postwar=next(i for i,e in enumerate(settle) if e.key=='set_country_flag' and e.value=='STP_cw_postwar')
        self.assertGreater(calls.index('STP_qol_initialize_staff'),postwar)
        for country,fn in (('STP','02_ADISCORD_STP_on_actions.txt'),('VAL','02_ADISCORD_VAL_rework_on_actions.txt')):
            hooks=block(parse('common/on_actions/'+fn),'on_actions')
            self.assertTrue(any(e.key==country+'_qol_initialize_staff' for e in walk(block(hooks,'on_startup'))))
            for event in hooks:
                if event.key!='on_startup':
                    self.assertFalse(any(e.key.endswith('_qol_initialize_staff') for e in walk(event.value)),event.key)

    def test_sotnikov_is_not_native_leader_of_two_parties_and_story_role_is_preserved(self):
        w=World()
        person='STP_grigory_sotnikov'
        w.characters.add(person);w.roles[person]={'steland_military_directory'}
        w.leaders['steland_military_directory']=person
        w.execute(w.scripts['STP_qol_initialize_party_leaders'])
        self.assertEqual(w.roles[person],{'humanism_ideology'})
        self.assertEqual(w.government,'hedonism')
        self.assertEqual(w.leaders.get('humanism_ideology'),person)
        before=list(w.role_writes)
        w.execute(w.scripts['STP_qol_initialize_party_leaders'])
        self.assertEqual(w.role_writes,before)
        w.execute(w.scripts['STP_cw_release_resistance_officeholders'])
        self.assertNotIn('humanism_ideology',w.roles[person])
        self.assertNotIn(person,w.leaders.values())
        self.assertTrue(any(e.key=='add_country_leader_role' and any(x.key=='ideology' and x.value=='steland_military_directory' for x in walk(e.value))
                            for e in walk(w.scripts['STP_cw_establish_resistance_command'])))

    def test_party_initialization_never_revives_people_or_runs_after_the_stp_split(self):
        for country in ('STP','VAL'):
            w=World(country)
            effect=w.scripts[country+'_qol_initialize_party_leaders']
            w.execute(effect)
            self.assertFalse(w.recruited)
            self.assertFalse(w.role_writes)
            self.assertFalse(any(e.key in ('set_politics','retire_character','create_country_leader','set_nationality') for e in walk(effect)))
        for guard in ('STP_cw_started','STP_cw_participant','STP_cw_postwar'):
            w=World();w.characters.add('STP_grigory_sotnikov')
            (w.global_flags if guard=='STP_cw_started' else w.flags).add(guard)
            w.execute(w.scripts['STP_qol_initialize_party_leaders'])
            self.assertFalse(w.role_writes,guard)

    def test_val_opposition_uses_existing_officers_without_changing_government(self):
        w=World('VAL'); w.characters.update(('VAL_Boris_Gromov','VAL_Renata_Morn'))
        effect=w.scripts['VAL_qol_initialize_party_leaders']
        w.execute(effect)
        self.assertEqual(w.leaders,{'chauvinism_ideology':'VAL_Boris_Gromov','pragmatism_ideology':'VAL_Renata_Morn'})
        self.assertEqual(w.government,'etatism')
        before=list(w.role_writes);w.characters.clear();w.execute(effect)
        self.assertEqual(w.role_writes,before)
        self.assertFalse(w.recruited)

    def test_mio_tree_references_equipment_stats_scopes_and_sprites(self):
        sprites=set()
        for path in (ROOT/'interface').glob('*.gfx'):
            sprites.update(re.findall(r'\bname\s*=\s*"(GFX_[^"]+)"',path.read_text(encoding='utf-8-sig')))
        archetypes=set()
        for path in (ROOT/'common/units/equipment').glob('*.txt'):
            for root in parse_clausewitz(path.read_text(encoding='utf-8-sig')):
                if root.key!='equipments':continue
                for entry in root.value:
                    if isinstance(entry.value,list) and any(e.key=='is_archetype' and e.value=='yes' for e in entry.value):archetypes.add(entry.key)
        enums=parse('common/script_enums.txt')
        production={e.value for e in block(enums,'script_enum_production_stat')}
        equipment_stats={e.value for e in block(enums,'script_enum_equipment_stat')}
        for mio in parse(MIO_PATH):
            self.assertTrue(scalar(mio.value,'icon') in sprites, (mio.key, scalar(mio.value,'icon')))
            self.assertEqual([e.key for e in block(mio.value,'available')],['FROM'])
            self.assertTrue({e.value for e in block(mio.value,'equipment_type')}<=archetypes,mio.key)
            traits={scalar(e.value,'token'):e.value for e in mio.value if e.key=='trait'}
            positions=set()
            for name,trait in traits.items():
                self.assertTrue(scalar(trait,'icon') in sprites, scalar(trait,'icon'))
                xy=(scalar(block(trait,'position'),'x'),scalar(block(trait,'position'),'y'))
                self.assertNotIn(xy,positions);positions.add(xy)
                for parent in optional_block(trait,'any_parent'): self.assertIn(parent.value,traits)
                for other in optional_block(trait,'mutually_exclusive'):
                    self.assertIn(name,[e.value for e in block(traits[other.value],'mutually_exclusive')])
            for e in walk(mio.value):
                if e.key=='equipment_bonus':self.assertTrue({x.key for x in e.value}<=equipment_stats)
                if e.key=='production_bonus':self.assertTrue({x.key for x in e.value}<=production)

    def test_localisation_defines_every_new_entity_and_keeps_bilingual_key_parity(self):
        dictionaries=[]
        for language in ('russian','english'):
            path=ROOT/f'localisation/{language}/ADISCORD_playable_staff_l_{language}.yml'
            self.assertTrue(path.read_bytes().startswith(b'\xef\xbb\xbf'))
            rows=re.findall(r'^ ([\w.]+):(?:\d+)? "(.*)"$',path.read_text(encoding='utf-8-sig'),re.M)
            values=dict(rows);self.assertEqual(len(values),len(rows))
            dictionaries.append(values)
            for country in ('STP','VAL'):
                ideas=block(parse(IDEAS[country]),'ideas')
                for slot in ideas:
                    if not isinstance(slot.value,list):continue
                    for idea in slot.value:
                        if not isinstance(idea.value,list):continue
                        if '_qol_' in idea.key or any(idea.key=='minister_'+country+'_'+p for p in BASIC_MINISTERS[country]):
                            name=next((x.value for x in idea.value if x.key=='name'),idea.key)
                            self.assertIn(name,values,name)
                for name in GENERALS[country]:self.assertIn(name,values)
            for mio in parse(MIO_PATH):
                self.assertIn(scalar(mio.value,'name'),values)
                for e in walk(mio.value):
                    if e.key=='name':self.assertIn(e.value,values)
        self.assertEqual(dictionaries[0].keys(),dictionaries[1].keys())

    def test_party_migration_preserves_an_existing_sotnikov_government(self):
        w=World('STP');w.government='etatism'
        person='STP_grigory_sotnikov'
        w.characters.add(person)
        w.roles[person]={'steland_military_directory'}
        w.leaders['steland_military_directory']=person
        w.execute(w.scripts['STP_qol_initialize_party_leaders'])
        self.assertEqual(w.roles[person],{'steland_military_directory'})
        self.assertEqual(w.leaders,{'steland_military_directory':person})
        self.assertFalse(w.role_writes)

    def test_labels_hide_retired_party_roles_even_when_character_is_still_recruited(self):
        rows=party_leader_rows()
        names={'GetSTPPrewarHumanistLeader':'STP_grigory_sotnikov',
               'GetSTPPrewarNationalLeader':'STP_maksim_shabrat',
               'GetVALStatePartyLeader':'VAL_Valera_Solgalov',
               'GetVALHedonistPartyLeader':'VAL_Artem_Rask',
               'GetVALNationalPartyLeader':'VAL_Boris_Gromov',
               'GetVALPragmatistPartyLeader':'VAL_Renata_Morn'}
        for fn,character in names.items():
            definition=next(e.value for e in rows if e.key=='defined_text' and scalar(e.value,'name')==fn)
            w=World('STP' if fn.startswith('GetSTP') else 'VAL')
            w.characters.add(character)
            texts=[e.value for e in definition if e.key=='text']
            def selected():return next(scalar(t,'localization_key') for t in texts if w.condition(optional_block(t,'trigger')))
            self.assertEqual(selected(),'ADISCORD_qol_no_party_leader')
            w.leaders['displayed_party']=character
            self.assertNotEqual(selected(),'ADISCORD_qol_no_party_leader')
            w.characters.clear()
            self.assertEqual(selected(),'ADISCORD_qol_no_party_leader')


if __name__ == '__main__':
    unittest.main()
