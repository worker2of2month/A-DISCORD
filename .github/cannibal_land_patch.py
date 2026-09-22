from pathlib import Path
import ast, json, re, subprocess, sys, textwrap

root = Path.cwd()
logs = Path('/tmp/cannibal-land-qa')
logs.mkdir(exist_ok=True)
paths = [
    'common/scripted_effects/ADISCORD_vorkerland_effects.txt',
    'common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt',
    'tools/lib/vorkerland_collapse_manifest.py',
    'tools/tests/test_validate_adiscord_vorkerland_collapse.py',
]
for name in paths:
    for parent in (root/name).parents:
        if parent == root:
            break
        rules = parent/'AGENTS.md'
        if rules.exists():
            raise RuntimeError(f'Additional repository rules need review: {rules}\n{rules.read_text()}')
originals = {name: (root/name).read_bytes() for name in paths}
base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
print('BASE', base, flush=True)

def run(label, command, timeout=300):
    path = logs/f'{label}.log'
    timed_out = False
    with path.open('w') as stream:
        try:
            result = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            timed_out = True
    output = path.read_text(errors='replace')
    print(label, 'EXIT', code, 'TIMEOUT', timed_out, flush=True)
    print('\n'.join(output.splitlines()[-18:]), flush=True)
    return code, output

modules = ['tools.tests.test_validate_adiscord_vorkerland_collapse', 'tools.tests.test_val_contract_ui']
modules += ['tools.tests.'+p.stem for p in sorted((root/'tools/tests').glob('*exclusion_zone_boundar*.py'))]
focused = [sys.executable, '-B', '-m', 'unittest', *modules, '-v']
baseline_focused = run('focused-before', focused)
validator = [sys.executable, '-B', '-m', 'tools.validators.validate_tc', '--limit', '300']
baseline_validator = run('validator-before', validator)

tests = r'''
class NorthernLandContaminationTests(unittest.TestCase):
    states = set(range(58, 66))
    effects_path = "common/scripted_effects/ADISCORD_vorkerland_effects.txt"

    def test_northern_tribal_land_is_excluded_from_dirty_bootstrap(self):
        from tools.lib.vorkerland_collapse_manifest import CONTAMINATED_STATES, DIRTY_GROUPS
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        self.assertFalse(self.states & CONTAMINATED_STATES)
        block = named_block(read(self.effects_path), "ADISCORD_vorkerland_apply_dirty_modifiers")
        applied = {int(entry.key) for entry in parse_clausewitz(block)[0].value}
        self.assertFalse(self.states & applied)
        self.assertEqual(applied, CONTAMINATED_STATES)
        self.assertTrue({24, 57} <= applied)
        self.assertTrue({state for group in DIRTY_GROUPS.values() for state in group} <= applied)

    def test_northern_tribal_provinces_have_ordinary_terrain(self):
        terrain = {}
        for line in read("map/definition.csv").splitlines():
            fields = line.split(";")
            if fields[0].isdigit() and len(fields) > 6:
                terrain[int(fields[0])] = fields[6]
        found = set()
        for path in (ROOT / "history/states").glob("*.txt"):
            source = path.read_text(encoding="utf-8-sig")
            match = re.search(r"\bid\s*=\s*(\d+)", source)
            if not match or int(match.group(1)) not in self.states:
                continue
            state = int(match.group(1))
            found.add(state)
            provinces = re.search(r"\bprovinces\s*=\s*\{([^}]*)\}", source)
            self.assertIsNotNone(provinces)
            for province in map(int, re.findall(r"\d+", provinces.group(1))):
                self.assertNotEqual(terrain[province], "contaminated", (state, province))
        self.assertEqual(found, self.states)

    def test_northern_save_cleanup_is_ungated_bounded_and_owner_independent(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz

        source = read(self.effects_path)
        cleanup_id = "ADISCORD_vorkerland_clear_northern_dirty_modifiers"
        helper_id = "ADISCORD_vorkerland_remove_dirty_state_modifier"
        dirty_id = "ADISCORD_vorkerland_dirty_state"
        self.assertTrue(re.search(r"(?m)^" + cleanup_id + r"\s*=\s*\{", source), "missing northern cleanup")
        cleanup = parse_clausewitz(named_block(source, cleanup_id))[0].value
        self.assertEqual({entry.key for entry in cleanup}, {str(state) for state in self.states})
        self.assertEqual(len(cleanup), len(self.states))
        for entry in cleanup:
            self.assertEqual([(call.key, call.value) for call in entry.value], [(helper_id, "yes")])
        helper = parse_clausewitz(named_block(source, helper_id))[0].value
        self.assertEqual([entry.key for entry in helper], ["if"])
        branch = helper[0].value
        self.assertEqual([entry.key for entry in branch], ["limit", "remove_dynamic_modifier", "owner"])
        self.assertEqual([entry.key for entry in branch[0].value], ["has_dynamic_modifier"])
        guard = branch[0].value[0].value
        self.assertEqual([(entry.key, entry.value) for entry in guard], [("modifier", dirty_id)])
        self.assertEqual([(entry.key, entry.value) for entry in branch[1].value], [("modifier", dirty_id)])
        self.assertEqual([(entry.key, entry.value) for entry in branch[2].value], [("ADISCORD_economy_mark_dirty", "yes")])
        startup = parse_clausewitz(named_block(read("common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt"), "on_startup"))[0].value
        payload = next(entry.value for entry in startup if entry.key == "effect")
        self.assertEqual([entry.value for entry in payload if entry.key == cleanup_id], ["yes"])


'''
test_path = root/paths[3]
before = test_path.read_text(encoding='utf-8')
marker = 'class VorkerlandCollapseValidatorTests(unittest.TestCase):'
assert before.count(marker) == 1 and 'class NorthernLandContaminationTests' not in before
test_path.write_text(before.replace(marker, textwrap.dedent(tests).lstrip()+marker), encoding='utf-8')
red_command = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_validate_adiscord_vorkerland_collapse.NorthernLandContaminationTests', '-v']
red = run('regression-red', red_command)
assert red[0] == 1 and 'FAILED (failures=2)' in red[1] and 'ERROR:' not in red[1], red[1]

