# A-DISCORD Superevents Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate A-DISCORD's generic super-event event definitions into one dedicated file, normalize the presentation inventory across GUI/GFX/localisation/sound layers, and add a data-driven regression contract without changing gameplay outcomes or existing public event IDs.

**Architecture:** `events/ADISCORD_superevents.txt` becomes the sole event-definition owner for the generic `ADISCORD_superevent*` namespaces. Gameplay subsystems continue to select and trigger presentations; the super-event layer remains presentation-only. A new data-driven validator defines the seven active presentation routes once and verifies every UI/GFX/localisation/sound layer plus canonical ordering, while existing Vorkerland/STP validators are migrated to the new owner path.

**Tech Stack:** HOI4 Clausewitz script (`.txt`, `.gui`, `.gfx`, `.asset`, localisation YAML), Python 3 `unittest`, repository validators under `tools/validators`.

**Spec:** `docs/superpowers/specs/2026-09-17-superevents-cleanup-design.md`

## Global Constraints

- Do not renumber existing event IDs.
- Do not rename existing gameplay-facing global flags unless a proven bug requires it.
- Do not change console compatibility behaviour for `ADISCORD_superevent.1` or `.2`.
- Preserve existing art and sound asset paths unless a path is demonstrably wrong.
- Keep RU/EN localisation keys stable.
- Preserve the current human-player scoped audio routing needed by HOI4 major-news/global-effect scopes.
- Do not duplicate gameplay mutations inside presentation events.
- Preserve all seven active presentations, including the utilitarian route added by commit `588bf4f`.
- Keep the Dirty Zone lifecycle/news ownership separate from its generic super-event presentation.
- Preserve UTF-8 BOM on localisation `.yml` files and UTF-8 without BOM on Clausewitz `.txt` files.

## File Map

### New files

- `events/ADISCORD_superevents.txt` — sole owner of `ADISCORD_superevent`, `ADISCORD_superevent_audio`, and `ADISCORD_superevent_news` event definitions.
- `tools/validators/validate_adiscord_superevents.py` — data-driven presentation inventory and structural validation.
- `tools/tests/test_validate_adiscord_superevents.py` — unit/regression coverage for the new validator.

### Removed file

- `events/ADISCORD_news.txt` — obsolete generic owner name after its complete contents move to `events/ADISCORD_superevents.txt`.

### Existing presentation files normalized

- `interface/superevents.gfx`
- `interface/superevents.gui`
- `common/scripted_guis/superevents.txt`
- `common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt`
- `localisation/english/ADISCORD_superevents_l_english.yml`
- `localisation/russian/ADISCORD_superevents_l_russian.yml`
- `sound/superevents_sound.asset`
- `sound/superevents_effects.asset`
- `sound/superevents_category.asset`

### Existing registry/validator/test consumers migrated

- `tools/data/adiscord_event_ids.json`
- `tools/validators/validate_adiscord_new_states.py`
- `tools/validators/validate_adiscord_vorkerland_story.py`
- `tools/validators/validate_adiscord_vorkerland_collapse.py`
- `tools/validators/validate_tc.py`
- `tools/tests/test_adiscord_superevents_stp_empire.py`
- `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- `tools/tests/test_validate_adiscord_vorkerland_story.py`

---

### Task 1: Establish the data-driven super-event structural contract

**Files:**
- Create: `tools/validators/validate_adiscord_superevents.py`
- Create: `tools/tests/test_validate_adiscord_superevents.py`
- Modify: `tools/validators/validate_tc.py`

**Interfaces:**
- Consumes: the current presentation files on disk and the approved seven-entry inventory.
- Produces: `PRESENTATIONS`, `collect_issues(root: Path = ROOT) -> list[str]`, and `main() -> int` in `validate_adiscord_superevents.py`; `validate_tc.py` imports `collect_issues` as `validate_adiscord_superevents`.

- [ ] **Step 1: Write failing validator tests for the canonical inventory and cross-layer contract**

Create `tools/tests/test_validate_adiscord_superevents.py` with tests shaped like:

```python
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_superevents import PRESENTATIONS, collect_issues


