# Executed inside the isolated patch driver, using its checked file helpers.
source = read(validator)
old = '''    all_multipliers = [
        entry
        for _, entry in _walk_entries(effect.value)
        if entry.key == "multiply_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var")
        == "ADISCORD_economy_research_expenses"
    ]'''
new = '''    # The cached-base branch owns one fixed cost conversion before policy.
    # Only that exact, adjacent cache write is exempt from the five controls.
    base_scaling = set()
    expense = "ADISCORD_economy_research_expenses"
    cache = "ADISCORD_economy_research_expense_policy_base"
    for ancestors, entry in _walk_entries(effect.value):
        if len(ancestors) != 1 or ancestors[0].key != "else":
            continue
        owner = ancestors[0]
        if not _is_exact_variable_write(entry, "multiply_variable", expense, "2.00"):
            continue
        owner_position = effect.value.index(owner)
        if owner_position == 0:
            continue
        cached_branch = effect.value[owner_position - 1]
        cached_limit = _direct_limit(cached_branch)
        position = owner.value.index(entry)
        if (
            cached_branch.key == "if"
            and cached_limit is not None
            and _exact_check(cached_limit, "ADISCORD_economy_policy_preview_uses_cached_base_temp", "1", "greater_than_or_equals")
            and len(_direct_variable_operation(cached_branch.value, "set_variable", expense, cache)) == 1
            and len(_direct_variable_operation(owner.value, "multiply_variable", expense)) == 1
            and position + 1 < len(owner.value)
            and _is_exact_variable_write(owner.value[position + 1], "set_variable", cache, expense)
        ):
            base_scaling.add(id(entry))
    all_multipliers = [
        entry
        for _, entry in _walk_entries(effect.value)
        if entry.key == "multiply_variable"
        and isinstance(entry.value, list)
        and _direct_scalar(entry.value, "var") == expense
        and id(entry) not in base_scaling
    ]'''
node = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == 'research_policy_flow_issues')
lines = source.splitlines(keepends=True)
body = ''.join(lines[node.lineno-1:node.end_lineno])
body = once(body, old, new)
lines[node.lineno-1:node.end_lineno] = [body]
write(validator, ''.join(lines))

path = 'tools/tests/test_adiscord_economy_weekly_contracts.py'
methods = {
    'test_core_policy_and_debt_flow_negative_fixtures': {
        '("0.60", "0.80", "1.00", "1.30", "1.60")': '("0.30", "0.65", "1.00", "1.30", "1.60")',
        'ADISCORD_economy_research_expenses value = 0.60': 'ADISCORD_economy_research_expenses value = 0.30',
    },
    'test_building_tooltips_lead_with_role_and_budget_impact': {
        '+1,20': '+23,00', '-0,27': '-2,92', '+0,31': 'Почти нейтрален',
    },
    'test_economic_building_reference_documents_roles_and_formulas': {
        '1.05 + 0.25 - 0.10 = +1.20': '18 × (1.05 + 0.25) - 4 × 0.10 = +23.00',
        '0.20 - 0.35 - 0.12 = -0.27': '18 × 0.02 - 4 × (2 × 0.35 + 0.12) = -2.92',
        '0.45 + 0.16 - 0.18 - 0.12 = +0.31': '18 × (0.045 + 0.016) - 4 × (0.18 + 0.12) = -0.102',
    },
}
for name, replacements in methods.items():
    source = read(path)
    node = next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.FunctionDef) and node.name == name)
    lines = source.splitlines(keepends=True)
    body = ''.join(lines[node.lineno-1:node.end_lineno])
    for before, after in replacements.items():
        body = once(body, before, after)
    lines[node.lineno-1:node.end_lineno] = [body]
    write(path, ''.join(lines))

path = 'localisation/russian/ADISCORD_economy_l_russian.yml'
source = read(path)
source = once(source, '§YРоль: производство§!', '§YРоль: местное военное производство§!')
write(path, source)

path = 'tools/tests/test_adiscord_economy_balance.py'
method = '''
    def test_research_validator_rejects_unowned_or_duplicate_base_scaling(self):
        from tools.validators.validate_adiscord_economy_ai import block, research_policy_flow_issues
        body = block(EFFECTS, "ADISCORD_economy_calculate_research_expenses")
        self.assertEqual(research_policy_flow_issues(body), [])
        scale = "multiply_variable = { var = ADISCORD_economy_research_expenses value = 2.00 }"
        cache = "set_variable = { var = ADISCORD_economy_research_expense_policy_base value = ADISCORD_economy_research_expenses }"
        self.assertEqual(body.count(scale), 1)
        self.assertEqual(body.count(cache), 1)
        for name, mutation in (
            ("changed conversion", body.replace(scale, scale.replace("2.00", "3.00"))),
            ("duplicate conversion", body.replace(scale, scale + " " + scale)),
            ("missing cache owner", body.replace(cache, "")),
            ("unconditional extra conversion", body[:-1] + scale + "\\n}"),
        ):
            with self.subTest(case=name):
                self.assertTrue(research_policy_flow_issues(mutation))

'''
source = read(path)
source = once(source, '\nif __name__ == "__main__":', '\n' + method + '\nif __name__ == "__main__":')
write(path, source)
