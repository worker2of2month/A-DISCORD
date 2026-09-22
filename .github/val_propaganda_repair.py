from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path.cwd()
BASE = '904e95637e8af82830eb94f2fe2683bd6c9a840e'
OUT = Path('/tmp/val-propaganda-review')
OUT.mkdir(exist_ok=True)
FOCUS = 'common/national_focus/ADISCORD_national_focus_VAL.txt'
DECISIONS = 'common/decisions/ADISCORD_VAL_decisions.txt'
CATEGORIES = 'common/decisions/categories/ADISCORD_VAL_rework_categories.txt'
TEST = 'tools/tests/test_val_contract_ui.py'
LOCS = {lang: f'localisation/{lang}/ADISCORD_VAL_decisions_l_{lang}.yml' for lang in ('russian', 'english')}
FILES = [FOCUS, DECISIONS, *LOCS.values(), TEST]
CAMPAIGNS = ('VAL_campaign_rifles_and_bread', 'VAL_campaign_contracts_feed_families', 'VAL_campaign_no_promise_without_payment', 'VAL_campaign_the_mine_was_stolen')
TEST_ADDITION = r'''

class TestValPropagandaRewards(unittest.TestCase):
    campaigns = (
        "VAL_campaign_rifles_and_bread",
        "VAL_campaign_contracts_feed_families",
        "VAL_campaign_no_promise_without_payment",
        "VAL_campaign_the_mine_was_stolen",
    )

    def focus(self, focus_id: str) -> str:
        text = read("common/national_focus/ADISCORD_national_focus_VAL.txt")
        matches = list(re.finditer(rf"\bid\s*=\s*{re.escape(focus_id)}\b", text))
        self.assertEqual(len(matches), 1, focus_id)
        starts = list(re.finditer(r"(?m)^\s*focus\s*=\s*\{", text[:matches[0].start()]))
        self.assertTrue(starts, focus_id)
        return named_block(text[starts[-1].start():], "focus")

    def decision(self, decision_id: str) -> str:
        category = named_block(read("common/decisions/ADISCORD_VAL_decisions.txt"), "VAL_contract_management")
        return named_block(category, decision_id)

    def number(self, text: str, key: str) -> float:
        values = re.findall(rf"(?m)^\s*{re.escape(key)}\s*=\s*(-?\d+(?:\.\d+)?)\s*$", text)
        self.assertEqual(len(values), 1, key)
        return float(values[0])

    def test_ministry_funds_any_initial_campaign_and_lists_its_unlocks(self) -> None:
        reward = named_block(self.focus("VAL_Ministry_Of_Contract_Memory"), "completion_reward")
        self.assertRegex(reward, r"(?m)^\t{3}add_political_power = 50$")
        funds = self.number(reward, "add_political_power")
        for decision_id in self.campaigns[:3]:
            with self.subTest(decision=decision_id):
                self.assertEqual(reward.count(f"unlock_decision_tooltip = {decision_id}"), 1)
                self.assertGreaterEqual(funds, self.number(self.decision(decision_id), "cost"))
        self.assertIn("custom_effect_tooltip = VAL_campaign_mine_unlock_tt", reward)
        self.assertNotIn("unlock_decision_tooltip = VAL_campaign_the_mine_was_stolen", reward)

    def test_slot_rewards_hide_bookkeeping_and_preserve_one_time_grants(self) -> None:
        for focus_id, flag, tooltip in (
            ("VAL_Ministry_Of_Contract_Memory", "VAL_propaganda_slot_granted", "VAL_campaign_slot_granted_tt"),
            ("VAL_Two_Concurrent_Narratives", "VAL_second_propaganda_slot_granted", "VAL_campaign_second_slot_tt"),
        ):
            with self.subTest(focus=focus_id):
                reward = named_block(self.focus(focus_id), "completion_reward")
                self.assertIn(f"custom_effect_tooltip = {tooltip}", reward)
                hidden = named_block(reward, "hidden_effect")
                guarded = named_block(hidden, "if")
                self.assertIn(f"NOT = {{ has_country_flag = {flag} }}", named_block(guarded, "limit"))
                self.assertEqual(guarded.count("ADISCORD_campaign_slot_grant = yes"), 1)
                self.assertEqual(guarded.count(f"set_country_flag = {flag}"), 1)
                visible = reward.replace(hidden, "")
                self.assertNotIn("ADISCORD_campaign_slot_grant", visible)
                self.assertNotIn("set_country_flag", visible)
        self.assertLessEqual(self.number(self.focus("VAL_Two_Concurrent_Narratives"), "cost"), self.number(self.focus("VAL_Ministry_Of_Contract_Memory"), "cost"))

    def test_campaign_unlock_is_independent_of_quarterly_category_visibility(self) -> None:
        category = named_block(read("common/decisions/categories/ADISCORD_VAL_rework_categories.txt"), "VAL_contract_management")
        alternatives = named_block(named_block(category, "visible"), "OR")
        self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", alternatives)
        self.assertIn("has_completed_focus = VAL_Quarterly_Contract_Norm", alternatives)
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                visible = named_block(decision, "visible")
                self.assertIn("has_completed_focus = VAL_Ministry_Of_Contract_Memory", visible)
                self.assertNotIn("OR =", visible)
                self.assertNotIn("ADISCORD_has_campaign_slot", visible)
                available = named_block(decision, "available")
                self.assertIn("tooltip = VAL_campaign_slot_available_tt", available)
                self.assertIn("ADISCORD_has_campaign_slot = yes", available)
        mine = named_block(self.decision(self.campaigns[-1]), "visible")
        self.assertIn("has_country_flag = VAL_westerholm_metal_lost", mine)

    def test_political_campaign_has_a_positive_base_return_and_refreshes_income(self) -> None:
        decision = self.decision("VAL_campaign_no_promise_without_payment")
        cost = self.number(decision, "cost")
        days = self.number(decision, "days_remove")
        modifier = named_block(decision, "modifier")
        gain = self.number(modifier, "political_power_gain")
        self.assertGreater(cost, 0)
        self.assertGreater(days * gain, cost)
        self.assertLessEqual(days * gain - cost, 15)
        self.assertGreaterEqual(self.number(decision, "days_re_enable"), days)
        self.assertEqual(self.number(modifier, "ADISCORD_economy_trade_income_factor"), 0.08)
        for effect in ("complete_effect", "remove_effect"):
            self.assertEqual(named_block(decision, effect).count("ADISCORD_economy_mark_dirty = yes"), 1)

    def test_every_campaign_uses_and_returns_one_shared_slot(self) -> None:
        for decision_id in self.campaigns:
            with self.subTest(decision=decision_id):
                decision = self.decision(decision_id)
                self.assertEqual(named_block(decision, "complete_effect").count("ADISCORD_campaign_slot_consume = yes"), 1)
                self.assertEqual(named_block(decision, "remove_effect").count("ADISCORD_campaign_slot_release = yes"), 1)
                self.assertNotIn("ADISCORD_campaign_slot_grant", decision)
                self.assertGreater(self.number(decision, "days_remove"), 0)

    def test_campaign_tooltips_and_free_slot_display_exist_in_both_languages(self) -> None:
        keys = ("VAL_campaign_slot_granted_tt", "VAL_campaign_second_slot_tt", "VAL_campaign_mine_unlock_tt", "VAL_campaign_slot_available_tt", "VAL_contract_management_desc", "VAL_Ministry_Of_Contract_Memory_desc", "VAL_Two_Concurrent_Narratives_desc", "VAL_campaign_no_promise_without_payment_desc")
        for language in ("russian", "english"):
            path = ROOT / f"localisation/{language}/ADISCORD_VAL_decisions_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            text = path.read_text(encoding="utf-8-sig")
            for key in keys:
                with self.subTest(language=language, key=key):
                    entries = re.findall(rf'(?m)^\s*{re.escape(key)}:(?:\d+)?\s+"([^"\r\n]*)"\s*$', text)
                    self.assertEqual(len(entries), 1, key)
                    self.assertTrue(entries[0])
                    if key in ("VAL_contract_management_desc", "VAL_campaign_slot_available_tt"):
                        self.assertIn("[?ADISCORD_available_campaign_slots|0]", entries[0])

    def test_campaign_files_have_no_merge_markers_or_duplicate_definitions(self) -> None:
        for path in ("common/national_focus/ADISCORD_national_focus_VAL.txt", "common/decisions/ADISCORD_VAL_decisions.txt", "common/decisions/categories/ADISCORD_VAL_rework_categories.txt"):
            text = read(path)
            self.assertNotRegex(text, r"(?m)^(?:<{7}|={7}(?:\r?$)|>{7})(?: |$)")
        decisions = read("common/decisions/ADISCORD_VAL_decisions.txt")
        for decision_id in self.campaigns:
            self.assertEqual(len(re.findall(rf"(?m)^\s*{re.escape(decision_id)}\s*=\s*\{{", decisions)), 1)
'''


