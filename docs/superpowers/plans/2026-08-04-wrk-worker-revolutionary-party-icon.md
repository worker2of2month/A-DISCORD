# WRK Worker Revolutionary Party Icon Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Подключить подготовленный значок к правящей прагматистской партии WRK и переименовать её в «Рабочая революционная партия».

**Architecture:** Отдельный WRK-текстовый спрайт связывает нормализованное имя PNG с двумя локализационными ключами партии. Небольшой контрактный тест проверяет файл, размер изображения, регистрацию спрайта, русскую локализацию и UTF-8 BOM.

**Tech Stack:** HOI4 Clausewitz GFX/localisation, PNG, Python 3 `unittest`, Pillow.

## Global Constraints

- Изменение относится только к прагматистской партии тега `WRK`.
- Другие идеологии, страны, популярность партий и политическая логика не меняются.
- Существующие незавершённые изменения в рабочем дереве сохраняются.
- Русская локализация сохраняет UTF-8 BOM.
- Статические проверки не считаются визуальной проверкой интерфейса в игре.

---

### Task 1: Подключить значок и название партии WRK

**Files:**
- Create: `tools/test_wrk_party_icon.py`
- Rename: `gfx/texticons/adiscord/parties/WRK/worker revolutionary party.png` -> `gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png`
- Modify: `interface/parties_texticons.gfx`
- Modify: `localisation/russian/parties_l_russian.yml`

**Interfaces:**
- Consumes: существующий PNG 25x25 и локализационные ключи `WRK_pragmatism_party`, `WRK_pragmatism_party_long`.
- Produces: спрайт `GFX_WRK_worker_revolutionary_party_texticon`, используемый обеими строками партии.

- [ ] **Step 1: Write the failing contract test**

Create `tools/test_wrk_party_icon.py`:

```python
from __future__ import annotations

import re
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
ICON = ROOT / "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"
SPRITE = "GFX_WRK_worker_revolutionary_party_texticon"


class WrkPartyIconContractTests(unittest.TestCase):
    def test_icon_and_sprite_contract(self) -> None:
        self.assertTrue(ICON.is_file(), ICON)
        with Image.open(ICON) as image:
            self.assertEqual(image.size, (25, 25))
            self.assertEqual(image.mode, "RGBA")

        gfx = (ROOT / "interface/parties_texticons.gfx").read_text(
            encoding="utf-8-sig"
        )
        block = re.search(
            rf'(?s)spriteType\s*=\s*\{{(?:(?!spriteType).)*name\s*=\s*"{SPRITE}"(?:(?!spriteType).)*\}}',
            gfx,
        )
        self.assertIsNotNone(block)
        self.assertIn(
            'texturefile = "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"',
            block.group(0),
        )
        self.assertIn("legacy_lazy_load = no", block.group(0))

    def test_russian_party_name_uses_wrk_icon(self) -> None:
        path = ROOT / "localisation/russian/parties_l_russian.yml"
        self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
        localisation = path.read_text(encoding="utf-8-sig")
        expected = f'£{SPRITE} Рабочая революционная партия'
        self.assertIn(f'WRK_pragmatism_party: "{expected}"', localisation)
        self.assertIn(f'WRK_pragmatism_party_long: "{expected}"', localisation)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```powershell
python -B -m unittest tools.test_wrk_party_icon -v
```

Expected: FAIL because `WRK_worker_revolutionary_party.png`, its sprite registration, and the new localisation are absent.

- [ ] **Step 3: Rename the supplied icon after resolving exact paths**

Verify that the source exists inside the repository and the destination does not, then rename only that file:

```powershell
$source = (Resolve-Path -LiteralPath 'gfx/texticons/adiscord/parties/WRK/worker revolutionary party.png').Path
$destination = Join-Path (Split-Path -Parent $source) 'WRK_worker_revolutionary_party.png'
if (Test-Path -LiteralPath $destination) { throw "Destination already exists: $destination" }
Move-Item -LiteralPath $source -Destination $destination
```

- [ ] **Step 4: Register the dedicated WRK sprite**

Add this block after the unknown-party sprite in `interface/parties_texticons.gfx`:

```text
	##WRK
	spriteType = {
		name = "GFX_WRK_worker_revolutionary_party_texticon"
		texturefile = "gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png"
		legacy_lazy_load = no
	}
```

- [ ] **Step 5: Replace the WRK pragmatist localisation and preserve BOM**

In `localisation/russian/parties_l_russian.yml`, replace only these two entries:

```yaml
  WRK_pragmatism_party: "£GFX_WRK_worker_revolutionary_party_texticon Рабочая революционная партия"
  WRK_pragmatism_party_long: "£GFX_WRK_worker_revolutionary_party_texticon Рабочая революционная партия"
```

- [ ] **Step 6: Run the focused contract**

Run:

```powershell
python -B -m unittest tools.test_wrk_party_icon -v
```

Expected: 2 tests PASS.

- [ ] **Step 7: Run project validation and diff hygiene**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check -- tools/test_wrk_party_icon.py interface/parties_texticons.gfx localisation/russian/parties_l_russian.yml
git status --short -- tools/test_wrk_party_icon.py interface/parties_texticons.gfx localisation/russian/parties_l_russian.yml gfx/texticons/adiscord/parties/WRK
```

Expected: focused contract passes; `validate_tc.py` reports no target-related issue; diff check is clean; status contains only the intended party-icon subset within these paths.

- [ ] **Step 8: Commit only the coherent party-icon subset**

```powershell
git add -- tools/test_wrk_party_icon.py interface/parties_texticons.gfx localisation/russian/parties_l_russian.yml gfx/texticons/adiscord/parties/WRK/WRK_worker_revolutionary_party.png
git diff --cached --check
git diff --cached --name-status
git commit -m "feat: add WRK revolutionary party icon"
```
