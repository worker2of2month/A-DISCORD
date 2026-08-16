# A-Discord Six-Tier Economic Mobilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new default civilian-oriented economy law, retain the existing five active economy laws as tiers 2-6, and connect the six user-authored PNGs to the complete progression.

**Architecture:** A dedicated unittest parses the actual Clausewitz law category, wrapper/cache effects, upgrade effect, GFX declarations, image payloads, and localisation. The implementation adds one law and one first-step transition while preserving all tier 2-6 mechanics, then installs the six byte-identical icons and bilingual text in separate reviewable commits.

**Tech Stack:** Hearts of Iron IV Clausewitz script and GFX declarations, YAML localisation, Python 3 `unittest`, Pillow, SHA-256.

## Global Constraints

- Fresh campaigns only; do not add old-save migrations or startup repair.
- Work directly in the explicitly approved `main` checkout, stage only exact task paths, and preserve all unrelated dirty work.
- Do not alter tier 2-6 modifiers, availability, costs, AI weights, or war-support gates.
- Do not alter explicit starting economy laws in country history.
- Do not change postwar demobilization or the separate `ADISCORD_economic_system_laws` category.
- Move the six exact PNGs without changing their bytes, dimensions, format, or alpha channel.
- Do not modify or stage `tools/assets/source/laws.psd`.
- Preserve UTF-8 BOM in `localisation/russian/ADISCORD_economy_l_russian.yml`.
- Do not launch Hearts of Iron IV automatically; runtime proof remains a manual fresh-campaign follow-up.

## Source Image Baseline

| Source filename | SHA-256 |
|---|---|
| `Гражданско-ориентированная экономика ур1.png` | `330E254423F2BC672C63EBEED2E47F24227CF3318F52D9F81837663EAD8517C4` |
| `Гражданско-ориентированная экономика ур2 (чуть меннее, нужно поменять название).png` | `6589B6A13380D6EA36E349DED05FFDE2E1942110FAE3002DAF5AB9DD33F55DB1` |
| `ранняя мобилизация ур3.png` | `D38526A25FFA3D5CEE1412CB331546241DF9CBD5BA60994A5DAE5AE9990218ED` |
| `частичная мобилизация ур4.png` | `FF677EEF383F90170CECA442776C645DBB586D4E5A6E6DD6B98F90B7DC17A2F5` |
| `военная экономика ур5.png` | `2AE5F8D3E02407763583BC0DB867B2CB567981F1519C78567560CEAEB141E1AE` |
| `тотальная мобилизация ур 6.png` | `98934F65323573D1C63990078FD8F8C3BC09BA5202F410A546EFD8614C18C5C8` |

---

### Task 1: Add the New Default Law and Six-Step Runtime Contract

**Files:**
- Create: `tools/tests/test_adiscord_economic_mobilization_laws.py`
- Modify: `tools/tests/test_adiscord_economy_weekly_contracts.py:7229-7236`
- Modify: `common/ideas/_economic.txt:7-102`
- Modify: `common/scripted_triggers/ADISCORD_economy_triggers.txt:7-13`
- Modify: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt:238-247`
- Modify: `common/scripted_effects/00_scripted_effects.txt:382-411`

**Interfaces:**
- Consumes: the `economy` law category, stable `has_idea` wrappers, cached consumer-goods law adjustment, and `upgrade_economy_law`.
- Produces: `ADISCORD_civilian_oriented_economy`, wrapper `ADISCORD_economy_has_idea_civilian_oriented_economy`, cache value `1.0`, and transition tier 1 → tier 2.

- [ ] **Step 1: Write the failing law and runtime contract**

Create `tools/tests/test_adiscord_economic_mobilization_laws.py`:

```python
import re
import unittest
from pathlib import Path

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
IDEAS_PATH = ROOT / "common" / "ideas" / "_economic.txt"
TRIGGERS_PATH = ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
MODIFIER_EFFECTS_PATH = (
    ROOT / "common" / "scripted_effects" / "ADISCORD_economy_modifier_effects.txt"
)
GENERAL_EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "00_scripted_effects.txt"
GFX_PATH = ROOT / "interface" / "ADISCORD_ideas.gfx"
RU_LOC_PATH = ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"