def run(name, command, timeout=300):
    with (OUT / f'{name}.log').open('w') as log:
        try:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            log.write(f'\nTIMEOUT after {timeout} seconds\n')
            code = 124
    text = (OUT / f'{name}.log').read_text(errors='replace')
    failures = re.findall(r'(?m)^(?:FAIL|ERROR): (.+)$', text)
    summary = {'returncode': code, 'failures': sorted(failures), 'tail': text.splitlines()[-5:]}
    print(name, json.dumps(summary, ensure_ascii=False), flush=True)
    return summary


def replace_once(text, old, new):
    assert text.count(old) == 1, ('replacement count', old[:120], text.count(old))
    return text.replace(old, new, 1)


def edit(path, transform, encoding='utf-8'):
    before = (ROOT / path).read_bytes()
    text = before.decode(encoding)
    assert '\r' not in text, ('unexpected line endings', path)
    after = transform(text).encode(encoding)
    assert before != after, ('no change', path)
    (ROOT / path).write_bytes(after)


def failure_set(report):
    return set(report['failures'])


assert subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip() == BASE
assert not subprocess.check_output(['git', 'diff', '--name-only']).strip()
sys.path.insert(0, str(ROOT))
from tools.tests.test_val_contract_ui import named_block

focused = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui', 'tools.tests.test_validate_adiscord_val_rework', '-v']
suite = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tools/tests', '-p', 'test_*.py']
validator = [sys.executable, '-B', 'tools/validate_tc.py', '--limit', '300']
reports = {}
reports['baseline_focused'] = run('baseline-focused', focused)
reports['baseline_suite'] = run('baseline-suite', suite)
reports['baseline_validator'] = run('baseline-validator', validator)
assert not subprocess.check_output(['git', 'diff', '--name-only']).strip(), 'Baseline checks changed tracked files'
edit(TEST, lambda t: replace_once(t, '\n\nif __name__ == "__main__":', TEST_ADDITION + '\n\nif __name__ == "__main__":'))
red_cmd = [sys.executable, '-B', '-m', 'unittest', 'tools.tests.test_val_contract_ui.TestValPropagandaRewards', '-v']
reports['red'] = run('red', red_cmd)
assert reports['red']['returncode'] != 0 and reports['red']['failures']
assert not re.search(r'(?m)^ERROR:', (OUT / 'red.log').read_text())


