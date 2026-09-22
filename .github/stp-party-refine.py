"""Align presentation contracts with their new owners and preserve local formatting."""
from pathlib import Path
import difflib
import re
import subprocess
import sys

sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz


def read(path):
    return Path(path).read_text(encoding='utf-8-sig')


def write(path, text):
    raw = Path(path).read_bytes()
    enc = 'utf-8-sig' if raw.startswith(b'\xef\xbb\xbf') else 'utf-8'
    Path(path).write_text(text, encoding=enc, newline='')


def replace_once(text, old, new):
    assert text.count(old) == 1, old
    return text.replace(old, new, 1)


path = 'common/decisions/categories/ADISCORD_decision_categories_STP.txt'
text = read(path)
text = replace_once(text, 'has_completed_focus = STP_ps_expedition_request',
                     'has_completed_focus = STP_ps_expedition_logistics')
write(path, text)

# The seven faction bargains remain distinct from government construction programmes.
path = 'tools/tests/test_adiscord_stp_party_route.py'
text = read(path)
text = replace_once(text, '        decisions = one(categories, "STP_party_factions")\n        self.assertEqual(len(decisions), 7)',
    '        decisions = [e for e in one(categories, "STP_party_factions")\n'
    '                     if e.key.startswith("STP_pf_negotiate_")]\n'
    '        self.assertEqual(len(decisions), 7)\n'
    '        self.assertEqual({e.key for e in decisions}, {f"STP_pf_negotiate_{k}" for k in self.KEYS})')
text = replace_once(text, '        self.assertIn("70", party)\n        self.assertIn("25", party)',
    '        self.assertIn("70", self.loc["STP_party_factions_desc"])\n'
    '        self.assertIn("25", self.loc["STP_party_factions_desc"])\n'
    '        self.assertNotIn("STPGetPartyPreparationReport", party)')
write(path, text)
path = 'tools/tests/test_adiscord_stp_preparation.py'
text = read(path)
text = replace_once(text, '            self.assertTrue(matches_conditions(visible, party), "Party government programs share this category")',
    '            self.assertFalse(matches_conditions(visible, party), "Government programmes moved out of the completed election panel")')
write(path, text)

# Keep actionable thresholds in the apparatus panel and remove duplicate government status.
for lang in ('russian', 'english'):
    path = f'localisation/{lang}/ADISCORD_STP_l_{lang}.yml'
    text = read(path)
    if lang == 'russian':
        threshold = ' Верность 70+ задерживает операции подполья; ниже 25 они готовятся быстрее.'
        war = '§YЗадача: сохранить управление и подготовить контрудар.§! Оперативный резерв усиливает армию; охрана сообщений - службу безопасности и снабжение. Это альтернативные курсы. Повторные программы оплачиваются отдельно.[STPGetPartySurvival]'
        recovery = '§YЗадача: восстановить страну.§! Выберите проект восстановления ниже; фракции находятся в «Президиуме и аппарате», отношения с соседями - во «Внешних связях».[STPGetRecoveryReport]'
    else:
        threshold = ' Loyalty of 70+ delays underground operations; below 25 they prepare faster.'
        war = '§YObjective: preserve government and prepare the counterattack.§! The operational reserve strengthens the army; route security prioritises the security service and supply. These are alternative courses. Further programmes are paid separately.[STPGetPartySurvival]'
        recovery = '§YObjective: rebuild the country.§! Choose a reconstruction project below. Factions are under Presidium and Apparatus; neighbouring powers are under Foreign Relations.[STPGetRecoveryReport]'
    pattern = r'(?m)^( STP_party_factions_desc:\d*\s*"[^\n]*?)(\[STPGetPartyPreparationReport\]"\s*)$'
    text, n = re.subn(pattern, lambda m: m.group(1) + threshold + m.group(2), text)
    assert n == 1, (lang, 'apparatus')
    text, n = re.subn(r'(?m)^( STP_PARTY_WAR_BRIEFING:\d*)[^\n]*$',
                     lambda m: m.group(1) + ' "' + war + '"', text)
    assert n == 1, (lang, 'war')
    text += '\n STP_PARTY_RECON_BRIEFING: "' + recovery + '"\n'
    write(path, text)
path = 'common/scripted_localisation/ADISCORD_STP_scripted_loc.txt'
text = read(path)
text = replace_once(text,
    '    name = STPGetWarCouncilBriefing\n    text = { trigger = { tag = STP }',
    '    name = STPGetWarCouncilBriefing\n'
    '    text = { trigger = { tag = STP has_country_flag = STP_cw_postwar } localization_key = STP_PARTY_RECON_BRIEFING }\n'
    '    text = { trigger = { tag = STP }')
write(path, text)
path = 'tools/tests/test_adiscord_stp_party_qol.py'
text = read(path)
text = replace_once(text, "'STP_ps_preparation_report', 'STP_PARTY_WAR_BRIEFING', 'STP_PARTY_FOREIGN_BRIEFING')",
    "'STP_ps_preparation_report', 'STP_PARTY_WAR_BRIEFING', 'STP_PARTY_FOREIGN_BRIEFING',\n                'STP_PARTY_RECON_BRIEFING')")
write(path, text)

# Only trim newly inserted/replaced lines, not unrelated authored content.
for path in subprocess.check_output(['git', 'diff', '--name-only'], text=True).splitlines():
    raw = Path(path).read_bytes()
    before = subprocess.check_output(['git', 'show', 'HEAD:' + path]).decode('utf-8-sig').splitlines(keepends=True)
    after = raw.decode('utf-8-sig').splitlines(keepends=True)
    edits = difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes()
    for operation, a0, a1, b0, b1 in edits:
        if operation in ('insert', 'replace'):
            for i in range(b0, b1):
                after[i] = after[i].rstrip() + ('\n' if after[i].endswith('\n') else '')
    write(path, ''.join(after))

print('CATEGORY_CONTRACTS: seven faction bargains retained; election panel closes; thresholds retained in apparatus')
