"""Temporary runner helper; the tests are appended to the existing economy suite."""
from pathlib import Path

ADDITIONS = r'''

def building_budget_fixture(business=12, clusters=4, science=2):
    """Mixed economy, development 3, 250k army, active industry, normal budgets.

    Engine inputs: 60 civilian/30 military factories, four dockyards, 300 planes,
    twelve ships. Monthly interest is six. No focus/flat-income bonuses apply.
    This executes authored arithmetic, not a native game campaign.
    """
    f = income_fixture(civilian=60, military=30, resources=10, business=business)
    for name in tuple(f.facts):
        match = re.search(r'_development_(at_least|exact)_(\d)$', name)
        if match:
            f.facts[name] = int(match[2]) <= 3 if match[1] == 'at_least' else int(match[2]) == 3
    # Every authored manpower threshold is below this scenario's 250,000 soldiers.
    f.facts.update({'has_army_manpower': True, 'has_war': False})
    values = f.scopes['A']
    values.update({
        'ADISCORD_industrial_cluster_count': clusters,
        'ADISCORD_science_center_count': science,
        'ADISCORD_state_development_level': 3,
        'ADISCORD_social_system_development_level': 3,
        'num_deployed_planes': 300,
        'num_ships': 12,
        P + 'cached_army_organization_factor': 1,
        P + 'cached_available_civilian_factories': 0,
        P + 'cached_available_military_factories': 0,
        P + 'cached_naval_factories': 4,
        P + 'army_spending_mode': 3,
        P + 'social_spending_mode': 3,
        P + 'research_spending_mode': 3,
        P + 'debt_service': 6,
        P + 'debt': 600,
        P + 'treasury_cap': 10000,
        P + 'accounting_period_treasury_start': 100,
    })
    f.run(P + 'calculate_income')
    f.run(P + 'calculate_expenses')
    f.run(P + 'calculate_monthly_balance')
    f.run(P + 'calculate_weekly_budget')
    return f


class BuildingIncomeTests(unittest.TestCase):
    def test_developed_building_economy_exceeds_100_net_per_week(self):
        f = building_budget_fixture()
        values = f.scopes['A']
        self.assertGreater(values[P + 'monthly_expenses'], 40)
        self.assertEqual(values[P + 'debt_service'], 6)
        self.assertEqual(values[P + 'final_overall_income_factor_bp'], 100)
        self.assertEqual(values.get(P + 'final_weekly_income_bonus', 0), 0)
        self.assertGreaterEqual(values[P + 'weekly_balance'], 100)

    def test_business_center_adds_at_least_six_net_weekly_without_low_caps(self):
        for count in (0, 4, 12, 24):
            with self.subTest(existing_centers=count):
                before = building_budget_fixture(business=count).scopes['A']
                after = building_budget_fixture(business=count + 1).scopes['A']
                self.assertGreaterEqual(after[P + 'weekly_balance'] - before[P + 'weekly_balance'], 6)

    def test_industrial_cluster_adds_at_least_two_net_weekly_without_low_caps(self):
        for count in (0, 4, 12, 24):
            with self.subTest(existing_clusters=count):
                before = building_budget_fixture(clusters=count).scopes['A']
                after = building_budget_fixture(clusters=count + 1).scopes['A']
                self.assertGreaterEqual(after[P + 'weekly_balance'] - before[P + 'weekly_balance'], 2)

    def test_large_network_tax_preview_matches_full_calculation_and_never_pays(self):
        for level in range(1, 6):
            cached = building_budget_fixture(business=25, clusters=15)
            cached.scopes['A'][P + 'tax_burden_mode'] = level
            cached.run(P + 'recalculate_tax_dependent_income')
            full = building_budget_fixture(business=25, clusters=15)
            full.scopes['A'][P + 'tax_burden_mode'] = level
            full.run(P + 'calculate_income')
            self.assertAlmostEqual(cached.scopes['A'][P + 'monthly_income'], full.scopes['A'][P + 'monthly_income'])
            self.assertEqual(cached.scopes['A'][P + 'treasury'], 100)

    def test_large_weekly_surplus_reaches_cash_exactly_thirteen_times(self):
        f = building_budget_fixture()
        f.stubs.update(P + suffix for suffix in (
            'update_debt_state_after_settlement', 'queue_debt_notification',
        ))
        balance = f.scopes['A'][P + 'weekly_balance']
        self.assertGreaterEqual(balance, 100)
        for _ in range(13):
            f.run(P + 'apply_weekly_balance')
        self.assertAlmostEqual(f.scopes['A'][P + 'treasury'], 100 + 13 * balance)
        self.assertAlmostEqual(f.scopes['A'][P + 'last_period_unexplained_delta'], 0)
        self.assertEqual(f.scopes['A'][P + 'debt'], 600)

    def test_no_custom_buildings_does_not_get_a_free_weekly_bonus(self):
        f = building_budget_fixture(business=0, clusters=0, science=0)
        self.assertLess(f.scopes['A'][P + 'weekly_balance'], 25)
        self.assertEqual(f.scopes['A'][P + 'treasury'], 100)
'''

path = Path('tools/tests/test_adiscord_economy_rebalance.py')
text = path.read_text(encoding='utf-8')
marker = '\n\nif __name__ == "__main__":'
assert text.count(marker) == 1 and 'class BuildingIncomeTests' not in text
path.write_text(text.replace(marker, '\n' + ADDITIONS + marker), encoding='utf-8')