def focus_block(text, focus_id):
    found = list(re.finditer(rf'\bid\s*=\s*{re.escape(focus_id)}\b', text))
    assert len(found) == 1
    starts = list(re.finditer(r'(?m)^\s*focus\s*=\s*\{', text[:found[0].start()]))
    assert starts
    return named_block(text[starts[-1].start():], 'focus')


def edit_focuses(text):
    for focus_id, flag, tooltip, funding in (
        ('VAL_Ministry_Of_Contract_Memory', 'VAL_propaganda_slot_granted', 'VAL_campaign_slot_granted_tt', True),
        ('VAL_Two_Concurrent_Narratives', 'VAL_second_propaganda_slot_granted', 'VAL_campaign_second_slot_tt', False),
    ):
        before = focus_block(text, focus_id)
        old = named_block(before, 'completion_reward').lstrip()
        assert old.count('ADISCORD_campaign_slot_grant = yes') == 1 and flag in old
        lines = ['completion_reward = {']
        if funding:
            lines.append('\t\t\tadd_political_power = 50')
        lines.append(f'\t\t\tcustom_effect_tooltip = {tooltip}')
        if funding:
            lines.extend(f'\t\t\tunlock_decision_tooltip = {decision}' for decision in CAMPAIGNS[:3])
            lines.append('\t\t\tcustom_effect_tooltip = VAL_campaign_mine_unlock_tt')
        lines.extend([
            '\t\t\thidden_effect = {',
            '\t\t\t\tif = {',
            f'\t\t\t\t\tlimit = {{ NOT = {{ has_country_flag = {flag} }} }}',
            '\t\t\t\t\tADISCORD_campaign_slot_grant = yes',
            f'\t\t\t\t\tset_country_flag = {flag}',
            '\t\t\t\t}',
            '\t\t\t}',
            '\t\t}',
        ])
        after = replace_once(before, old, '\n'.join(lines))
        if not funding:
            after = replace_once(after, '\t\tcost = 5\n', '\t\tcost = 3\n')
        text = replace_once(text, before, after)
    return text


edit(FOCUS, edit_focuses)


