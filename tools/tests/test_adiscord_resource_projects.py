"""Execute investment transactions; native modifier loading still needs an HOI4 run."""
from pathlib import Path
import re
import unittest

from tools.tests.test_adiscord_economy_weekly_contracts import EconomyScriptFixture
from tools.validators.validate_adiscord_division_templates import Entry, parse_clausewitz

ROOT = Path(__file__).resolve().parents[2]
P = 'ADISCORD_economy_'
PROJECTS = {
    'precision_tooling': (1, 800, 6, 3, 90),
    'automated_industry': (2, 1200, 8, 6, 120),
    'national_computing': (3, 1500, 12, 4, 120),
    'logistics_contract': (4, 600, 4, 6, 60),
    'drone_contract': (5, 1000, 8, 4, 90),
    'platform_contract': (6, 1800, 8, 12, 120),
}
DECISIONS = ROOT / 'common/decisions/ADISCORD_economy_projects.txt'
DYNAMIC = ROOT / 'common/dynamic_modifiers/ADISCORD_economy_dynamic_modifiers.txt'


def read(path):
    path = ROOT / path
    return path.read_text(encoding='utf-8-sig') if path.exists() else ''


def direct(nodes, key):
    matches = [node.value for node in nodes if node.key == key]
    if len(matches) != 1:
        raise AssertionError(f'expected exactly one {key}, got {len(matches)}')
    return matches[0]


class ProjectFixture(EconomyScriptFixture):
    """Engine edges are explicit: surplus, allocation, native technology and equipment."""
    def __init__(self, unlocked=True, treasury=5000, components=40, alloys=40):
        super().__init__(facts={
            'has_capitulated': False, 'is_subject': False,
            P + 'has_current_schema': True,
        }, stubs=(P + 'mark_dirty', 'custom_effect_tooltip', 'effect_tooltip',
                  'force_update_dynamic_modifier'))
        self.focuses = {'VAL_econ_' + n for n in (
            'development_fund', 'precision_industry', 'special_metallurgy', 'automation',
            'computing', 'logistics', 'defense_orders', 'export_finance', 'integrated_economy')}
        if not unlocked:
            self.focuses.clear()
        self.techs = {'ADISCORD_tech_restored_truck_fleets', 'ADISCORD_tech_armored_rail_convoys',
                      'ADISCORD_tech_unmanned_recon_vehicles', 'ADISCORD_tech_semi_autonomous_combat_modules'}
        self.tag = 'VAL'
        self.dynamic = False
        self.reserved = (0, 0)
        self.equipment = {}
        self.scopes['A'].update({P+'treasury':treasury,
            'resource@rare_components':components, 'resource@rare_alloys':alloys,
            'num_of_available_civilian_factories':10, 'num_of_civilian_factories':20})
        self.dynamics = {n.key:n.value for n in parse_clausewitz(read(DYNAMIC))}
        if DECISIONS.exists():
            self.decisions = {n.key:n.value for n in direct(parse_clausewitz(read(DECISIONS)), P+'projects')}
        else:
            self.decisions = {}

    @staticmethod
    def native_conditions(entries):
        """The repository parser emits bare comparison operands as separate entries."""
        nodes = []
        index = 0
        while index < len(entries):
            node = entries[index]
            if node.key:
                nodes.append(node)
                index += 1
                continue
            operands = entries[index:index + 3]
            assert len(operands) == 3 and not any(n.key for n in operands)
            lhs, operator, rhs = [n.value for n in operands]
            assert operator in ('>', '<')
            nodes.append(Entry('check_variable', [
                Entry('var', lhs, node.line),
                Entry('value', rhs, node.line),
                Entry('compare', 'greater_than' if operator == '>' else 'less_than', node.line),
            ], node.line))
            index += 3
        return nodes

    def condition(self, entries, scope='A', previous=None, root='A'):
        def one(node):
            key, value = node.key, node.value
            if key == 'has_completed_focus':
                return value in self.focuses
            if key == 'has_tech':
                return value in self.techs
            if key == 'tag':
                return self.tag == value
            if key == 'has_dynamic_modifier':
                return self.dynamic
            if key in ('custom_trigger_tooltip', 'hidden_trigger'):
                return self.condition([c for c in value if c.key != 'tooltip'], scope, previous, root)
            if key in ('AND', 'OR', 'NOT'):
                results = [one(child) for child in self.native_conditions(value)]
                return any(results) if key == 'OR' else (not any(results) if key == 'NOT' else all(results))
            return super(ProjectFixture, self).condition([node], scope, previous, root)
        return all(one(node) for node in self.native_conditions(entries))

    def run(self, name, scope='A', previous=None, root='A'):
        if name not in self.definitions and name not in self.stubs:
            raise AssertionError('missing project effect '+name)
        super().run(name,scope,previous,root)

    def execute(self, entries, scope, previous, root):
        segment=[]
        special={'add_dynamic_modifier','remove_dynamic_modifier','add_equipment_to_stockpile','hidden_effect'}
        for node in entries:
            if node.key not in special:
                segment.append(node)
                continue
            if segment:
                super().execute(segment,scope,previous,root)
                segment=[]
            if node.key == 'hidden_effect':
                self.execute(node.value,scope,previous,root)
            elif node.key == 'add_dynamic_modifier':
                body=self.dynamics[direct(node.value,'modifier')]
                self.reserved=tuple(self.number(direct(body,'country_resource_cost_'+r),scope,previous)
                                    for r in ('rare_components','rare_alloys'))
                for r,q in zip(('rare_components','rare_alloys'),self.reserved):
                    self.scopes[scope]['resource@'+r]-=q
                self.scopes[scope]['num_of_available_civilian_factories']-=3
                self.dynamic=True
            elif node.key == 'remove_dynamic_modifier':
                for r,q in zip(('rare_components','rare_alloys'),self.reserved):
                    self.scopes[scope]['resource@'+r]+=q
                self.scopes[scope]['num_of_available_civilian_factories']+=3
                self.dynamic=False
            elif node.key == 'add_equipment_to_stockpile':
                typ=direct(node.value,'type');amount=float(direct(node.value,'amount'))
                self.equipment[typ]=self.equipment.get(typ,0)+amount
        if segment:
            super().execute(segment,scope,previous,root)


