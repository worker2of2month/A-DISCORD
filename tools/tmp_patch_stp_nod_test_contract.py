from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
path = ROOT / "tools/tests/test_adiscord_stp_civil_war.py"
text = path.read_text(encoding="utf-8")
old = '''            if event_id == "ADISCORD_STP_cw.20":
                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.committed"]
                self.assertEqual(len(closing), 1)
                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],
                                 "the committed-route option only closes the event")
                options = [o for o in options if o not in closing]
            self.assertEqual(len(options), len(choices))
'''
new = '''            if event_id == "ADISCORD_STP_cw.20":
                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.20.committed"]
                self.assertEqual(len(closing), 1)
                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],
                                 "the committed-route option only closes the event")
                options = [o for o in options if o not in closing]
            else:
                closing = [o for o in options if scalar(o, "name") == "ADISCORD_STP_cw.42.c"]
                self.assertEqual(len(closing), 1)
                self.assertEqual([e for e in closing[0] if e.key not in ("name", "trigger", "ai_chance")], [],
                                 "a stale Nodrul card must only close")
                options = [o for o in options if o not in closing]
            self.assertEqual(len(options), len(choices))
'''
if text.count(old) != 1:
    raise RuntimeError(f"external-choice contract changed: {text.count(old)} matches")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
