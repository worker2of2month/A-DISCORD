from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tools/tests/test_adiscord_stp_preparation.py"
text = path.read_text(encoding="utf-8")
old = '''                self.assertIn(idea, {e.value for e in block(available, "NOT") if e.key == "has_idea"},\n                              "do not overwrite a still-active prewar preparation bonus")\n'''
new = '''                idea_locks = {e.value for guard in (e.value for e in available if e.key == "NOT")\n                              for e in guard if e.key == "has_idea"}\n                self.assertIn(idea, idea_locks,\n                              "do not overwrite a still-active prewar preparation bonus")\n'''
if text.count(old) != 1:
    raise RuntimeError(f"expected one war-plan idea assertion; got {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