class SupereventContractTests(unittest.TestCase):
    def test_repository_contract_is_clean(self) -> None:
        self.assertEqual(collect_issues(), [])

    def test_inventory_order_is_canonical(self) -> None:
        self.assertEqual(
            tuple(item.name for item in PRESENTATIONS),
            (
                "superevent_vorkerland_civilwar",
                "superevent_vorkerland_dirty_opening",
                "superevent_vorkerland_worker_victory",
                "superevent_vorkerland_utilitarian_victory",
                "superevent_vorkerland_vlad_victory",
                "superevent_vorkerland_dorian_victory",
                "superevent_stelander_empire",
            ),
        )
```

Add fixture-driven failure tests by copying only the small presentation files into a temporary root, then deleting one required binding at a time. At minimum assert that `collect_issues(temp_root)` reports a missing scripted-GUI entry, missing GFX sprite, missing RU localisation key, and an orphan GUI window.

- [ ] **Step 2: Run the new tests and verify they fail because the validator does not exist yet**

Run:

```bash
python -m unittest tools.tests.test_validate_adiscord_superevents -v
```

Expected: import failure for `tools.validators.validate_adiscord_superevents`.

- [ ] **Step 3: Implement the inventory and structural validator**

Create `tools/validators/validate_adiscord_superevents.py` around this explicit model:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SupereventPresentation:
    name: str
    dedicated_sound_effect: str | None = None


PRESENTATIONS = (
    SupereventPresentation("superevent_vorkerland_civilwar", "superevent_vorkerland_civilwar_sound_e"),
    SupereventPresentation("superevent_vorkerland_dirty_opening", "superevent_vorkerland_dirty_opening_sound_e"),
    SupereventPresentation("superevent_vorkerland_worker_victory", "superevent_vorkerland_worker_victory_sound_e"),
    SupereventPresentation("superevent_vorkerland_utilitarian_victory", "superevent_vorkerland_utilitarian_victory_sound_e"),
    SupereventPresentation("superevent_vorkerland_vlad_victory"),
    SupereventPresentation("superevent_vorkerland_dorian_victory"),
    SupereventPresentation("superevent_stelander_empire", "superevent_stelander_empire_sound_e"),
)
```

Implement helpers that read with `utf-8-sig`, count exact presentation bindings, and check canonical ordering by comparing each identifier's first index. `collect_issues()` must verify:

