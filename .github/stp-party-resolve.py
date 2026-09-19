"""Resolve only independently appended economic/party dummy definitions."""
import re
import subprocess
import sys
from pathlib import Path

path = 'common/ideas/ADISCORD_STP_civil_war_ideas.txt'
unmerged = subprocess.check_output(['git', 'diff', '--name-only', '--diff-filter=U'], text=True).splitlines()
if not unmerged:
    raise SystemExit(0)
if unmerged != [path]:
    raise SystemExit(f'Unexpected conflicted paths: {unmerged}')
p = Path(path)
text = p.read_text(encoding='utf-8')
pattern = r'(?m)^<<<<<<< ours\n(.*?)^=======\n(.*?)^>>>>>>> theirs\n'
match = list(re.finditer(pattern, text, re.S))
if len(match) != 1:
    raise SystemExit('Expected one known additive conflict')
m = match[0]
old, new = m.group(1), m.group(2)
old_ids = set(re.findall(r'(?m)^\t\t(\w+) = \{', old))
new_ids = set(re.findall(r'(?m)^\t\t(\w+) = \{', new))
expected_old = {'STP_pw_economy_' + suffix + '_delta' for suffix in
                ('count_the_cost', 'reopen_tax_offices', 'repair_workshops', 'stabilize_currency', 'recovery_budget')}
expected_new = {'STP_party_' + suffix for suffix in (
    'district_compact_party_delta', 'supply_directorate_army_delta', 'civil_register_party_delta',
    'succession_protocol_party_delta', 'war_transport_army_delta', 'rear_administration_party_delta',
    'war_directorate_army_delta', 'district_charters_post_delta', 'local_cadres_post_delta',
    'personnel_commissions_post_delta', 'chain_of_command_post_delta', 'revenue_service_post_delta',
    'port_contracts_post_delta', 'industrial_board_post_delta', 'research_council_post_delta',
    'technical_institutes_post_delta')}
if old_ids != expected_old or new_ids != expected_new or old_ids & new_ids:
    raise SystemExit('Conflict is not the reviewed independent append')
resolved = text[:m.start()] + old + '\n' + new + text[m.end():]
if re.search(r'(?m)^(<<<<<<<|=======|>>>>>>>)', resolved):
    raise SystemExit('Residual conflict markers')
sys.path.insert(0, str(Path.cwd()))
from tools.validators.validate_adiscord_division_templates import parse_clausewitz

def definitions(source):
    root = next(e.value for e in parse_clausewitz(source) if e.key == 'ideas')
    def signature(entry):
        return (entry.key, [signature(e) for e in entry.value] if isinstance(entry.value, list) else entry.value, entry.quoted)
    return {e.key: signature(e) for section in root if isinstance(section.value, list) for e in section.value}

baseline = subprocess.check_output(['git', 'show', 'HEAD:' + path], text=True)
before, after = definitions(baseline), definitions(resolved)
for name, node in before.items():
    if name not in after or after[name] != node:
        raise SystemExit('Changed existing definition: ' + name)
if set(after) - set(before) != expected_new:
    raise SystemExit('Unexpected appended definitions')
p.write_text(resolved, encoding='utf-8')
subprocess.run(['git', 'add', '--', path], check=True)
print('Preserved the five concurrent economic ideas and sixteen independent party deltas.')
