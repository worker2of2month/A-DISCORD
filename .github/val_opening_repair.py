from pathlib import Path
import hashlib
import sys

ROOT = Path.cwd()
FOCUS = 'common/national_focus/ADISCORD_national_focus_VAL.txt'
EFFECTS = 'common/scripted_effects/ADISCORD_VAL_logistics_market_effects.txt'
MUSIC_TESTS = 'tools/tests/test_val_contract_ui.py'
REFUGEE_TESTS = 'tools/tests/test_adiscord_val_refugees.py'
EXPECTED = {
    FOCUS: '95c9b884580755ce74ec0cd7ccc757cb6b431af7',
    EFFECTS: 'ff5f9b20835e4912c19646bf541af3b0d196d06f',
    MUSIC_TESTS: '698798ecb862c78d4a463d20965b958faa52962a',
    REFUGEE_TESTS: 'b1ed4bf4827c9d2fcc3405e396a8c6dcd4d9c4ba',
}
MUSIC_ADDITION = '''

class KefreytOpeningThemeTests(unittest.TestCase):
    def test_first_focus_plays_registered_theme_for_human_country(self):
        from tools.validators.validate_adiscord_division_templates import parse_clausewitz
        tree = parse_clausewitz((ROOT / "common/national_focus/ADISCORD_national_focus_VAL.txt").read_text())[0].value
        focus = next(e.value for e in tree if e.key == "focus" and any(c.key == "id" and c.value == "VAL_The_Contract_State" for c in e.value))
        reward = next(e.value for e in focus if e.key == "completion_reward")
        hidden = next(e.value for e in reward if e.key == "hidden_effect")
        guarded = [e.value for e in hidden if e.key == "if" and any(c.key == "scoped_play_song" for c in e.value)]
        self.assertEqual(len(guarded), 1, "The opening focus must start Kefreyt's theme exactly once")
        limit = next(e.value for e in guarded[0] if e.key == "limit")
        self.assertEqual([(e.key, e.value) for e in limit], [("is_ai", "no")])
        self.assertEqual([e.value for e in guarded[0] if e.key == "scoped_play_song"], ["ADISCORD_val_theme"])
        self.assertFalse(any(e.key == "play_song" for e in reward + hidden + guarded[0]))
        assets = parse_clausewitz((ROOT / "music/ADISCORD_music.asset").read_text())
        theme = [e.value for e in assets if e.key == "music" and any(c.key == "name" and c.value == "ADISCORD_val_theme" for c in e.value)]
        self.assertEqual(len(theme), 1)
        self.assertIn(("file", "ADISCORD_val_theme.ogg"), [(e.key, e.value) for e in theme[0]])
        self.assertIn('song = "ADISCORD_val_theme"', (ROOT / "music/ADISCORD_songs.txt").read_text())
'''
REFUGEE_ADDITION = '''    def test_startup_and_weekly_recover_only_unseen_war_windows(self):
        for entry in ("VAL_initialize_logistics_market", "VAL_update_refugees_weekly"):
            calls = [e for e in self.effects[entry] if e.key == "VAL_open_refugee_waves"]
            self.assertEqual(len(calls), 1, f"{entry} must recover a missed war notification")
            self.assertEqual(calls[0].value, "yes")
            for region in REGIONS:
                with self.subTest(entry=entry, region=region):
                    self.setUp()
                    self.facts[("VAL", f"VAL_refugee_{region}_war", "yes")] = True
                    self.run_effect(self.effects[calls[0].key])
                    window = f"VAL_refugee_{region}_window"
                    self.assertTrue(self.visible(region))
                    self.assertEqual(self.windows[window], 180)
                    self.facts[("VAL", "has_country_flag", window)] = False
                    self.run_effect(self.effects[calls[0].key])
                    self.assertFalse(self.visible(region), "Expired windows must not be restarted")

'''

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding='utf-8')
    assert text.count(old) == 1, (path, old)
    p.write_text(text.replace(old, new, 1), encoding='utf-8')

def tests():
    for path, wanted in EXPECTED.items():
        data = (ROOT / path).read_bytes()
        actual = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        assert actual == wanted, (path, actual, wanted)
    replace_once(MUSIC_TESTS, '\nif __name__ == "__main__":', MUSIC_ADDITION + '\nif __name__ == "__main__":')
    replace_once(REFUGEE_TESTS, '    def test_each_war_opens_once_and_expiry_does_not_reopen(self):', REFUGEE_ADDITION + '    def test_each_war_opens_once_and_expiry_does_not_reopen(self):')

def fix():
    replace_once(FOCUS, '\t\t\t\tset_country_flag = VAL_contract_throne\n', '\t\t\t\tif = { limit = { is_ai = no } scoped_play_song = "ADISCORD_val_theme" }\n\t\t\t\tset_country_flag = VAL_contract_throne\n')
    replace_once(EFFECTS, '\tVAL_refresh_refugee_state = yes\n}\n\nVAL_refresh_trade_network', '\tVAL_refresh_refugee_state = yes\n\tVAL_open_refugee_waves = yes\n}\n\nVAL_refresh_trade_network')
    replace_once(EFFECTS, 'VAL_update_refugees_weekly = {\n', 'VAL_update_refugees_weekly = {\n\t# Recover missed war notifications without renewing an already seen wave.\n\tVAL_open_refugee_waves = yes\n')

if __name__ == '__main__':
    {'tests': tests, 'fix': fix}[sys.argv[1]]()