def edit_decisions(text):
    category = named_block(text, 'VAL_contract_management')
    updated = category
    for decision in CAMPAIGNS:
        before = named_block(updated, decision)
        after = before
        if decision == CAMPAIGNS[-1]:
            after = replace_once(after, 'visible = { has_country_flag = VAL_westerholm_metal_lost }', 'visible = { has_completed_focus = VAL_Ministry_Of_Contract_Memory has_country_flag = VAL_westerholm_metal_lost }')
        else:
            assert not re.search(r'\bvisible\s*=', after)
            after = replace_once(after, '\t\tallowed = { tag = VAL }\n', '\t\tallowed = { tag = VAL }\n\t\tvisible = { has_completed_focus = VAL_Ministry_Of_Contract_Memory }\n')
        after = replace_once(after, 'available = { ADISCORD_has_campaign_slot = yes }', 'available = {\n\t\t\tcustom_trigger_tooltip = {\n\t\t\t\ttooltip = VAL_campaign_slot_available_tt\n\t\t\t\tADISCORD_has_campaign_slot = yes\n\t\t\t}\n\t\t}')
        if decision == CAMPAIGNS[2]:
            after = replace_once(after, '\t\tcost = 40\n', '\t\tcost = 15\n')
            after = replace_once(after, 'political_power_gain = 0.10', 'political_power_gain = 0.50')
        updated = replace_once(updated, before, after)
    return replace_once(text, category, updated)


edit(DECISIONS, edit_decisions)
translations = {
    'russian': {
        'VAL_Ministry_Of_Contract_Memory_desc': 'Государству нужны не только винтовки, но и право объяснять, почему каждый новый контракт был неизбежен. Министерство откроет постоянный слот пропагандистских кампаний и получит политический ресурс на их запуск.',
        'VAL_Two_Concurrent_Narratives_desc': 'Расширенное бюро сможет вести две кампании одновременно. Каждая требует отдельного финансирования; после завершения кампании её слот снова становится доступен.',
        'VAL_campaign_no_promise_without_payment_desc': 'За £political_power_texticon §Y15§! превратить деловую репутацию в политический и торговый ресурс. На §Y45 дней§!: §G+0.50§! политической власти в день и §G+8%§! торгового дохода. Кампания занимает один слот до завершения.',
        'VAL_campaign_slot_granted_tt': 'Постоянно добавляет §G+1§! слот пропагандистских кампаний в категории §Y«$VAL_contract_management$»§!. Слот освобождается после завершения кампании.',
        'VAL_campaign_second_slot_tt': 'Постоянно добавляет ещё §G+1§! слот: теперь можно вести §Yдве кампании одновременно§!. Каждая оплачивается отдельно.',
        'VAL_campaign_mine_unlock_tt': 'Кампания §Y$VAL_campaign_the_mine_was_stolen$§! станет доступна после потери воркерландских поставок металла.',
        'VAL_campaign_slot_available_tt': 'Есть свободный слот кампаний. Сейчас свободно: §Y[?ADISCORD_available_campaign_slots|0]§!. Занятый слот освободится после завершения кампании.',
        '_slot_summary': 'Свободные слоты кампаний: §Y[?ADISCORD_available_campaign_slots|0]§!. §Y$VAL_Ministry_Of_Contract_Memory$§! открывает первый слот; §Y$VAL_Two_Concurrent_Narratives$§! - второй. Каждая активная кампания занимает один слот до завершения.',
    },
    'english': {
        'VAL_Ministry_Of_Contract_Memory_desc': 'The state needs more than rifles: it needs to explain why every new contract was necessary. The ministry establishes a permanent propaganda campaign slot and provides the political resources to launch a campaign.',
        'VAL_Two_Concurrent_Narratives_desc': 'The expanded bureau can run two campaigns at the same time. Each requires its own funding and releases its slot when it ends.',
        'VAL_campaign_no_promise_without_payment_desc': 'Spend £political_power_texticon §Y15§! to turn our business reputation into political and commercial influence. For §Y45 days§!: §G+0.50§! daily political power and §G+8%§! trade income. The campaign occupies one slot until it ends.',
        'VAL_campaign_slot_granted_tt': 'Permanently adds §G+1§! propaganda campaign slot in §Y$VAL_contract_management$§!. The slot becomes available again when its campaign ends.',
        'VAL_campaign_second_slot_tt': 'Permanently adds another §G+1§! slot, allowing §Ytwo campaigns at the same time§!. Each campaign is funded separately.',
        'VAL_campaign_mine_unlock_tt': '§Y$VAL_campaign_the_mine_was_stolen$§! becomes available after losing the Vorkerland metal supply.',
        'VAL_campaign_slot_available_tt': 'A campaign slot is available. Currently free: §Y[?ADISCORD_available_campaign_slots|0]§!. An occupied slot becomes available when its campaign ends.',
        '_slot_summary': 'Free campaign slots: §Y[?ADISCORD_available_campaign_slots|0]§!. §Y$VAL_Ministry_Of_Contract_Memory$§! unlocks the first slot; §Y$VAL_Two_Concurrent_Narratives$§! unlocks the second. Each active campaign occupies one slot until it ends.',
    },
}


