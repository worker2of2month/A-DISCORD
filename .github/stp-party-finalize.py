from pathlib import Path
import re

root = Path.cwd()
path = root / 'tools/tests/test_adiscord_stp_preparation.py'
s = path.read_text()
old = '''            party = {**closed, ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True}
            self.assertTrue(matches_conditions(visible, party), "Party government programs share this category")
            self.assertFalse(matches_conditions(visible, {**party,
                ("STP", "has_global_flag", "STP_cw_union_wars_finished"): True}))'''
new = '''            party = {**closed, ("STP", "has_country_flag", "STP_sided_with_the_party_flag"): True,
                     ("STP", "STP_pf_active", "yes"): True}
            self.assertTrue(matches_conditions(visible, party), "Active factions keep the Presidium available")
            self.assertTrue(matches_conditions(visible, {**party,
                ("STP", "has_global_flag", "STP_cw_union_wars_finished"): True}),
                "Postwar faction management must remain accessible")
            self.assertFalse(matches_conditions(visible, {**party,
                ("STP", "STP_pf_active", "yes"): False}),
                "Without preparation or active factions the Presidium closes")'''
assert s.count(old) == 1, 'preparation visibility test changed upstream'
path.write_text(s.replace(old, new))

replacements = {
 'russian': {
  'STP_ps_val_intercept_desc': 'За 14 дней подготовим засаду на разведанный груз. До раскола перехваченное оружие вернётся в общий государственный запас; во время войны его получит партия вместо сопротивления. Подготовка доступна и при закрытом маршруте. Если груз уйдёт раньше, депозит вернётся.\\n\\n[STPGetPartyConvoyStatus]',
  'STP_ps_val_intercept_result_tt': 'Через 14 дней засада будет готова. При отправке груз вернётся в общий запас до раскола либо поступит партии во время войны. Ранний уход груза возвращает оплату незавершённой операции.',
 },
 'english': {
  'STP_ps_val_intercept_desc': 'Prepare an ambush on the known cargo in 14 days. Before the split, intercepted weapons return to the shared state stockpile; during the war they go to the Party instead of the resistance. Preparation can begin while the route is closed. Early departure refunds the deposit.\\n\\n[STPGetPartyConvoyStatus]',
  'STP_ps_val_intercept_result_tt': 'After 14 days, the ambush is ready. At departure, cargo returns to the shared state stockpile before the split, or goes to the Party during the war. Early departure refunds an unfinished operation.',
 }
}
for language, values in replacements.items():
 path = root / f'localisation/{language}/ADISCORD_STP_l_{language}.yml'
 text = path.read_bytes().decode('utf-8')
 for key, value in values.items():
  pattern = re.compile(r'^(\s*' + re.escape(key) + r':(?:\d+)?\s*)".*"$', re.M)
  text, count = pattern.subn(lambda m: m.group(1)+'"'+value+'"', text)
  assert count == 1, key
 path.write_bytes(text.encode('utf-8'))
