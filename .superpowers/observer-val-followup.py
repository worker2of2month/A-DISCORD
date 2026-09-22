from pathlib import Path
import json, os, re, signal, subprocess, sys
sys.path.insert(0, str(Path.cwd()))
from tools.tests.test_val_contract_ui import named_block

report = {'checks': {}, 'runtime_tested': False}
def run(name, command, timeout=90):
    p = Path('/tmp/' + name + '.log')
    with p.open('w') as out:
        proc = subprocess.Popen(command, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
        try: code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait(); code = 124
            out.write('\nTIMEOUT\n')
    text = p.read_text(errors='replace')
    report['checks'][name] = {'returncode': code, 'problems': re.findall(r'(?m)^(?:FAIL|ERROR): .+$', text), 'early_problems': re.findall(r'(?m)^test_.*(?:FAIL|ERROR).*$', text), 'tail': text[-3500:]}
    Path('/tmp/observer-val-followup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(name, code, text[-1500:], flush=True)
    return code, text

tests = Path('tools/tests/test_val_contract_ui.py')
before = tests.read_bytes()
addition = r'''

class TestValProgressionContinuation(unittest.TestCase):
    def refusal(self):
        source = read("events/ADISCORD_VAL_contract_events.txt")
        marker = source.index("id = val_rework.111\n")
        return named_block(source[source.rfind("country_event", 0, marker):], "country_event")

    def test_proclamation_category_is_visible_from_its_unlock(self):
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_postwar_administration")
        visible = named_block(category, "visible")
        for focus in ("VAL_frontier_conference", "VAL_Contracts_Outlive_Kings"):
            self.assertIn("has_completed_focus = " + focus, visible)
        self.assertIn("OR =", visible)

    def test_refusal_event_selects_the_same_safe_withdrawal_as_the_decision(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.withdraw")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        reward = named_block(option, "hidden_effect")
        self.assertIn("VAL_frontier_reply_is_current = yes", reward)
        self.assertIn("VAL_frontier_withdraw_and_defer = yes", reward)
        self.assertNotIn("VAL_frontier_close = yes", reward)
        self.assertIn("custom_effect_tooltip = VAL_frontier_withdraw_tt", option)

    def test_ai_refusal_event_uses_the_same_force_gate_as_decisions(self):
        event = self.refusal()
        marker = event.index("name = val_rework.111.war")
        option = named_block(event[event.rfind("option", 0, marker):], "option")
        chance = named_block(option, "ai_chance")
        self.assertIn("VAL_ai_frontier_force_ready = no", chance)
        self.assertNotIn("num_divisions < 24", chance)

    def test_opt_out_and_recovery_evaluate_the_real_trigger_graph(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        definitions = {e.key: e.value for e in parse_clausewitz(read("common/scripted_triggers/ADISCORD_VAL_rework_triggers.txt"))}
        flags, focuses = set(), {"VAL_frontier_security_plan"}
        facts = {"has_war": False, "is_subject": False, "has_capitulated": False,
                 "VAL_frontier_stage": 0, "VAL_campaign_objectives_met": False}

        def evaluate(entry):
            key, value = entry.key, entry.value
            if key in ("OR", "AND", "NOT"):
                result = [evaluate(e) for e in value]
                return any(result) if key == "OR" else (not all(result) if key == "NOT" else all(result))
            if key == "has_country_flag": return value in flags
            if key == "has_completed_focus": return value in focuses
            if key == "tag": return value == "VAL"
            if key in ("has_war", "is_subject", "has_capitulated", "VAL_campaign_objectives_met"):
                return facts[key] == (value == "yes")
            if key == "check_variable":
                data = {e.key: e.value for e in value}
                self.assertEqual(data["compare"], "greater_than")
                return facts.get(data["var"], 0) > float(data["value"])
            if key in definitions:
                self.assertIn(value, ("yes", "no"))
                return all(evaluate(e) for e in definitions[key]) == (value == "yes")
            self.fail("Unimplemented trigger in this fixture: " + key)

        def check(name): return all(evaluate(e) for e in definitions[name])
        self.assertTrue(check("VAL_can_defer_northern_expansion"))
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.add("VAL_frontier_expansion_deferred")
        self.assertFalse(check("VAL_can_defer_northern_expansion"))
        self.assertTrue(check("VAL_northern_expansion_deferred"))
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Returning_Buyers")
        self.assertFalse(check("VAL_economic_settlement_ready"))
        focuses.add("VAL_Contingency_Ledgers")
        self.assertTrue(check("VAL_economic_settlement_ready"))
        for key in ("has_war", "is_subject", "has_capitulated"):
            with self.subTest(blocker=key):
                facts[key] = True
                self.assertFalse(check("VAL_northern_expansion_deferred"))
                self.assertFalse(check("VAL_economic_settlement_ready"))
                facts[key] = False
        for stage in (1, 2, 3):
            facts["VAL_frontier_stage"] = stage
            self.assertFalse(check("VAL_northern_expansion_deferred"))
        facts["VAL_frontier_stage"] = 0
        for flag in ("VAL_campaign_mobilizing", "VAL_stelander_defeated"):
            flags.add(flag)
            self.assertFalse(check("VAL_economic_settlement_ready"))
            flags.remove(flag)
        focuses.remove("VAL_frontier_security_plan")
        self.assertFalse(check("VAL_northern_expansion_deferred"))
        flags.clear()
        facts["VAL_campaign_objectives_met"] = True
        self.assertTrue(check("VAL_economic_settlement_ready"))
'''
assert 'class TestValProgressionContinuation' not in before.decode()
tests.write_bytes(before + addition.encode())
command = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui.TestValProgressionContinuation', '-v']
code, output = run('continuation_red', command)
assert code == 1 and 'FAILED (failures=3)' in output and 'ERROR:' not in output, output

category_path = Path('common/decisions/categories/ADISCORD_VAL_rework_categories.txt')
text = category_path.read_text()
old = named_block(text, 'VAL_postwar_administration')
new = old.replace('visible = { has_completed_focus = VAL_frontier_conference }', 'visible = { OR = { has_completed_focus = VAL_frontier_conference has_completed_focus = VAL_Contracts_Outlive_Kings } }')
assert old != new
category_path.write_text(text.replace(old, new, 1))

path = Path('events/ADISCORD_VAL_contract_events.txt')
text = path.read_text()
marker = text.index('id = val_rework.111\n')
old = named_block(text[text.rfind('country_event', 0, marker):], 'country_event')
new = old.replace('modifier = { factor = 0 num_divisions < 24 }', 'modifier = { factor = 0 VAL_ai_frontier_force_ready = no }')
new = new.replace('limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } }', 'limit = { check_variable = { var = VAL_frontier_stage value = 2 compare = equals } VAL_frontier_reply_is_current = yes }')
assert new.count('VAL_frontier_close = yes') == 1
new = new.replace('VAL_frontier_close = yes', 'VAL_frontier_withdraw_and_defer = yes')
new = new.replace('ai_chance = { base = 30 }\n\t\thidden_effect', 'ai_chance = { base = 30 }\n\t\tcustom_effect_tooltip = VAL_frontier_withdraw_tt\n\t\thidden_effect')
assert old != new
path.write_text(text.replace(old, new, 1))
assert run('continuation_green', command)[0] == 0
full = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui.TestValProgressionChoices', 'tools.tests.test_val_contract_ui.TestValProgressionContinuation', 'tools.tests.test_adiscord_superevents_stp_empire.ObserverSupereventTimeoutTests', '-v']
assert run('all_regressions', full)[0] == 0
assert run('tc_followup', [sys.executable, '-B', 'tools/validate_tc.py', '--limit', '300'], 150)[0] == 0
run('suite_followup', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py', '-v'], 90)
assert run('final_regressions', full)[0] == 0
assert run('final_diff', ['git', 'diff', '--check'])[0] == 0
paths = [str(tests), str(category_path), str(path)]
actual = subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines()
assert set(actual) == set(paths), actual
report['paths'] = paths
subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=True)
subprocess.run(['git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com'], check=True)
subprocess.run(['git', 'add', '--', *paths], check=True)
subprocess.run(['git', 'commit', '-m', 'fix(val): complete proclamation visibility and frontier withdrawal lifecycle'], check=True)
subprocess.run(['git', 'push', 'origin', 'HEAD:fix/observer-val-ready'], check=True)
report['commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
Path('/tmp/observer-val-followup.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print('RESULT', report['commit'], flush=True)