class ResourceProjectTransactions(unittest.TestCase):
    def test_project_cost_localisation_uses_native_resource_icons(self):
        for language in ('russian', 'english'):
            loc = read(f'localisation/{language}/ADISCORD_economy_l_{language}.yml')
            for name in PROJECTS:
                for suffix in ('', '_blocked', '_tooltip'):
                    key = f'{P}{name}_cost{suffix}:0'
                    line = next((row for row in loc.splitlines() if key in row), None)
                    self.assertIsNotNone(line, (language, key))
                    self.assertIn('£resources_strip|8', line, (language, key))
                    self.assertIn('£resources_strip|9', line, (language, key))
                    self.assertIn('£civ_factory', line, (language, key))
                    self.assertNotIn('компоненты §', line, (language, key))
                    self.assertNotIn('rare components §', line, (language, key))

    def test_exact_start_prices_and_actual_resource_allocation(self):
        for name,(pid,cost,c,a,days) in PROJECTS.items():
            with self.subTest(project=name):
                f=ProjectFixture(treasury=cost,components=c,alloys=a)
                f.run(P+'start_'+name)
                v=f.scopes['A']
                self.assertEqual(v[P+'treasury'],0)
                self.assertEqual(v[P+'current_month_action_costs'],cost)
                self.assertEqual(v[P+'project_id'],pid)
                self.assertEqual(v[P+'project_deposit'],cost)
                self.assertEqual(v['resource@rare_components'],0)
                self.assertEqual(v['resource@rare_alloys'],0)
                self.assertTrue(f.dynamic)

    def test_fractional_shortages_cannot_start_or_charge(self):
        for name,(_,cost,c,a,_) in PROJECTS.items():
            for inputs in ({'treasury':cost-.001},{'components':c-.001},{'alloys':a-.001}):
                with self.subTest(project=name,inputs=inputs):
                    f=ProjectFixture(**inputs);before=f.scopes['A'][P+'treasury']
                    f.run(P+'start_'+name)
                    self.assertEqual(f.scopes['A'][P+'treasury'],before)
                    self.assertNotIn(P+'project_id',f.scopes['A'])

    def test_one_shared_slot_and_no_double_payment(self):
        f=ProjectFixture();f.run(P+'start_precision_tooling')
        for name in PROJECTS:f.run(P+'start_'+name)
        self.assertEqual(f.scopes['A'][P+'treasury'],4200)
        self.assertEqual(f.scopes['A'][P+'project_id'],1)
        self.assertEqual(f.scopes['A'][P+'project_deposit'],800)

    def test_success_releases_inputs_once_and_installs_permanent_capability(self):
        for name in ('precision_tooling','automated_industry','national_computing'):
            f=ProjectFixture();f.run(P+'start_'+name);f.run(P+'finish_'+name)
            self.assertTrue(f.scopes['A']['idea@'+P+name])
            self.assertFalse(f.dynamic)
            self.assertNotIn(P+'project_id',f.scopes['A'])
            self.assertEqual(f.scopes['A']['resource@rare_components'],40)
            paid=f.scopes['A'][P+'treasury']
            f.run(P+'finish_'+name);f.run(P+'start_'+name)
            self.assertEqual(f.scopes['A'][P+'treasury'],paid)
            self.assertNotIn(P+'project_id',f.scopes['A'])

    def test_resource_shortage_or_capitulation_refunds_75_percent_without_reward(self):
        for name,(_,cost,_,_,_) in PROJECTS.items():
            for failure in ('shortage','capitulated','subject'):
                with self.subTest(project=name,failure=failure):
                    f=ProjectFixture();f.run(P+'start_'+name)
                    if failure=='shortage':f.scopes['A']['resource@rare_alloys']=-.001
                    elif failure=='capitulated':f.facts['has_capitulated']=True
                    else:f.facts['is_subject']=True
                    f.run(P+'finish_'+name)
                    self.assertEqual(f.scopes['A'][P+'treasury'],5000-cost*.25)
                    self.assertEqual(f.scopes['A'][P+'current_month_action_income'],cost*.75)
                    self.assertFalse(f.equipment)
                    self.assertFalse(f.scopes['A'].get('idea@'+P+name,False))
                    self.assertNotIn(P+'project_id',f.scopes['A'])
                    self.assertFalse(f.dynamic)
                    f.run(P+'cancel_project')
                    self.assertEqual(f.scopes['A'][P+'treasury'],5000-cost*.25)

    def test_old_callback_cannot_cancel_or_finish_another_project(self):
        f=ProjectFixture();f.run(P+'start_precision_tooling');f.run(P+'cancel_project')
        f.run(P+'start_automated_industry');paid=f.scopes['A'][P+'treasury']
        f.run(P+'finish_precision_tooling')
        self.assertEqual(f.scopes['A'][P+'treasury'],paid)
        self.assertEqual(f.scopes['A'][P+'project_id'],2)
        self.assertTrue(f.dynamic)

    def test_focus_research_and_country_gates(self):
        for name in PROJECTS:
            f=ProjectFixture(unlocked=False);f.run(P+'start_'+name)
            self.assertNotIn(P+'project_id',f.scopes['A'])
        for name in ('drone_contract','platform_contract','logistics_contract'):
            f=ProjectFixture();f.techs.clear();f.run(P+'start_'+name)
            self.assertNotIn(P+'project_id',f.scopes['A'])
        f=ProjectFixture();f.tag='STP';f.run(P+'start_precision_tooling')
        self.assertNotIn(P+'project_id',f.scopes['A'])

    def test_delivery_uses_exact_existing_equipment_and_is_idempotent(self):
        expected={
            'logistics_contract':{'motorized_equipment_1':300,'armored_train_equipment_1':20},
            'drone_contract':{'ADISCORD_recon_drone_carrier_2170':60},
            'platform_contract':{'ADISCORD_combat_platform_2170':80},
        }
        for name,items in expected.items():
            f=ProjectFixture();f.run(P+'start_'+name)
            f.run(P+'finish_'+name);f.run(P+'finish_'+name)
            self.assertEqual(f.equipment,items)

    def test_civilian_factory_capacity_uses_the_exact_three_factory_price(self):
        for available in (0, 2, 2.999, 3):
            f = ProjectFixture()
            f.scopes['A']['num_of_available_civilian_factories'] = available
            f.run(P + 'start_precision_tooling')
            self.assertEqual(f.dynamic, available >= 3, available)
        f = ProjectFixture()
        f.run(P + 'start_precision_tooling')
        f.scopes['A']['num_of_civilian_factories'] = 2.999
        f.run(P + 'finish_precision_tooling')
        self.assertFalse(f.scopes['A'].get('idea@' + P + 'precision_tooling', False))
        self.assertEqual(f.scopes['A'][P + 'treasury'], 4800)

    def test_sts_success_and_zero_surplus_after_reservation_are_allowed(self):
        for name, (_, cost, components, alloys, _) in PROJECTS.items():
            with self.subTest(project=name):
                f = ProjectFixture(treasury=cost, components=components, alloys=alloys)
                f.tag = 'STS'
                f.focuses = {focus.replace('VAL_econ_', 'STP_pc_investment_') for focus in f.focuses}
                f.scopes['A']['STP_cw_postwar'] = True
                f.scopes['A']['num_of_available_civilian_factories'] = 3
                f.run(P + 'start_' + name)
                self.assertTrue(f.dynamic)
                self.assertEqual(f.scopes['A']['num_of_available_civilian_factories'], 0)
                f.run(P + 'finish_' + name)
                self.assertFalse(f.dynamic)
                self.assertTrue(f.equipment or f.scopes['A'].get('idea@' + P + name))

    def test_native_decision_cancel_and_completion_share_the_paid_receipt(self):
        for name, (_, cost, _, _, _) in PROJECTS.items():
            for cancel in (True, False):
                with self.subTest(project=name, cancel=cancel):
                    f = ProjectFixture()
                    decision = f.decisions[P + name]
                    f.execute(direct(decision, 'complete_effect'), 'A', None, 'A')
                    self.assertEqual(f.scopes['A'][P + 'treasury'], 5000 - cost)
                    self.assertFalse(f.equipment)
                    self.assertFalse(f.scopes['A'].get('idea@' + P + name, False))
                    if cancel:
                        f.scopes['A']['resource@rare_components'] = -0.01
                        self.assertTrue(f.condition(direct(decision, 'cancel_trigger')))
                        callback = direct(decision, 'cancel_effect')
                    else:
                        self.assertFalse(f.condition(direct(decision, 'cancel_trigger')))
                        callback = direct(decision, 'remove_effect')
                    f.execute(callback, 'A', None, 'A')
                    self.assertFalse(f.dynamic)
                    self.assertNotIn(P + 'project_deposit', f.scopes['A'])
                    self.assertEqual(f.scopes['A'][P + 'treasury'], 5000 - cost * (0.25 if cancel else 1))

    def test_start_and_refund_reconcile_with_the_actual_weekly_cash_ledger(self):
        for cancel in (True, False):
            f = ProjectFixture()
            f.stubs.update(P + n for n in ('calculate_debt_metrics', 'update_macro_confidence',
                'update_debt_state_after_settlement', 'queue_debt_notification'))
            v = f.scopes['A']
            v.update({P + 'treasury_cap': 10000, P + 'accounting_period_treasury_start': 5000,
                      P + 'weekly_balance': 100})
            f.run(P + 'start_national_computing')
            f.run(P + 'apply_weekly_balance')
            self.assertEqual(v[P + 'last_period_unexplained_delta'], 0)
            self.assertEqual(v[P + 'treasury'], 3600)
            f.run(P + ('cancel_project' if cancel else 'finish_national_computing'))
            f.run(P + 'apply_weekly_balance')
            self.assertEqual(v[P + 'last_period_unexplained_delta'], 0)
            self.assertEqual(v[P + 'treasury'], 3700 + (1125 if cancel else 0))


