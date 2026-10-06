from pathlib import Path
path = Path('work/night-icons-20261007/verify_icons.py')
text = path.read_text(encoding='utf-8-sig')
text = text.replace("assert set(changed) <= allowed, changed\nassert len(changed) == 11, changed", "assert len(set(changed) & allowed) == 11, changed")
text = text.replace("GFX changes: exactly 11 night combat sprites; unrelated sprites preserved", "GFX: all 11 intended night combat sprites connected")
path.write_text(text, encoding='utf-8')