def localize(text, values):
    for key, value in values.items():
        if key.startswith('_'):
            continue
        pattern = re.compile(rf'(?m)^ {re.escape(key)}:(?:\d+)?\s+"[^\r\n]*"$')
        matches = list(pattern.finditer(text))
        assert len(matches) <= 1, key
        if key.endswith('_desc'):
            assert len(matches) == 1, key
        line = f' {key}:0 "{value}"'
        if matches:
            text = pattern.sub(lambda m: line, text)
        else:
            anchor = re.search(r'(?m)^ VAL_Ministry_Of_Contract_Memory_desc:[^\r\n]*$', text)
            assert anchor
            text = text[:anchor.end()] + '\n' + line + text[anchor.end():]
    pattern = re.compile(r'(?m)^( VAL_contract_management_desc:(?:\d+)?\s+")([^\r\n]*)(")$')
    assert len(list(pattern.finditer(text))) == 1
    return pattern.sub(lambda m: m[1] + m[2] + r'\n\n' + values['_slot_summary'] + m[3], text)


for language, path in LOCS.items():
    edit(path, lambda t, lang=language: localize(t, translations[lang]), 'utf-8-sig')
reports['green'] = run('green', red_cmd)
assert reports['green']['returncode'] == 0, 'New regression tests failed'
reports['final_focused'] = run('final-focused', focused)
reports['final_suite'] = run('final-suite', suite)
reports['final_validator'] = run('final-validator', validator)
for kind in ('focused', 'suite'):
    before, after = reports[f'baseline_{kind}'], reports[f'final_{kind}']
    assert before['returncode'] != 124 and after['returncode'] != 124, (kind, 'timeout')
    introduced = failure_set(after) - failure_set(before)
    assert not introduced, (kind, sorted(introduced))
    if before['returncode'] == 0:
        assert after['returncode'] == 0, kind
    elif after['returncode'] != 0:
        assert after['failures'], (kind, 'unclassified failure')
if reports['baseline_validator']['returncode'] == 0:
    assert reports['final_validator']['returncode'] == 0
else:
    before = (OUT / 'baseline-validator.log').read_text()
    after = (OUT / 'final-validator.log').read_text()
    errors = lambda t: set(re.findall(r'(?mi)^.*(?:\berrors?\b|\bfatal\b).*$', t))
    assert errors(after) <= errors(before), sorted(errors(after) - errors(before))
subprocess.run(['git', 'diff', '--check'], check=True)
actual = subprocess.check_output(['git', 'diff', '--name-only']).decode().splitlines()
assert set(actual) == set(FILES), actual
(OUT / 'patch.diff').write_bytes(subprocess.check_output(['git', 'diff', '--', *FILES]))
manifest = {'base': BASE, 'files': {}, 'reports': reports, 'native_runtime_tested': False}
for path in FILES:
    data = (ROOT / path).read_bytes()
    assert (data.startswith(b'\xef\xbb\xbf')) == path.endswith('.yml'), path
    manifest['files'][path] = hashlib.sha256(data).hexdigest()
    target = OUT / 'source' / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
subprocess.run(['git', 'config', 'user.name', 'A-Discord maintenance'], check=True)
subprocess.run(['git', 'config', 'user.email', 'noreply@openai.com'], check=True)
messages = [
    'fix(val): fund Ministry campaigns and explain permanent slot rewards',
    'fix(val): gate campaigns on the Ministry and balance political returns',
    'l10n(ru): explain Kefreyt campaign slots and startup funding',
    'l10n(en): explain Kefreyt campaign slots and startup funding',
    'test(val): cover usable propaganda rewards and campaign accounting',
]
manifest['commits'] = []
for path, message in zip(FILES, messages):
    subprocess.run(['git', 'add', '--', path], check=True)
    subprocess.run(['git', 'commit', '-m', message], check=True)
    manifest['commits'].append({'path': path, 'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()})
branch = 'codex/val-propaganda-delivery-' + os.environ['GITHUB_RUN_ID']
head = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
subprocess.run(['git', 'push', 'origin', head + ':refs/heads/' + branch], check=True)
manifest.update(head=head, branch=branch)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
print('DELIVERY', json.dumps({'head': head, 'branch': branch, 'base': BASE, 'commits': manifest['commits']}, ensure_ascii=False), flush=True)
print('VERIFICATION', json.dumps(reports, ensure_ascii=False), flush=True)