manifest = root/paths[2]
before = manifest.read_text(encoding='utf-8')
old = '23, 24, 49, 51, 57, 59, 60, 125'
assert before.count(old) == 1
manifest.write_text(before.replace(old, '23, 24, 49, 51, 57, 125'), encoding='utf-8')

script = root/paths[0]
before = script.read_text(encoding='utf-8')
for state in (59, 60):
    line = f'    {state} = {{ ADISCORD_vorkerland_apply_dirty_state_modifier = yes }}\n'
    assert before.count(line) == 1
    before = before.replace(line, '')
cleanup = '# Northern tribal land stays outside the contaminated belt regardless of its owner.\n'
cleanup += 'ADISCORD_vorkerland_clear_northern_dirty_modifiers = {\n'
cleanup += ''.join(f'\t{state} = {{ ADISCORD_vorkerland_remove_dirty_state_modifier = yes }}\n' for state in range(58, 66))
cleanup += '}\n\n'
cleanup += '''ADISCORD_vorkerland_remove_dirty_state_modifier = {
\tif = {
\t\tlimit = { has_dynamic_modifier = { modifier = ADISCORD_vorkerland_dirty_state } }
\t\tremove_dynamic_modifier = { modifier = ADISCORD_vorkerland_dirty_state }
\t\towner = { ADISCORD_economy_mark_dirty = yes }
\t}
}

'''
marker = '# --- collapse_dirty_effects ---\n'
assert before.count(marker) == 1
script.write_text(before.replace(marker, marker+cleanup), encoding='utf-8')

hooks = root/paths[1]
before = hooks.read_text(encoding='utf-8')
marker = '\ton_startup = {\n\t\teffect = {\n'
assert before.count(marker) == 1
hooks.write_text(before.replace(marker, marker+'\t\t\tADISCORD_vorkerland_clear_northern_dirty_modifiers = yes\n'), encoding='utf-8')

for name in paths:
    assert not (root/name).read_bytes().startswith(b'\xef\xbb\xbf'), name
for name in paths[2:]:
    ast.parse((root/name).read_text(encoding='utf-8'))

green = run('regression-green', red_command)
assert green[0] == 0, green[1]
focused_after = run('focused-after', focused)
validator_after = run('validator-after', validator)

def failures(output):
    return set(re.findall(r'^(?:FAIL|ERROR): .+$', output, re.MULTILINE))
assert focused_after[0] == baseline_focused[0] == 0 or (focused_after[0] != 124 and failures(focused_after[1]) == failures(baseline_focused[1]) and failures(focused_after[1])), 'Focused regressions changed'
assert validator_after == baseline_validator or validator_after[0] == baseline_validator[0] == 0, 'Validator findings changed'

full_command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py']
full_after = run('suite-after', full_command, timeout=360)
full_before = None
if full_after[0] != 0:
    patched = {name: (root/name).read_bytes() for name in paths}
    try:
        for name, content in originals.items():
            (root/name).write_bytes(content)
        full_before = run('suite-before', full_command, timeout=360)
    finally:
        for name, content in patched.items():
            (root/name).write_bytes(content)
    if full_after[0] != 124:
        assert full_before[0] != 124 and failures(full_after[1]) == failures(full_before[1]) and failures(full_after[1]), 'New full-suite regression'
    else:
        assert full_before[0] == 124, 'Only modified suite timed out'

subprocess.run(['git', 'diff', '--check'], check=True)
changed = set(subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines())
assert changed == set(paths), changed
patch = subprocess.check_output(['git', 'diff', '--', *paths], text=True)
(logs/'change.diff').write_text(patch)
print(patch, flush=True)
report = {'base': base, 'regression_tests': '3 passed', 'focused_before': baseline_focused[0], 'focused_after': focused_after[0], 'validator_before': baseline_validator[0], 'validator_after': validator_after[0], 'suite_after': full_after[0], 'suite_before': full_before[0] if full_before else None, 'baseline_failures': sorted(failures(full_after[1]))}
(logs/'report.json').write_text(json.dumps(report, indent=2))
print('REPORT', json.dumps(report), flush=True)
subprocess.run(['git', 'add', '--', *paths], check=True)
subprocess.run(['git', '-c', 'user.name=github-actions[bot]', '-c', 'user.email=41898282+github-actions[bot]@users.noreply.github.com', 'commit', '-m', 'fix: keep northern tribal lands free of contamination'], check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD:refs/heads/fix/cannibal-clean-land-result'], check=True)
print('VERIFIED_COMMIT', subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(), flush=True)
