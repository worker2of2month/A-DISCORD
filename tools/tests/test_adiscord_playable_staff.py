"""Source-executed staff lifecycle and live availability contracts, not an HOI4 playtest."""
from pathlib import Path
import re
import unittest

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


def parse(path):
    return parse_clausewitz(read(path))


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
            if k == 'has_dlc': return self.dlc
            if k in self.triggers: return self.condition(self.triggers[k]) == (v == 'yes')
            raise AssertionError('unsupported staff predicate: ' + k)
        return all(one(e) for e in rows)

    def execute(self, rows):
        chain = None
        for e in rows:
            k,v=e.key,e.value
            if k == 'if':
                chain=self.condition(block(v,'limit'))
                if chain: self.execute([x for x in v if x.key != 'limit'])
            elif k == 'else_if':
                if chain is False:
                    chain=self.condition(block(v,'limit'))
                    if chain: self.execute([x for x in v if x.key != 'limit'])
            elif k == 'else':
                if chain is False: self.execute(v)
                chain=None
            elif k == 'hidden_effect': self.execute(v)
            elif k == 'set_country_flag': self.flags.add(v)
            elif k == 'clr_country_flag': self.flags.discard(v)
            elif k == 'recruit_character':
                self.characters.add(v); self.recruited.append(v)
            elif k == 'custom_effect_tooltip': pass
            elif k in self.scripts: self.execute(self.scripts[k])
            else: raise AssertionError('unsupported staff effect: ' + k)


class PlayableStaffTests(unittest.TestCase):
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
        rows=parse('common/scripted_localisation/ADISCORD_ideologies.txt')
        for name,character in (('GetSTPPrewarHumanistLeader','STP_grigory_sotnikov'),('GetSTPPrewarNationalLeader','STP_maksim_shabrat')):
            definition=next((e.value for e in rows if e.key=='defined_text' and scalar(e.value,'name')==name),[])
            self.assertTrue(definition,name)
            texts=[e.value for e in definition if e.key=='text']
            for present in (False,True):
                for split in (False,True):
                    w=World('STP')
                    if present:w.characters.add(character)
                    if split:w.global_flags.add('STP_cw_started')
                    selected=next(scalar(t,'localization_key') for t in texts if w.condition(block(t,'trigger')))
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


if __name__ == '__main__':
    unittest.main()