class ResourceProjectSourceContracts(unittest.TestCase):
    def test_decisions_show_full_prices_and_time_and_guard_each_cancellation(self):
        self.assertTrue(DECISIONS.exists(),'shared economic projects are missing')
        decisions={n.key:n.value for n in direct(parse_clausewitz(read(DECISIONS)),P+'projects')}
        loc=read('localisation/russian/ADISCORD_economy_l_russian.yml')
        for name,(pid,cost,c,a,days) in PROJECTS.items():
            nodes=decisions[P+name]
            self.assertEqual(direct(nodes,'cost'),'0')
            self.assertEqual(direct(nodes,'days_remove'),str(days))
            self.assertIn(P+'start_'+name, str(direct(nodes,'complete_effect')))
            self.assertIn(P+'finish_'+name, str(direct(nodes,'remove_effect')))
            self.assertIn('project_id',str(direct(nodes,'cancel_effect')))
            key=direct(nodes,'custom_cost_text')
            for suffix in ('','_blocked','_tooltip'):
                match=re.search(r'(?m)^\s*'+key+suffix+r':\d*\s+"([^"\n]+)"',loc)
                self.assertIsNotNone(match,key+suffix)
                self.assertIn(str(cost),match[1])
                self.assertIn('компонент',match[1])
                self.assertIn('сплав',match[1])
            self.assertIn('custom_cost_trigger',[n.key for n in nodes])

    def test_all_resource_costs_are_country_scoped_native_consumers(self):
        source=read(DYNAMIC)
        body=direct(parse_clausewitz(source),P+'project_allocation')
        self.assertEqual(direct(body,'country_resource_cost_rare_components'),P+'project_components')
        self.assertEqual(direct(body,'country_resource_cost_rare_alloys'),P+'project_alloys')
        self.assertEqual(direct(body,'civilian_factory_use'),'3')
        self.assertNotIn('add_resource',read(DECISIONS))

    def test_both_economic_branches_have_nine_reachable_nonoverlapping_focuses(self):
        for country,prefix,parent in (('VAL','VAL_econ_','VAL_Industrial_Mobilization_Plan'),
                                     ('STP','STP_pc_investment_','STP_pc_economy_recovery_budget')):
            source=read(f'common/national_focus/ADISCORD_national_focus_{country}.txt')
            trees=[t for t in parse_clausewitz(source) if t.key=='focus_tree']
            selected=[f.value for t in trees for f in t.value if f.key=='focus' and str(direct(f.value,'id')).startswith(prefix)]
            self.assertEqual(len(selected),9)
            ids={direct(f,'id') for f in selected}
            for f in selected:
                for n in f:
                    if n.key=='prerequisite':
                        self.assertTrue(all(c.value in ids|{parent} for c in n.value if c.key=='focus'))
                self.assertIn('completion_reward',[n.key for n in f])
            containing=next(t for t in trees if any(f.key=='focus' and str(direct(f.value,'id')).startswith(prefix) for f in t.value))
            positions={}
            for node in containing.value:
                if node.key!='focus':continue
                f=node.value
                if not all(any(n.key==k for n in f) for k in ('x','y')):continue
                pos=(direct(f,'x'),direct(f,'y'));ident=direct(f,'id')
                positions.setdefault(pos,[]).append(ident)
            for pos,fs in positions.items():
                if any(x.startswith(prefix) for x in fs):self.assertEqual(len(fs),1,(pos,fs))

    def test_project_capstone_requires_delivered_investment_not_only_completed_focuses(self):
        for country in ('VAL','STP'):
            src=read(f'common/national_focus/ADISCORD_national_focus_{country}.txt')
            self.assertIn(P+'has_completed_capital_project',src)


if __name__=='__main__':
    unittest.main()