ACTIVE_LAWS = (
    "ADISCORD_civilian_oriented_economy",
    "civilian_economy",
    "low_economic_mobilisation",
    "partial_economic_mobilisation",
    "war_economy",
    "tot_economic_mobilisation",
)
EXPECTED_LEVELS = {
    "ADISCORD_civilian_oriented_economy": "6",
    "civilian_economy": "5",
    "low_economic_mobilisation": "4",
    "partial_economic_mobilisation": "3",
    "war_economy": "2",
    "tot_economic_mobilisation": "1",
}
EXPECTED_NEW_LAW_MODIFIERS = {
    "consumer_goods_expected_value": "0.38",
    "stability_factor": "0.12",
    "production_speed_industrial_complex_factor": "0.18",
    "production_speed_arms_factory_factor": "-0.40",
    "production_speed_dockyard_factor": "-0.35",
    "conversion_cost_civ_to_mil_factor": "0.40",
    "conversion_cost_mil_to_civ_factor": "-0.15",
    "production_factory_max_efficiency_factor": "-0.08",
    "industrial_capacity_factory": "-0.10",
    "max_fuel_factor": "-0.35",
    "fuel_gain_factor": "-0.45",
    "factory_energy_consumption": "-0.30",
    "ADISCORD_economy_civilian_factory_income_factor": "0.15",
    "ADISCORD_economy_military_industry_income_factor": "-0.15",
    "ADISCORD_economy_army_expense_factor": "-0.15",
    "ADISCORD_economy_inflation_pressure_factor": "-0.08",
    "ADISCORD_economy_price_stability_factor": "0.08",
    "ADISCORD_economy_creditworthiness_factor": "0.05",
    "ADISCORD_economy_state_overload_gain_factor": "-0.08",
    "ADISCORD_country_development_economic_growth_factor": "0.05",
}


def unique_child(entries, key):
    matches = [entry for entry in entries if entry.key == key]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one block {key}, found {len(matches)}")
    return matches[0].value


