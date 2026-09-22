from decimal import Decimal
from pathlib import Path
import re
import subprocess

modules = ['tools.tests.test_adiscord_stp_party_survival', 'tools.tests.test_adiscord_stp_party_route', 'tools.tests.test_adiscord_stp_party_balance', 'tools.tests.test_adiscord_stp_party_qol']

def run(label, targets, expect_success=True):
    result = subprocess.run(['python', '-B', '-m', 'unittest', *targets], capture_output=True, text=True)
    text = result.stdout + result.stderr
    Path('/tmp/packet2-review-' + label + '.txt').write_text(text)
    print(label, text[-6000:], flush=True)
    if expect_success:
        assert result.returncode == 0, label
    else:
        assert result.returncode != 0 and 'ERROR:' not in text, label
    return text

run('before', modules)
path = Path('tools/tests/test_adiscord_stp_party_route.py')
text = path.read_text()
addition = '''
    def test_coalition_tooltips_match_the_sixty_percent_cap(self):
        for language in ('russian', 'english'):
            text = read(f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
            for faction in self.KEYS:
                key = 'STP_pf_' + faction + '_deal_tt'
                value = next(line for line in text.splitlines() if line.startswith(' ' + key + ':'))
                self.assertNotIn('до 100%', value)
                self.assertNotIn('up to 100%', value)
                self.assertIn('60%', value)
                self.assertIn('+12', value)
                self.assertIn('-12', value)

    def test_fixed_point_cap_and_legacy_shares_do_not_drift(self):
        from decimal import Decimal, ROUND_DOWN
        quantum = Decimal('0.001')
        for faction in self.KEYS:
            for initial in ('59.999', '60.000', '65.001', '99.999', '100.000'):
                with self.subTest(faction=faction, initial=initial):
                    values, flags = self.simulate('STP_pf_initialize')
                    old = Decimal(initial)
                    others = [k for k in self.KEYS if k != faction]
                    share = ((100 - old) / 6).quantize(quantum, rounding=ROUND_DOWN)
                    for k in others:
                        values[f'STP_pf_{k}_influence'] = share
                    values[f'STP_pf_{others[-1]}_influence'] = 100 - old - 5 * share
                    values[f'STP_pf_{faction}_influence'] = old
                    values['STP_pf_selected'] = self.KEYS.index(faction) + 1
                    self.simulate('STP_pf_shift', values, flags, quantize=True)
                    self.assertEqual(values[f'STP_pf_{faction}_influence'], max(old, Decimal(60)))
                    self.assertEqual(sum(values[f'STP_pf_{k}_influence'] for k in self.KEYS), 100)
                    self.assertTrue(all(values[f'STP_pf_{k}_influence'] >= 0 for k in self.KEYS))
'''
marker = 'if __name__ == "__main__":'
assert text.count(marker) == 1
text = text.replace(marker, addition.rstrip() + '\n\n\n' + marker)
path.write_text(text)
run('red', ['tools.tests.test_adiscord_stp_party_route.PartySecondPackageContracts.test_coalition_tooltips_match_the_sixty_percent_cap', 'tools.tests.test_adiscord_stp_party_route.PartySecondPackageContracts.test_fixed_point_cap_and_legacy_shares_do_not_drift'], False)

path = Path('common/scripted_effects/ADISCORD_STP_scripted_effects.txt')
text = path.read_text()
start = text.index('STP_pf_shift = {')
end = text.index('\nSTP_pf_clear = {', start)
shift = text[start:end]
old = 'var = STP_pf_room value = 0 compare = greater_than'
assert shift.count(old) == 1
shift = shift.replace(old, 'var = STP_pf_gain value = 0 compare = greater_than')
pattern = r'(?m)^\t\tif = \{ limit = \{ check_variable = \{ var = STP_pf_selected value = [1-7] compare = equals \} \} add_to_variable = \{ var = STP_pf_\w+_influence value = STP_pf_remainder \} \}\n'
assert len(re.findall(pattern, shift)) == 7
shift = re.sub(pattern, '', shift)
marker = '\t\tSTP_refresh_apparatus_loyalty = yes'
assert shift.count(marker) == 1
replacement = '''		# Keep rounding residue outside the selected faction's capped share.
		if = {
			limit = { check_variable = { var = STP_pf_selected value = 1 compare = equals } }
			add_to_variable = { var = STP_pf_borons_influence value = STP_pf_remainder }
		}
		else = { add_to_variable = { var = STP_pf_conservatives_influence value = STP_pf_remainder } }
'''
shift = shift.replace(marker, replacement + marker)
path.write_text(text[:start] + shift + text[end:])

for language in ('russian', 'english'):
    path = Path(f'localisation/{language}/ADISCORD_STP_l_{language}.yml')
    assert path.read_bytes().startswith(b'\xef\xbb\xbf')
    text = path.read_text(encoding='utf-8-sig')
    lines = text.splitlines()
    changed = 0
    for i, line in enumerate(lines):
        if re.match(r'^ STP_pf_\w+_deal_tt:', line):
            original = line
            line = line.replace('до 100%', 'до 60%').replace('up to 100%', 'up to 60%')
            line = line.replace('влияние §Y+5 п.п.§!', 'влияние до §Y+5 п.п.§!').replace('influence §Y+5 percentage points§!', 'influence up to §Y+5 percentage points§!')
            assert line != original
            lines[i] = line
            changed += 1
    assert changed == 7, (language, changed)
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8-sig')

path = Path('docs/development/focus-effects.md')
text = path.read_text()
text += '\nНулевой прирост влияния не запускает пропорциональный пересчёт: это предотвращает\nдрейф старых долей при фиксированной точности. Остаток округления возвращается\nневыбранной группе, поэтому выбранная доля не превышает потолок за счёт округления.\n'
path.write_text(text)
run('after', modules)
subprocess.run(['git', 'diff', '--check'], check=True)
print('FINAL_REVIEW_PASSED', flush=True)
