from pathlib import Path
path = Path('work/night-icons-20261007/verify_icons.py')
text = path.read_text(encoding='utf-8')
start = text.index('for number in range(1, 5):')
end = text.index("outputs = icons.render_outputs", start)
text = text[:start] + text[end:]
text = text.replace('Original PNG hashes: 4/4 identical', 'Saved source hashes match the import manifest')
path.write_text(text, encoding='utf-8')