def scalar(entries, key):
    matches = [
        entry.value
        for entry in entries
        if entry.key == key and isinstance(entry.value, str)
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected one scalar {key}, found {len(matches)}")
    return matches[0]


def block(text, name):
    match = re.search(rf"(?m)^\s*{re.escape(name)}\s*=\s*\{{", text)
    if not match:
        raise AssertionError(f"missing block: {name}")
    opening = text.find("{", match.start())
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[opening + 1 : index]
    raise AssertionError(f"unclosed block: {name}")


def law_entries():
    parsed = parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig"))
    ideas = unique_child(parsed, "ideas")
    economy = unique_child(ideas, "economy")
    return {
        entry.key: entry.value
        for entry in economy
        if entry.key and isinstance(entry.value, list)
    }


class EconomicMobilizationLawContracts(unittest.TestCase):
    def test_active_progression_has_six_unique_levels_and_new_default(self):
        laws = law_entries()
        self.assertEqual(list(ACTIVE_LAWS), [law for law in laws if law in ACTIVE_LAWS])
        self.assertEqual(
            EXPECTED_LEVELS,
            {law: scalar(laws[law], "level") for law in ACTIVE_LAWS},
        )
        defaults = [
            law
            for law in ACTIVE_LAWS
            if any(
                entry.key == "default" and entry.value == "yes"
                for entry in laws[law]
            )
        ]
        self.assertEqual(["ADISCORD_civilian_oriented_economy"], defaults)

        self.assertEqual("8", scalar(laws["undisturbed_isolation"], "level"))
        self.assertEqual("7", scalar(laws["isolation"], "level"))
        for disabled in ("undisturbed_isolation", "isolation"):
            self.assertEqual("no", scalar(unique_child(laws[disabled], "allowed"), "always"))

    def test_new_default_law_matches_the_approved_balance(self):
        law = law_entries()["ADISCORD_civilian_oriented_economy"]
        self.assertEqual("150", scalar(law, "cost"))
        self.assertEqual("-1", scalar(law, "removal_cost"))
        self.assertEqual("6", scalar(law, "level"))
        self.assertEqual("no", scalar(unique_child(law, "available"), "has_war"))
        self.assertEqual("no", scalar(law, "cancel_if_invalid"))
        actual_modifiers = {
            entry.key: entry.value
            for entry in unique_child(law, "modifier")
            if isinstance(entry.value, str)
        }
        self.assertEqual(EXPECTED_NEW_LAW_MODIFIERS, actual_modifiers)

    def test_runtime_wrapper_cache_and_upgrade_sequence_cover_all_six_tiers(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        modifier_effects = MODIFIER_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        general_effects = GENERAL_EFFECTS_PATH.read_text(encoding="utf-8-sig")

        wrapper = block(
            triggers, "ADISCORD_economy_has_idea_civilian_oriented_economy"
        )
        self.assertIn("has_idea = ADISCORD_civilian_oriented_economy", wrapper)

        cache = block(modifier_effects, "ADISCORD_economy_recalculate_policy_modifiers")
        new_cache_branch = (
            "if = { limit = { ADISCORD_economy_has_idea_civilian_oriented_economy = yes } "
            "set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 1.0 } }"
        )
        civilian_cache_branch = (
            "else_if = { limit = { ADISCORD_economy_has_idea_civilian_economy = yes } "
            "set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 0.7 } }"
        )
        self.assertIn(new_cache_branch, cache)
        self.assertIn(civilian_cache_branch, cache)
        self.assertLess(cache.index(new_cache_branch), cache.index(civilian_cache_branch))

        upgrade = block(general_effects, "upgrade_economy_law")
        self.assertEqual(
            list(ACTIVE_LAWS[:-1]),
            re.findall(r"\bhas_idea\s*=\s*([A-Za-z0-9_]+)", upgrade),
        )
        self.assertEqual(
            list(ACTIVE_LAWS[1:]),
            re.findall(r"\badd_ideas\s*=\s*([A-Za-z0-9_]+)", upgrade),
        )


if __name__ == "__main__":
    unittest.main()
```

This catches a missing tier, duplicate engine level, wrong default, balance drift, missing hot-reload-safe wrapper, wrong cache value, or a broken upgrade link.

- [ ] **Step 2: Extend the existing stable-wrapper expectation before production changes**

In `test_hot_reloadable_economy_effects_use_stable_idea_wrappers` inside `tools/tests/test_adiscord_economy_weekly_contracts.py`, add this literal entry before the current civilian wrapper:

```python
"ADISCORD_economy_has_idea_civilian_oriented_economy": "ADISCORD_civilian_oriented_economy",
```

- [ ] **Step 3: Run the runtime contract and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_hot_reloadable_economy_effects_use_stable_idea_wrappers
```

Expected: FAIL because the new law, unique level 6/default, wrapper, cache branch, and first upgrade transition do not exist.

- [ ] **Step 4: Add the new law without modifying tiers 2-6**

In `common/ideas/_economic.txt`:

1. change `undisturbed_isolation` to `level = 8`;
2. change `isolation` to `level = 7`;
3. insert this block immediately before `civilian_economy`;
4. remove only `default = yes` from `civilian_economy`.

```text
ADISCORD_civilian_oriented_economy = {
	available = {
		has_war = no
	}

	cost = 150
	removal_cost = -1
	level = 6

	modifier = {
		consumer_goods_expected_value = 0.38
		stability_factor = 0.12
		production_speed_industrial_complex_factor = 0.18
		production_speed_arms_factory_factor = -0.40
		production_speed_dockyard_factor = -0.35
		conversion_cost_civ_to_mil_factor = 0.40
		conversion_cost_mil_to_civ_factor = -0.15
		production_factory_max_efficiency_factor = -0.08
		industrial_capacity_factory = -0.10
		max_fuel_factor = -0.35
		fuel_gain_factor = -0.45
		factory_energy_consumption = -0.30
		ADISCORD_economy_civilian_factory_income_factor = 0.15
		ADISCORD_economy_military_industry_income_factor = -0.15
		ADISCORD_economy_army_expense_factor = -0.15
		ADISCORD_economy_inflation_pressure_factor = -0.08
		ADISCORD_economy_price_stability_factor = 0.08
		ADISCORD_economy_creditworthiness_factor = 0.05
		ADISCORD_economy_state_overload_gain_factor = -0.08
		ADISCORD_country_development_economic_growth_factor = 0.05
	}

	default = yes
	cancel_if_invalid = no
}
```

- [ ] **Step 5: Add the wrapper, cache branch, and first upgrade transition**

In `common/scripted_triggers/ADISCORD_economy_triggers.txt`, insert before the current civilian wrapper:

```text
ADISCORD_economy_has_idea_civilian_oriented_economy = { has_idea = ADISCORD_civilian_oriented_economy }
```

In `ADISCORD_economy_recalculate_policy_modifiers`, make the new law the first economy-law branch and change the current civilian branch to `else_if`:

```text
if = { limit = { ADISCORD_economy_has_idea_civilian_oriented_economy = yes } set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 1.0 } }
else_if = { limit = { ADISCORD_economy_has_idea_civilian_economy = yes } set_variable = { var = ADISCORD_economy_cached_consumer_goods_law_adjustment value = 0.7 } }
```

In `upgrade_economy_law`, insert the new first branch and turn the former first `if` into `else_if`:

```text
if = {
	limit = {
		has_idea = ADISCORD_civilian_oriented_economy
	}
	add_ideas = civilian_economy
}
else_if = {
	limit = {
		has_idea = civilian_economy
	}
	add_ideas = low_economic_mobilisation
}
```

Leave all later branches byte-for-byte unchanged.

- [ ] **Step 6: Verify GREEN and commit the runtime slice**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_hot_reloadable_economy_effects_use_stable_idea_wrappers
git diff --check -- common/ideas/_economic.txt common/scripted_triggers/ADISCORD_economy_triggers.txt common/scripted_effects/ADISCORD_economy_modifier_effects.txt common/scripted_effects/00_scripted_effects.txt tools/tests/test_adiscord_economic_mobilization_laws.py tools/tests/test_adiscord_economy_weekly_contracts.py
git add -- 'common/ideas/_economic.txt' 'common/scripted_triggers/ADISCORD_economy_triggers.txt' 'common/scripted_effects/ADISCORD_economy_modifier_effects.txt' 'common/scripted_effects/00_scripted_effects.txt' 'tools/tests/test_adiscord_economic_mobilization_laws.py' 'tools/tests/test_adiscord_economy_weekly_contracts.py'
git diff --cached --check
git commit -m "feat: add civilian-oriented economy tier"
```

---

### Task 2: Install and Bind the Six Economic-Mobilization Icons

**Files:**
- Modify: `tools/tests/test_adiscord_economic_mobilization_laws.py`
- Create directory: `gfx/interface/ideas/laws/economic_mobilization/`
- Move: six exact PNGs from the source-image baseline
- Modify: `interface/ADISCORD_ideas.gfx` after the economic-system sprite block

**Interfaces:**
- Consumes: the six baseline image payloads and six active law IDs.
- Produces: six `GFX_idea_<law ID>` sprites resolving to byte-preserved dedicated PNGs.

- [ ] **Step 1: Add the failing sprite and payload contract**

Add imports:

```python
import hashlib

from PIL import Image
```

Add literal maps:

```python
EXPECTED_TEXTURES = {
    "GFX_idea_ADISCORD_civilian_oriented_economy": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_1_civilian_oriented.png",
    "GFX_idea_civilian_economy": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_2_civilian.png",
    "GFX_idea_low_economic_mobilisation": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_3_early_mobilization.png",
    "GFX_idea_partial_economic_mobilisation": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_4_partial_mobilization.png",
    "GFX_idea_war_economy": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_5_war_economy.png",
    "GFX_idea_tot_economic_mobilisation": "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_6_total_mobilization.png",
}
EXPECTED_SHA256 = {
    "GFX_idea_ADISCORD_civilian_oriented_economy": "330E254423F2BC672C63EBEED2E47F24227CF3318F52D9F81837663EAD8517C4",
    "GFX_idea_civilian_economy": "6589B6A13380D6EA36E349DED05FFDE2E1942110FAE3002DAF5AB9DD33F55DB1",
    "GFX_idea_low_economic_mobilisation": "D38526A25FFA3D5CEE1412CB331546241DF9CBD5BA60994A5DAE5AE9990218ED",
    "GFX_idea_partial_economic_mobilisation": "FF677EEF383F90170CECA442776C645DBB586D4E5A6E6DD6B98F90B7DC17A2F5",
    "GFX_idea_war_economy": "2AE5F8D3E02407763583BC0DB867B2CB567981F1519C78567560CEAEB141E1AE",
    "GFX_idea_tot_economic_mobilisation": "98934F65323573D1C63990078FD8F8C3BC09BA5202F410A546EFD8614C18C5C8",
}
```

Add this test:

```python
def test_six_law_sprites_resolve_to_byte_preserved_pngs(self):
    parsed = parse_clausewitz(GFX_PATH.read_text(encoding="utf-8-sig"))
    sprite_types = unique_child(parsed, "spriteTypes")
    matching = []
    for entry in sprite_types:
        if entry.key != "spriteType" or not isinstance(entry.value, list):
            continue
        name = scalar(entry.value, "name")
        if name in EXPECTED_TEXTURES:
            matching.append((name, scalar(entry.value, "texturefile")))

    self.assertEqual(len(EXPECTED_TEXTURES), len(matching))
    self.assertEqual(EXPECTED_TEXTURES, dict(matching))
    for sprite_name, relative_path in EXPECTED_TEXTURES.items():
        path = ROOT / relative_path
        self.assertEqual(
            EXPECTED_SHA256[sprite_name],
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        )
        with self.subTest(sprite_name=sprite_name), Image.open(path) as image:
            self.assertEqual("PNG", image.format)
            self.assertEqual((64, 64), image.size)
            self.assertIn("A", image.getbands())
```

- [ ] **Step 2: Run the sprite test and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws.EconomicMobilizationLawContracts.test_six_law_sprites_resolve_to_byte_preserved_pngs
```

Expected: FAIL because no six dedicated sprite bindings or target files exist.

- [ ] **Step 3: Recheck all source hashes before moving**

Run:

```powershell
Get-ChildItem -LiteralPath 'gfx/interface/ideas/laws' -File | Sort-Object Name | ForEach-Object { $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash; '{0}`t{1}' -f $_.Name,$hash }
```

Expected: each of the six exact filenames matches the source-image baseline. If any hash differs, preserve the newer user payload and update the test/spec baseline before moving it.

- [ ] **Step 4: Move only the six approved files**

Create `gfx/interface/ideas/laws/economic_mobilization/`, validate source and destination paths remain inside their intended directories, and perform these exact `Move-Item -LiteralPath` mappings:

```powershell
Move-Item -LiteralPath 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_1_civilian_oriented.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур2 (чуть меннее, нужно поменять название).png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_2_civilian.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/ранняя мобилизация ур3.png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_3_early_mobilization.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/частичная мобилизация ур4.png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_4_partial_mobilization.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/военная экономика ур5.png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_5_war_economy.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/тотальная мобилизация ур 6.png' -Destination 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_6_total_mobilization.png'
```

Do not use a wildcard or recursive move.

- [ ] **Step 5: Declare all six law sprites**

Add this exact block to `interface/ADISCORD_ideas.gfx` after the existing economic-system icons:

```text
### A-DISCORD economic mobilization law icons
	spriteType = {
		name = "GFX_idea_ADISCORD_civilian_oriented_economy"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_1_civilian_oriented.png"
	}
	spriteType = {
		name = "GFX_idea_civilian_economy"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_2_civilian.png"
	}
	spriteType = {
		name = "GFX_idea_low_economic_mobilisation"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_3_early_mobilization.png"
	}
	spriteType = {
		name = "GFX_idea_partial_economic_mobilisation"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_4_partial_mobilization.png"
	}
	spriteType = {
		name = "GFX_idea_war_economy"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_5_war_economy.png"
	}
	spriteType = {
		name = "GFX_idea_tot_economic_mobilisation"
		texturefile = "gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_6_total_mobilization.png"
	}
```

- [ ] **Step 6: Verify GREEN and commit the icon slice**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws
git diff --check -- interface/ADISCORD_ideas.gfx tools/tests/test_adiscord_economic_mobilization_laws.py
git add -- 'interface/ADISCORD_ideas.gfx' 'tools/tests/test_adiscord_economic_mobilization_laws.py' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_1_civilian_oriented.png' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_2_civilian.png' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_3_early_mobilization.png' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_4_partial_mobilization.png' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_5_war_economy.png' 'gfx/interface/ideas/laws/economic_mobilization/ADISCORD_economic_mobilization_6_total_mobilization.png'
git diff --cached --check
git commit -m "feat: install economic mobilization law icons"
```

Confirm `tools/assets/source/laws.psd` is not staged.

---

### Task 3: Add Bilingual Tier-1 Localisation

**Files:**
- Modify: `tools/tests/test_adiscord_economic_mobilization_laws.py`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml:355-369`
- Modify: `localisation/english/ADISCORD_economy_l_english.yml` near the economy-model/law entries

**Interfaces:**
- Consumes: new law ID `ADISCORD_civilian_oriented_economy`.
- Produces: bilingual player-facing name and description while preserving all existing tier 2-6 Russian names.

- [ ] **Step 1: Add the failing localisation contract**

Add:

```python
def localisation_value(text, key):
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^"]*)"', text)
    if not match:
        raise AssertionError(f"missing localisation key: {key}")
    return match.group(1)
```

Add this test:

```python
def test_new_tier_is_bilingual_and_existing_russian_names_stay_stable(self):
    self.assertTrue(RU_LOC_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
    ru = RU_LOC_PATH.read_text(encoding="utf-8-sig")
    en = EN_LOC_PATH.read_text(encoding="utf-8-sig")
    self.assertEqual(
        "Гражданско-ориентированная экономика",
        localisation_value(ru, "ADISCORD_civilian_oriented_economy"),
    )
    self.assertEqual(
        "Civilian-Oriented Economy",
        localisation_value(en, "ADISCORD_civilian_oriented_economy"),
    )
    self.assertGreater(
        len(localisation_value(ru, "ADISCORD_civilian_oriented_economy_desc")),
        120,
    )
    self.assertGreater(
        len(localisation_value(en, "ADISCORD_civilian_oriented_economy_desc")),
        120,
    )
    expected_existing = {
        "civilian_economy": "Гражданская экономика",
        "low_economic_mobilisation": "Подготовительная мобилизация",
        "partial_economic_mobilisation": "Частичная мобилизация",
        "war_economy": "Военная экономика",
        "tot_economic_mobilisation": "Тотальная мобилизация",
    }
    self.assertEqual(
        expected_existing,
        {key: localisation_value(ru, key) for key in expected_existing},
    )
```

- [ ] **Step 2: Run the localisation test and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws.EconomicMobilizationLawContracts.test_new_tier_is_bilingual_and_existing_russian_names_stay_stable
```

Expected: FAIL because the two new localisation keys are absent.

- [ ] **Step 3: Add the exact Russian and English entries**

Russian:

```yaml
 ADISCORD_civilian_oriented_economy: "Гражданско-ориентированная экономика"
 ADISCORD_civilian_oriented_economy_desc: "Гражданское потребление, жилищное и инфраструктурное строительство получают приоритет над военными заказами. Такой курс поддерживает стабильность и долгосрочное развитие, но резко замедляет расширение военной промышленности и перевод фабрик на военные рельсы."
```

English:

```yaml
 ADISCORD_civilian_oriented_economy: "Civilian-Oriented Economy"
 ADISCORD_civilian_oriented_economy_desc: "Civilian consumption, housing, and infrastructure construction take priority over military orders. The policy supports stability and long-term development, but sharply slows military-industry expansion and the conversion of factories to wartime production."
```

Preserve the Russian BOM and do not edit existing tier 2-6 strings.

- [ ] **Step 4: Verify GREEN and commit the localisation slice**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws
$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath 'localisation/russian/ADISCORD_economy_l_russian.yml'))
if ($bytes[0] -ne 0xEF -or $bytes[1] -ne 0xBB -or $bytes[2] -ne 0xBF) { throw 'Russian localisation BOM is missing' }
git diff --check -- localisation/russian/ADISCORD_economy_l_russian.yml localisation/english/ADISCORD_economy_l_english.yml tools/tests/test_adiscord_economic_mobilization_laws.py
git add -- 'localisation/russian/ADISCORD_economy_l_russian.yml' 'localisation/english/ADISCORD_economy_l_english.yml' 'tools/tests/test_adiscord_economic_mobilization_laws.py'
git diff --cached --check
git commit -m "loc: add civilian-oriented economy law"
```

---

### Task 4: Run the Full Static Gate

**Files:**
- Verify only; no planned production edits.

**Interfaces:**
- Consumes: Tasks 1-3 and the repository's existing validators.
- Produces: static proof and a precise manual runtime handoff.

- [ ] **Step 1: Run focused and full economy tests**

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_mobilization_laws
python -B -m unittest tools.tests.test_adiscord_economic_system_laws
python -B -m unittest tools.tests.test_adiscord_economy_weekly_contracts
python -B tools/validators/validate_adiscord_economy_ai.py
```

Expected: all tests PASS and the validator prints `A-DISCORD economy/AI validation: OK`.

- [ ] **Step 2: Run the repository validator and diff gates**

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: `validate_tc` PASS and both diff checks clean. Do not repair unrelated failures if another dirty subsystem changes concurrently; report the exact ownership and keep the focused suite green.

- [ ] **Step 3: Audit final scope and image ownership**

```powershell
git status --short
git log --oneline -10
Get-ChildItem -LiteralPath 'gfx/interface/ideas/laws/economic_mobilization' -File | Sort-Object Name | ForEach-Object { $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash; '{0}`t{1}' -f $_.Name,$hash }
git status --short -- 'tools/assets/source/laws.psd'
```

Expected: all six final hashes match the baseline; `laws.psd` remains outside the task commits; unrelated dirty paths remain untouched.

- [ ] **Step 4: Report the runtime gate**

Report the three implementation commits, test counts, validator results, image hashes, and that Hearts of Iron IV was not launched. Request a full restart and fresh campaign to verify six icon overrides, ordering, the new default, localisation wrapping, AI law selection, and `upgrade_economy_law` behavior.