```python
# For every presentation `name`:
# 1. scripted GUI contains exactly one top-level `name = {` block.
# 2. GUI contains exactly one `name = "<name>"` containerWindowType.
# 3. GFX contains exactly one `name = "GFX_<name>"` spriteType.
# 4. GetSupereventTitle/Quote/Comment each route exactly once to
#    `<name>_title`, `<name>_quote`, `<name>_comment`.
# 5. EN and RU localisation each contain all three keys exactly once.
# 6. If dedicated_sound_effect is not None, the effect exists exactly once in
#    sound/superevents_effects.asset, is listed in SuperEvents category, and
#    its underlying sound name (effect name without trailing `_e`) exists in
#    sound/superevents_sound.asset.
# 7. GUI/scripted-GUI/GFX per-event names are subsets of the inventory.
# 8. All relevant files follow PRESENTATIONS order.
```

For orphan detection, extract only per-event identifiers matching `superevent_[a-z0-9_]+`; exclude shared infrastructure names such as `GFX_supereventframe`, `GFX_supereventquote`, and `GFX_supereventbutton` by extracting GFX only from `GFX_superevent_...` sprites.

Provide CLI behaviour:

```python
def main() -> int:
    issues = collect_issues()
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}")
        return 1
    print("Superevent contract: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Register the validator in the total-conversion gate**

In `tools/validators/validate_tc.py`, add:

```python
from tools.validators.validate_adiscord_superevents import (
    collect_issues as validate_adiscord_superevents,
)
```

Near the other A-DISCORD specialized checks, run it and report it with the existing `print_section(...)` convention used by `validate_adiscord_vorkerland_story` and sibling validators.

- [ ] **Step 5: Run focused tests**

Run:

```bash
python -m unittest tools.tests.test_validate_adiscord_superevents -v
python tools/validators/validate_adiscord_superevents.py
```

Expected at this stage: unit fixture tests pass; repository-contract test may still report ordering/ownership issues that later tasks intentionally fix. Do not weaken the validator to accommodate those issues.

- [ ] **Step 6: Commit the validator contract**

```bash
git add tools/validators/validate_adiscord_superevents.py tools/tests/test_validate_adiscord_superevents.py tools/validators/validate_tc.py
git commit -m "test: define superevent presentation contract"
```

---

### Task 2: Move generic super-event event definitions to their dedicated owner file

**Files:**
- Create: `events/ADISCORD_superevents.txt`
- Delete: `events/ADISCORD_news.txt`
- Modify: `tools/data/adiscord_event_ids.json`
- Modify: `tools/validators/validate_adiscord_new_states.py`
- Modify: `tools/validators/validate_adiscord_vorkerland_story.py`
- Modify: `tools/validators/validate_adiscord_vorkerland_collapse.py`
- Modify: `tools/tests/test_adiscord_superevents_stp_empire.py`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_story.py`

**Interfaces:**
- Consumes: existing event IDs `ADISCORD_superevent.1/.2`, `ADISCORD_superevent_audio.1/.2`, `ADISCORD_superevent_news.1/.2` and all existing callers.
- Produces: identical event definitions and behaviour at `events/ADISCORD_superevents.txt`; registry ownership for all six IDs points to the new path.

- [ ] **Step 1: Change path expectations in tests first**

Update test constants/reads from:

```python
ROOT / "events/ADISCORD_news.txt"
```

to:

```python
ROOT / "events/ADISCORD_superevents.txt"
```

In the new structural test add:

```python
def test_legacy_generic_news_file_is_gone(self) -> None:
    self.assertFalse((ROOT / "events/ADISCORD_news.txt").exists())
    self.assertTrue((ROOT / "events/ADISCORD_superevents.txt").is_file())
```

- [ ] **Step 2: Run the path-sensitive tests and verify they fail**

Run:

```bash
python -m unittest \
  tools.tests.test_adiscord_superevents_stp_empire \
  tools.tests.test_validate_adiscord_vorkerland_collapse \
  tools.tests.test_validate_adiscord_vorkerland_story \
  tools.tests.test_validate_adiscord_superevents -v
```

Expected: failures because `events/ADISCORD_superevents.txt` does not yet exist and the legacy file still exists.

- [ ] **Step 3: Move the complete event file without changing IDs or behaviour**

Create `events/ADISCORD_superevents.txt` with the complete current contents of `events/ADISCORD_news.txt`, preserving these namespace declarations:

```hoi4
add_namespace = ADISCORD_superevent
add_namespace = ADISCORD_superevent_news
add_namespace = ADISCORD_superevent_audio
```

Preserve the complete bodies of:

```text
ADISCORD_superevent.1
ADISCORD_superevent.2
ADISCORD_superevent_audio.1
ADISCORD_superevent_audio.2
ADISCORD_superevent_news.1
ADISCORD_superevent_news.2
```

Do not alter the Vorkerland-collapse dispatch, human scoped audio, or presentation-only Stelander Empire contract in this step. Delete `events/ADISCORD_news.txt` only after the new file is written.

- [ ] **Step 4: Migrate validator path constants and reads**

Replace only super-event owner references in the affected Python files:

```python
Path("events/ADISCORD_news.txt")
```

with:

```python
Path("events/ADISCORD_superevents.txt")
```

and equivalent string reads. Do not rename unrelated world-news or Dirty Zone news files.

- [ ] **Step 5: Update the event-ID registry ownership**

In `tools/data/adiscord_event_ids.json`, change `owner` for exactly these six entries to `events/ADISCORD_superevents.txt`:

```text
ADISCORD_superevent.1
ADISCORD_superevent.2
ADISCORD_superevent_audio.1
ADISCORD_superevent_audio.2
ADISCORD_superevent_news.1
ADISCORD_superevent_news.2
```

Keep namespace, number, subsystem, and status unchanged.

- [ ] **Step 6: Run migration and registry tests**

Run:

```bash
python -m unittest \
  tools.tests.test_adiscord_superevents_stp_empire \
  tools.tests.test_validate_adiscord_vorkerland_collapse \
  tools.tests.test_validate_adiscord_vorkerland_story \
  tools.tests.test_validate_adiscord_event_ids -v
python tools/validators/validate_adiscord_event_ids.py
```

Expected: PASS.

- [ ] **Step 7: Search for stale owner-path references**

Run:

```bash
git grep -n "events/ADISCORD_news.txt" -- ':!docs/superpowers/**'
```

Expected: no output. Historical design/plan documents may retain the old path as history and are intentionally excluded.

- [ ] **Step 8: Commit the ownership migration**

```bash
git add events/ADISCORD_superevents.txt tools/data/adiscord_event_ids.json tools/validators tools/tests
git rm events/ADISCORD_news.txt
git commit -m "refactor: give superevents a dedicated event owner"
```

---

### Task 3: Normalize all presentation layers to one inventory and order

**Files:**
- Modify: `interface/superevents.gfx`
- Modify: `interface/superevents.gui`
- Modify: `common/scripted_guis/superevents.txt`
- Modify: `common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt`
- Modify: `localisation/english/ADISCORD_superevents_l_english.yml`
- Modify: `localisation/russian/ADISCORD_superevents_l_russian.yml`
- Modify: `sound/superevents_sound.asset`
- Modify: `sound/superevents_effects.asset`
- Modify: `sound/superevents_category.asset`

**Interfaces:**
- Consumes: `PRESENTATIONS` order from Task 1 and existing global flags/assets.
- Produces: all seven active presentation routes in identical canonical order, with stable names/keys/paths and readable formatting.

- [ ] **Step 1: Tighten the repository-contract test to require canonical ordering everywhere**

Ensure `test_repository_contract_is_clean` calls the validator against the real repository and therefore fails until every listed file follows:

```text
civilwar
→ dirty_opening
→ worker_victory
→ utilitarian_victory
→ vlad_victory
→ dorian_victory
→ stelander_empire
```

Add a direct assertion for the shared GFX infrastructure remaining before event sprites:

```python
gfx = (ROOT / "interface/superevents.gfx").read_text(encoding="utf-8-sig")
self.assertLess(gfx.index('name = "GFX_supereventbutton"'), gfx.index('name = "GFX_superevent_vorkerland_civilwar"'))
```

- [ ] **Step 2: Run the structural test and capture the current ordering failures**

Run:

```bash
python -m unittest tools.tests.test_validate_adiscord_superevents -v
```

Expected: FAIL with one or more ordering/format inventory issues; failures must identify file and presentation name.

- [ ] **Step 3: Normalize `interface/superevents.gfx`**

Keep shared sprites first:

```text
GFX_supereventframe
GFX_supereventquote
GFX_supereventbutton
```

Then order event sprites exactly as `PRESENTATIONS`. Preserve these existing art bindings, including the new utilitarian asset:

```text
GFX_superevent_vorkerland_civilwar
GFX_superevent_vorkerland_dirty_opening
GFX_superevent_vorkerland_worker_victory
GFX_superevent_vorkerland_utilitarian_victory
GFX_superevent_vorkerland_vlad_victory
GFX_superevent_vorkerland_dorian_victory
GFX_superevent_stelander_empire
```

Do not substitute artwork in this cleanup.

- [ ] **Step 4: Normalize GUI and scripted GUI ordering/formatting**

In both `interface/superevents.gui` and `common/scripted_guis/superevents.txt`, order the seven event blocks exactly as `PRESENTATIONS`.

Expand compressed one-line blocks where needed so each scripted-GUI entry follows this readable shape:

```hoi4
superevent_vorkerland_dirty_opening = {
    window_name = "superevent_vorkerland_dirty_opening"
    context_type = player_context

    visible = {
        has_global_flag = superevent_vorkerland_dirty_opening
    }

    effects = {
        superevents_button_click = {
            clr_global_flag = superevent_vorkerland_dirty_opening
        }
    }
}
```

Apply the same structural formatting to all seven without changing window dimensions, fonts, coordinates, shortcuts, or click behaviour.

- [ ] **Step 5: Normalize scripted localisation and RU/EN localisation**

For each of `GetSupereventQuote`, `GetSupereventTitle`, and `GetSupereventComment`, order routes according to `PRESENTATIONS`. Preserve the joint-government special case immediately before ordinary Vlad routing because both use `superevent_vorkerland_vlad_victory`:

```hoi4
text = {
    trigger = {
        has_global_flag = superevent_vorkerland_vlad_victory
        has_global_flag = ADISCORD_vorkerland_joint_government_formed
    }
    localization_key = superevent_vorkerland_joint_victory_title
}
text = {
    trigger = { has_global_flag = superevent_vorkerland_vlad_victory }
    localization_key = superevent_vorkerland_vlad_victory_title
}
```

Use `_quote` and `_comment` analogues in the other defined-text blocks.

Order EN/RU title/quote/comment triplets to match the same inventory. Preserve every existing key and string value; preserve BOM on both YAML files.

- [ ] **Step 6: Normalize sound declarations**

Order `sound/superevents_sound.asset`, `sound/superevents_effects.asset`, and the `SuperEvents` category using the subset of `PRESENTATIONS` that has dedicated sound:

```text
civilwar
→ dirty_opening
→ worker_victory
→ utilitarian_victory
→ stelander_empire
```

Vlad and Dorian intentionally continue through the existing civil-war fallback in `ADISCORD_vorkerland_play_local_superevent_audio`; do not invent dedicated audio assets in this cleanup.

- [ ] **Step 7: Run the structural validator until the repository contract passes**

Run:

```bash
python -m unittest tools.tests.test_validate_adiscord_superevents -v
python tools/validators/validate_adiscord_superevents.py
```

Expected: PASS and `Superevent contract: OK`.

- [ ] **Step 8: Commit the presentation normalization**

```bash
git add interface/superevents.gfx interface/superevents.gui \
  common/scripted_guis/superevents.txt \
  common/scripted_localisation/ADISCORD_scripted_loc_superevents.txt \
  localisation/english/ADISCORD_superevents_l_english.yml \
  localisation/russian/ADISCORD_superevents_l_russian.yml \
  sound/superevents_sound.asset sound/superevents_effects.asset sound/superevents_category.asset
git commit -m "refactor: normalize superevent presentation layers"
```

---

### Task 4: Run the full regression gate and make the final cleanup commit

**Files:**
- Modify only if a regression exposes a direct super-event cleanup defect; do not expand scope.
- Verify: all files changed in Tasks 1–3.

**Interfaces:**
- Consumes: dedicated event ownership and normalized presentation contract.
- Produces: a clean repository state with all relevant validators/tests green and no stale live-code references to the old owner path.

- [ ] **Step 1: Run the focused super-event/STP/Vorkerland regression suite**

Run:

```bash
python -m unittest \
  tools.tests.test_validate_adiscord_superevents \
  tools.tests.test_adiscord_superevents_stp_empire \
  tools.tests.test_validate_adiscord_vorkerland_collapse \
  tools.tests.test_validate_adiscord_vorkerland_story \
  tools.tests.test_validate_adiscord_event_ids -v
```

Expected: all tests PASS.

- [ ] **Step 2: Run the direct validators**

Run:

```bash
python tools/validators/validate_adiscord_superevents.py
python tools/validators/validate_adiscord_event_ids.py
python tools/validators/validate_adiscord_vorkerland_collapse.py
python tools/validators/validate_adiscord_vorkerland_story.py
```

Expected: exit code 0 for every command.

- [ ] **Step 3: Run the total-conversion validator with the new super-event gate registered**

Run:

```bash
python tools/validators/validate_tc.py
```

Expected: no new super-event-related errors. If unrelated pre-existing repository errors exist, record them separately and verify the new `Superevents` section itself is clean rather than modifying unrelated systems.

- [ ] **Step 4: Perform stale-reference and inventory searches**

Run:

```bash
git grep -n "events/ADISCORD_news.txt" -- ':!docs/superpowers/**'
git grep -n "ADISCORD_superevent" events common tools/data tools/validators tools/tests
git grep -n "superevent_vorkerland_utilitarian_victory" common interface localisation sound
```

Expected: the first command has no output; the latter two show only intentional current wiring.

- [ ] **Step 5: Review the final diff for gameplay leakage**

Run:

```bash
git diff HEAD~3..HEAD -- events common interface localisation sound tools
```

Confirm that presentation files do not introduce `transfer_state`, `set_politics`, `add_country_leader_role`, or new war/peace/state mutations. Confirm `STP_proclaim_imperial_union` and Vorkerland gameplay effects remain the owners of mechanical state changes.

- [ ] **Step 6: Check working tree and create a final cleanup commit only if verification required follow-up edits**

If verification forced direct fixes, commit only those fixes:

```bash
git add <only-direct-superevent-fixes>
git commit -m "fix: close superevent cleanup regressions"
```

If the working tree is already clean after the three task commits, do not create an empty commit. Report the final implementation commit range and the latest commit SHA.
