# A-Discord Economic-System Law Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the nine user-authored economic-system icons, replace the obsolete mobilization system with a civilian-focused syndicalist system, and assign the requested starting systems without touching the separate economic-mobilization progression.

**Architecture:** A focused unittest parses the Clausewitz law, GFX, trigger, effect, localisation, and country-history boundaries that Hearts of Iron IV consumes. Production changes keep economy model number 5 but replace its law/predicate, remove only its old wartime special cases, and leave the separate `ADISCORD_economy_model_allows_mobilization_economy` capability and user-authored mobilization-progression artwork intact.

**Tech Stack:** Hearts of Iron IV Clausewitz script and GFX declarations, YAML localisation, Python 3 `unittest`, Pillow.

## Global Constraints

- Fresh campaigns only; do not add old-save migration or compatibility aliases.
- Preserve all unrelated dirty technology, equipment, entity, documentation, and source-art changes.
- Move only the nine exact source filenames listed in Task 1.
- Do not rename, move, edit, declare, stage, or commit `gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png` or later economic-mobilization artwork.
- Preserve the current protected-file SHA-256 `330E254423F2BC672C63EBEED2E47F24227CF3318F52D9F81837663EAD8517C4` throughout this implementation unless the user edits the file concurrently.
- Do not modify `tools/assets/source/laws.psd`.
- Preserve UTF-8 BOM in `localisation/russian/ADISCORD_economy_l_russian.yml`.
- Do not launch Hearts of Iron IV automatically; runtime proof is a manual fresh-campaign follow-up.
- Stage and commit only explicit paths from the task being completed.

---

### Task 1: Install the Dedicated Economic-System Icon Set

**Files:**
- Create: `tools/tests/test_adiscord_economic_system_laws.py`
- Create directory: `gfx/interface/ideas/laws/economic_system/`
- Move: the nine exact PNGs listed below into `gfx/interface/ideas/laws/economic_system/`
- Modify: `interface/ADISCORD_ideas.gfx:458-494`
- Preserve untouched: `gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png`

**Interfaces:**
- Consumes: nine 64x64 PNG files currently stored directly under `gfx/interface/ideas/laws/`.
- Produces: `GFX_idea_ADISCORD_economic_system_<suffix>` sprites whose `texturefile` values resolve to dedicated PNGs.

- [ ] **Step 1: Reconfirm the protected mobilization-progression asset before any move**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png'
```

Expected: SHA-256 `330E254423F2BC672C63EBEED2E47F24227CF3318F52D9F81837663EAD8517C4`. If the hash differs, treat it as concurrent user work: record the new value and preserve that file without editing or staging it.

- [ ] **Step 2: Write the failing icon-boundary test**

Create `tools/tests/test_adiscord_economic_system_laws.py` with the real GFX parser and literal expected paths:

```python
import re
import unittest
from pathlib import Path

from PIL import Image

from tools.validators.validate_adiscord_division_templates import parse_clausewitz


ROOT = Path(__file__).resolve().parents[2]
IDEAS_PATH = ROOT / "common" / "ideas" / "_economic.txt"
GFX_PATH = ROOT / "interface" / "ADISCORD_ideas.gfx"
TRIGGERS_PATH = ROOT / "common" / "scripted_triggers" / "ADISCORD_economy_triggers.txt"
EFFECTS_PATH = ROOT / "common" / "scripted_effects" / "ADISCORD_economy_effects.txt"
RU_LOC_PATH = ROOT / "localisation" / "russian" / "ADISCORD_economy_l_russian.yml"
EN_LOC_PATH = ROOT / "localisation" / "english" / "ADISCORD_economy_l_english.yml"

SYSTEM_SUFFIXES = (
    "agrarian",
    "industrializing",
    "free_market",
    "mixed",
    "state_coordinated",
    "planned_bureaucratic",
    "syndicalist",
    "oligarchic_clan",
    "technocratic",
)
SYSTEM_IDS = tuple(f"ADISCORD_economic_system_{suffix}" for suffix in SYSTEM_SUFFIXES)
EXPECTED_TEXTURES = {
    system_id: f"gfx/interface/ideas/laws/economic_system/{system_id}.png"
    for system_id in SYSTEM_IDS
}


def unique_child(entries, key):
    matches = [entry for entry in entries if entry.key == key]
    if len(matches) != 1 or not isinstance(matches[0].value, list):
        raise AssertionError(f"expected one block {key}, found {len(matches)}")
    return matches[0].value


def scalar(entries, key):
    matches = [entry.value for entry in entries if entry.key == key and isinstance(entry.value, str)]
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


def localisation_value(text, key):
    match = re.search(rf'(?m)^\s*{re.escape(key)}:\d*\s+"([^"]*)"', text)
    if not match:
        raise AssertionError(f"missing localisation key: {key}")
    return match.group(1)


class EconomicSystemLawContracts(unittest.TestCase):
    def test_economic_system_sprites_resolve_to_dedicated_pngs(self):
        parsed = parse_clausewitz(GFX_PATH.read_text(encoding="utf-8-sig"))
        sprite_types = unique_child(parsed, "spriteTypes")
        actual = {}
        for entry in sprite_types:
            if entry.key != "spriteType" or not isinstance(entry.value, list):
                continue
            name = scalar(entry.value, "name")
            if name.startswith("GFX_idea_ADISCORD_economic_system_"):
                system_id = name.removeprefix("GFX_idea_")
                actual[system_id] = scalar(entry.value, "texturefile")

        self.assertEqual(EXPECTED_TEXTURES, actual)
        for system_id, relative_path in EXPECTED_TEXTURES.items():
            with self.subTest(system_id=system_id), Image.open(ROOT / relative_path) as image:
                self.assertEqual("PNG", image.format)
                self.assertEqual((64, 64), image.size)
                self.assertIn("A", image.getbands())


if __name__ == "__main__":
    unittest.main()
```

This catches a missing sprite, a stale fallback, a wrong move, a wrong dimension, a non-PNG file, or lost alpha.

- [ ] **Step 3: Run the icon test and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws.EconomicSystemLawContracts.test_economic_system_sprites_resolve_to_dedicated_pngs
```

Expected: FAIL because the current nine economic-system sprites still point to fallback DDS files and the dedicated directory does not exist.

- [ ] **Step 4: Move only the nine approved source icons**

Run these path-specific PowerShell operations from the repository root:

```powershell
New-Item -ItemType Directory -Force -Path 'gfx/interface/ideas/laws/economic_system'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/аграрная.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_agrarian.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/ранняя индустриальная.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_industrializing.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/свободный рынок.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_free_market.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/смешанная.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_mixed.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/государственно-координируемая.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_state_coordinated.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/плановая.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_planned_bureaucratic.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/синдикалисткая экономика.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_syndicalist.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/олигархо-клановая.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_oligarchic_clan.png'
Move-Item -LiteralPath 'gfx/interface/ideas/laws/технократическая.png' -Destination 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_technocratic.png'
```

Do not use a wildcard or recursive move.

- [ ] **Step 5: Replace the nine fallback sprite bindings**

In `interface/ADISCORD_ideas.gfx`, rename the heading to `### A-DISCORD economic system icons`, replace the mobilization sprite name with `GFX_idea_ADISCORD_economic_system_syndicalist`, and set each texture to its literal entry from `EXPECTED_TEXTURES`, for example:

```text
spriteType = {
	name = "GFX_idea_ADISCORD_economic_system_syndicalist"
	texturefile = "gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_syndicalist.png"
}
```

Apply the same one-to-one path rule to the other eight existing sprite names.

- [ ] **Step 6: Verify GREEN and protected-file integrity**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws.EconomicSystemLawContracts.test_economic_system_sprites_resolve_to_dedicated_pngs
Get-FileHash -Algorithm SHA256 -LiteralPath 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png'
git diff --check -- interface/ADISCORD_ideas.gfx tools/tests/test_adiscord_economic_system_laws.py
```

Expected: test PASS; protected hash unchanged from the pre-move snapshot; no diff-check errors.

- [ ] **Step 7: Commit the isolated icon installation**

```powershell
git add -- 'tools/tests/test_adiscord_economic_system_laws.py' 'interface/ADISCORD_ideas.gfx' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_agrarian.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_industrializing.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_free_market.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_mixed.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_state_coordinated.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_planned_bureaucratic.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_syndicalist.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_oligarchic_clan.png' 'gfx/interface/ideas/laws/economic_system/ADISCORD_economic_system_technocratic.png'
git diff --cached --check
git commit -m "feat: install economic system law icons"
```

Confirm the protected civilian-oriented PNG and `laws.psd` are not staged.

---

### Task 2: Replace Economic-System Model 5 with Syndicalism

**Files:**
- Modify: `tools/tests/test_adiscord_economic_system_laws.py`
- Modify: `tools/tests/test_adiscord_economy_weekly_contracts.py:7189-7199,7248-7258`
- Modify: `common/ideas/_economic.txt:400-412,656-698`
- Modify: `common/scripted_triggers/ADISCORD_economy_triggers.txt:25-34,185-257`
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt:780,803,811,851-852,917,1131,2035,2149,2167,2379,3486,3500,3512,3694`
- Modify: `localisation/russian/ADISCORD_economy_l_russian.yml:205,213,221,389-390`
- Modify: `localisation/english/ADISCORD_economy_l_english.yml:108` and add the new law keys
- Modify: `tools/validators/validate_adiscord_economy_ai.py:3288-3299`

**Interfaces:**
- Consumes: numeric economy model values `0..7` and existing capability triggers.
- Produces: `ADISCORD_economic_system_syndicalist`, wrapper `ADISCORD_economy_has_idea_economic_system_syndicalist`, predicate `ADISCORD_economy_model_is_syndicalist`, and an authoritative law-to-model mapping of syndicalist to value 5.

- [ ] **Step 1: Extend the focused contract before production changes**

Add these literal expectations near the constants in `tools/tests/test_adiscord_economic_system_laws.py`:

```python
EXPECTED_SYNDICALIST_MODIFIERS = {
    "consumer_goods_expected_value": "0.05",
    "min_export": "-0.05",
    "industrial_capacity_factory": "0.03",
    "production_speed_industrial_complex_factor": "0.10",
    "production_speed_infrastructure_factor": "0.05",
    "line_change_production_efficiency_factor": "-0.05",
    "production_factory_max_efficiency_factor": "0.05",
    "production_factory_efficiency_gain_factor": "0.05",
    "political_power_gain": "-0.03",
    "stability_factor": "0.05",
    "ADISCORD_economy_tax_collection_factor": "0.05",
    "ADISCORD_economy_trade_income_factor": "-0.05",
    "ADISCORD_economy_civilian_factory_income_factor": "0.10",
    "ADISCORD_economy_building_income_factor": "0.08",
    "ADISCORD_economy_admin_expense_factor": "0.08",
    "ADISCORD_economy_creditworthiness_factor": "-0.05",
    "ADISCORD_economy_price_stability_factor": "0.05",
    "ADISCORD_economy_investment_confidence_factor": "-0.10",
    "ADISCORD_country_development_economic_growth_factor": "0.05",
}
```

Add a recursive walker and three tests to the same class:

```python
def walk(entries):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


class EconomicSystemLawContracts(unittest.TestCase):
    def test_roster_and_syndicalist_law_match_the_approved_contract(self):
        parsed = parse_clausewitz(IDEAS_PATH.read_text(encoding="utf-8-sig"))
        ideas = unique_child(parsed, "ideas")
        category = unique_child(ideas, "ADISCORD_economic_system_laws")
        law_entries = {
            entry.key: entry.value
            for entry in category
            if entry.key.startswith("ADISCORD_economic_system_") and isinstance(entry.value, list)
        }
        self.assertEqual(list(SYSTEM_IDS), list(law_entries))

        syndicalist = law_entries["ADISCORD_economic_system_syndicalist"]
        self.assertEqual("ADISCORD_economic_system_syndicalist", scalar(syndicalist, "picture"))
        self.assertEqual("300", scalar(syndicalist, "cost"))
        self.assertEqual("-1", scalar(syndicalist, "removal_cost"))
        self.assertEqual("no", scalar(syndicalist, "cancel_if_invalid"))

        availability = unique_child(syndicalist, "available")
        availability_entries = list(walk(availability))
        self.assertEqual(
            {"anarchism", "utilitarism"},
            {entry.value for entry in availability_entries if entry.key == "has_government"},
        )
        self.assertEqual(
            ["ADISCORD_labor_policy_guild_protections"],
            [entry.value for entry in availability_entries if entry.key == "has_idea"],
        )

        modifiers = unique_child(syndicalist, "modifier")
        actual_modifiers = {
            entry.key: entry.value for entry in modifiers if isinstance(entry.value, str)
        }
        self.assertEqual(EXPECTED_SYNDICALIST_MODIFIERS, actual_modifiers)

    def test_model_five_is_syndicalist_without_old_wartime_special_cases(self):
        triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        self.assertIn(
            "has_idea = ADISCORD_economic_system_syndicalist",
            block(triggers, "ADISCORD_economy_has_idea_economic_system_syndicalist"),
        )
        predicate = block(triggers, "ADISCORD_economy_model_is_syndicalist")
        self.assertIn("value = 5 compare = greater_than_or_equals", predicate)
        self.assertIn("value = 6 compare = less_than", predicate)

        refresh = block(effects, "ADISCORD_economy_update_model_and_cycle")
        self.assertIn(
            "else_if = { limit = { ADISCORD_economy_has_idea_economic_system_syndicalist = yes } set_variable = { var = ADISCORD_economy_model value = 5 } }",
            refresh,
        )
        obsolete = (
            "ADISCORD_economic_system_mobilization",
            "ADISCORD_economy_has_idea_economic_system_mobilization",
            "ADISCORD_economy_model_is_mobilization",
        )
        active_text = "\n".join((IDEAS_PATH.read_text(encoding="utf-8-sig"), triggers, effects))
        for symbol in obsolete:
            self.assertNotIn(symbol, active_text)
        self.assertNotIn("ADISCORD_economy_model_is_syndicalist", effects)

        advanced = block(triggers, "ADISCORD_economy_model_allows_advanced_taxation")
        market = block(triggers, "ADISCORD_economy_model_allows_market_expansion")
        self.assertIn("ADISCORD_economy_model_is_syndicalist = yes", advanced)
        self.assertIn("ADISCORD_economy_model_is_syndicalist = yes", market)
        for capability in (
            "ADISCORD_economy_model_allows_state_planning",
            "ADISCORD_economy_model_allows_mobilization_economy",
            "ADISCORD_economy_model_allows_emergency_extraction",
        ):
            self.assertNotIn(
                "ADISCORD_economy_model_is_syndicalist = yes",
                block(triggers, capability),
            )
        mobilization_capability = block(
            triggers, "ADISCORD_economy_model_allows_mobilization_economy"
        )
        self.assertIn("ADISCORD_economy_model_is_state_coordinated = yes", mobilization_capability)
        self.assertIn("ADISCORD_economy_model_is_planned_bureaucratic = yes", mobilization_capability)

    def test_syndicalist_localisation_is_bilingual_and_russian_keeps_bom(self):
        self.assertTrue(RU_LOC_PATH.read_bytes().startswith(b"\xef\xbb\xbf"))
        ru = RU_LOC_PATH.read_text(encoding="utf-8-sig")
        en = EN_LOC_PATH.read_text(encoding="utf-8-sig")
        self.assertEqual("Синдикалистская экономика", localisation_value(ru, "ADISCORD_economic_system_syndicalist"))
        self.assertEqual("Синдикалистская экономика", localisation_value(ru, "ADISCORD_economy_model_5"))
        self.assertEqual(
            "расширенное налогообложение, кооперативные инвестиции, гражданское строительство",
            localisation_value(ru, "ADISCORD_economy_model_unlocks_5"),
        )
        self.assertEqual(
            "административные расходы, слабые частные инвестиции и кредитоспособность",
            localisation_value(ru, "ADISCORD_economy_model_penalties_5"),
        )
        self.assertEqual("Syndicalist Economy", localisation_value(en, "ADISCORD_economic_system_syndicalist"))
        self.assertEqual("Syndicalist economy", localisation_value(en, "ADISCORD_economy_model_5"))
        self.assertNotIn("ADISCORD_economic_system_mobilization:", ru)
        self.assertGreater(len(localisation_value(ru, "ADISCORD_economic_system_syndicalist_desc")), 80)
        self.assertGreater(len(localisation_value(en, "ADISCORD_economic_system_syndicalist_desc")), 80)
```

Keep the existing icon test inside the same class; the second class line above denotes the insertion location, not a duplicate class declaration.

- [ ] **Step 2: Change the existing expected rosters before production changes**

In both suffix tuples in `tools/tests/test_adiscord_economy_weekly_contracts.py`, replace only:

```python
"mobilization",
```

with:

```python
"syndicalist",
```

This changes the expected authoritative model refresh and stable-wrapper contract before production is edited.

- [ ] **Step 3: Run the model contract and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_monthly_model_refresh_uses_only_explicit_system_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_hot_reloadable_economy_effects_use_stable_idea_wrappers
```

Expected: FAIL because the syndicalist law, wrapper, predicate, mapping, modifiers, and localisation do not yet exist and the existing contracts still expose mobilization.

- [ ] **Step 4: Replace the law definition and detach closed economy from the removed type**

In `common/ideas/_economic.txt`, remove `has_idea = ADISCORD_economic_system_mobilization` from `closed_economy.available`; do not change `war_economy` or `tot_economic_mobilisation`.

Replace the old mobilization law block with:

```text
ADISCORD_economic_system_syndicalist = {
	picture = ADISCORD_economic_system_syndicalist
	cost = 300
	removal_cost = -1

	available = {
		OR = {
			has_government = anarchism
			has_government = utilitarism
			has_idea = ADISCORD_labor_policy_guild_protections
		}
	}

	modifier = {
		consumer_goods_expected_value = 0.05
		min_export = -0.05
		industrial_capacity_factory = 0.03
		production_speed_industrial_complex_factor = 0.10
		production_speed_infrastructure_factor = 0.05
		line_change_production_efficiency_factor = -0.05
		production_factory_max_efficiency_factor = 0.05
		production_factory_efficiency_gain_factor = 0.05
		political_power_gain = -0.03
		stability_factor = 0.05
		ADISCORD_economy_tax_collection_factor = 0.05
		ADISCORD_economy_trade_income_factor = -0.05
		ADISCORD_economy_civilian_factory_income_factor = 0.10
		ADISCORD_economy_building_income_factor = 0.08
		ADISCORD_economy_admin_expense_factor = 0.08
		ADISCORD_economy_creditworthiness_factor = -0.05
		ADISCORD_economy_price_stability_factor = 0.05
		ADISCORD_economy_investment_confidence_factor = -0.10
		ADISCORD_country_development_economic_growth_factor = 0.05
	}

	cancel_if_invalid = no
}
```

- [ ] **Step 5: Replace model-5 wrappers and capability membership**

In `common/scripted_triggers/ADISCORD_economy_triggers.txt`:

- replace the economic-system mobilization wrapper with the syndicalist wrapper;
- replace `ADISCORD_economy_model_is_mobilization` with `ADISCORD_economy_model_is_syndicalist`, retaining the range `>= 5` and `< 6`;
- replace the old predicate with syndicalist in `ADISCORD_economy_model_allows_advanced_taxation`;
- add syndicalist to `ADISCORD_economy_model_allows_market_expansion`;
- remove the old model-5 predicate from `ADISCORD_economy_model_allows_mobilization_economy` and `ADISCORD_economy_model_allows_emergency_extraction`;
- keep state-coordinated and planned-bureaucratic membership in both those existing capability blocks.

- [ ] **Step 6: Remove former wartime model-5 branches and map syndicalism to value 5**

In `common/scripted_effects/ADISCORD_economy_effects.txt`, delete the complete `if` statements keyed by `ADISCORD_economy_model_is_mobilization` from:

- business-building income (`0.75`);
- consumer-cluster income (`0.70`) and consumer income (`-0.8`);
- forced factory income (`0`), including its mobilization-only comment;
- overall income (`-5`);
- military-factory expenses (`1.15`);
- inflation pressure (`+0.5`);
- wartime development (`-8`, `0.70`);
- stretched score (`+10`);
- military-investment army development and fatigue (`+8`, `+3`);
- war-tax cash and fatigue (`+25`, `+3`).

In `ADISCORD_economy_update_model_and_cycle`, replace the old law wrapper branch with exactly:

```text
else_if = { limit = { ADISCORD_economy_has_idea_economic_system_syndicalist = yes } set_variable = { var = ADISCORD_economy_model value = 5 } }
```

Do not introduce syndicalist replacements for the deleted hidden wartime adjustments.

- [ ] **Step 7: Add bilingual player text and update Russian model details**

In the Russian file, use:

```yaml
 ADISCORD_economy_model_5: "Синдикалистская экономика"
 ADISCORD_economy_model_unlocks_5: "расширенное налогообложение, кооперативные инвестиции, гражданское строительство"
 ADISCORD_economy_model_penalties_5: "административные расходы, слабые частные инвестиции и кредитоспособность"
 ADISCORD_economic_system_syndicalist: "Синдикалистская экономика"
 ADISCORD_economic_system_syndicalist_desc: "Предприятия управляются рабочими объединениями и отраслевыми союзами, которые согласуют производство между коллективами. Такая система укрепляет занятость и гражданскую промышленность, но ограничивает частные инвестиции и требует постоянной координации."
```

In the English file, use:

```yaml
 ADISCORD_economy_model_5: "Syndicalist economy"
 ADISCORD_economic_system_syndicalist: "Syndicalist Economy"
 ADISCORD_economic_system_syndicalist_desc: "Enterprises are managed by worker associations and industrial unions that coordinate production between collectives. The system supports employment and civilian industry, but constrains private investment and requires continuous coordination."
```

Remove only the two obsolete Russian `ADISCORD_economic_system_mobilization` keys. Preserve the Russian BOM.

- [ ] **Step 8: Align the economy AI validator's authoritative roster**

In `tools/validators/validate_adiscord_economy_ai.py`, replace `"mobilization"` with `"syndicalist"` in the nine-system loop. Do not rename or remove the separate `ADISCORD_economy_model_allows_mobilization_economy` validator/runtime capability.

- [ ] **Step 9: Verify GREEN for model 5 and the existing economy contracts**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_monthly_model_refresh_uses_only_explicit_system_laws tools.tests.test_adiscord_economy_weekly_contracts.WeeklyEconomyContracts.test_hot_reloadable_economy_effects_use_stable_idea_wrappers
python -B tools/validators/validate_adiscord_economy_ai.py
git diff --check -- common/ideas/_economic.txt common/scripted_triggers/ADISCORD_economy_triggers.txt common/scripted_effects/ADISCORD_economy_effects.txt localisation/russian/ADISCORD_economy_l_russian.yml localisation/english/ADISCORD_economy_l_english.yml tools/tests/test_adiscord_economic_system_laws.py tools/tests/test_adiscord_economy_weekly_contracts.py tools/validators/validate_adiscord_economy_ai.py
```

Expected: all tests PASS; validator prints `A-DISCORD economy/AI validation: OK`; diff check is clean.

- [ ] **Step 10: Commit the isolated law/model replacement**

```powershell
git add -- 'common/ideas/_economic.txt' 'common/scripted_triggers/ADISCORD_economy_triggers.txt' 'common/scripted_effects/ADISCORD_economy_effects.txt' 'localisation/russian/ADISCORD_economy_l_russian.yml' 'localisation/english/ADISCORD_economy_l_english.yml' 'tools/tests/test_adiscord_economic_system_laws.py' 'tools/tests/test_adiscord_economy_weekly_contracts.py' 'tools/validators/validate_adiscord_economy_ai.py'
git diff --cached --check
git commit -m "feat: replace mobilization system with syndicalism"
```

---

### Task 3: Assign Requested Starting Economic Systems

**Files:**
- Modify: `tools/tests/test_adiscord_economic_system_laws.py`
- Modify: `history/countries/STP - StepanLand.txt:36-51`
- Modify: `history/countries/NOD - Nodral.txt` in its starting `add_ideas` block
- Modify: `history/countries/VAL - ValeraLand.txt` in its starting `add_ideas` block
- Modify: `history/countries/APH - Anthropophagorum.txt:23-34`
- Verify unchanged assignment: `history/countries/OSF - FoedusOssifractorum.txt`
- Verify unchanged assignment: `history/countries/CIN - AshTribe.txt`

**Interfaces:**
- Consumes: final `SYSTEM_IDS` from the focused test and each country's top-level `add_ideas` block.
- Produces: exactly one starting economic-system law for each requested tag.

- [ ] **Step 1: Add the failing starting-law test**

Add the literal country mapping:

```python
STARTING_SYSTEMS = {
    "STP - StepanLand.txt": "ADISCORD_economic_system_oligarchic_clan",
    "NOD - Nodral.txt": "ADISCORD_economic_system_oligarchic_clan",
    "VAL - ValeraLand.txt": "ADISCORD_economic_system_state_coordinated",
    "APH - Anthropophagorum.txt": "ADISCORD_economic_system_agrarian",
    "OSF - FoedusOssifractorum.txt": "ADISCORD_economic_system_agrarian",
    "CIN - AshTribe.txt": "ADISCORD_economic_system_agrarian",
}
```

Add this method to `EconomicSystemLawContracts`:

```python
def test_requested_countries_start_with_exactly_one_approved_system(self):
    for filename, expected in STARTING_SYSTEMS.items():
        with self.subTest(filename=filename):
            path = ROOT / "history" / "countries" / filename
            parsed = parse_clausewitz(path.read_text(encoding="utf-8-sig"))
            add_ideas = unique_child(parsed, "add_ideas")
            assigned = [
                entry.value
                for entry in add_ideas
                if entry.key == "" and isinstance(entry.value, str) and entry.value in SYSTEM_IDS
            ]
            self.assertEqual([expected], assigned)
```

This catches a missing assignment, wrong system, or duplicate economic-system law while ignoring unrelated national ideas and ministers.

- [ ] **Step 2: Run the starting-law test and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws.EconomicSystemLawContracts.test_requested_countries_start_with_exactly_one_approved_system
```

Expected: FAIL for STP, NOD, and VAL because they have no explicit economic-system law, and for APH because it currently has the oligarchic-clan law.

- [ ] **Step 3: Make the minimal country-history edits**

Inside each existing top-level `add_ideas` block:

- add `ADISCORD_economic_system_oligarchic_clan` to STP;
- add `ADISCORD_economic_system_oligarchic_clan` to NOD;
- add `ADISCORD_economic_system_state_coordinated` to VAL;
- replace APH's `ADISCORD_economic_system_oligarchic_clan` with `ADISCORD_economic_system_agrarian`;
- leave OSF and CIN content unchanged because each already has the required agrarian law.

Do not reorder or edit other ideas, ministers, OOBs, politics, technologies, or stockpiles.

- [ ] **Step 4: Verify GREEN and commit the starting assignments**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws.EconomicSystemLawContracts.test_requested_countries_start_with_exactly_one_approved_system
git diff --check -- 'history/countries/STP - StepanLand.txt' 'history/countries/NOD - Nodral.txt' 'history/countries/VAL - ValeraLand.txt' 'history/countries/APH - Anthropophagorum.txt' tools/tests/test_adiscord_economic_system_laws.py
git add -- 'history/countries/STP - StepanLand.txt' 'history/countries/NOD - Nodral.txt' 'history/countries/VAL - ValeraLand.txt' 'history/countries/APH - Anthropophagorum.txt' 'tools/tests/test_adiscord_economic_system_laws.py'
git diff --cached --check
git commit -m "feat: assign starting economic system laws"
```

Do not stage OSF or CIN when their content remains unchanged.

---

### Task 4: Align the Pending Law-Localisation Plan

**Files:**
- Modify: `docs/superpowers/plans/2026-08-16-adiscord-law-localisation-rewrite.md:519,532`

**Interfaces:**
- Consumes: the final law ID and bilingual names implemented in Task 2.
- Produces: a future localisation plan that no longer reintroduces the removed mobilization economic-system key.

- [ ] **Step 1: Replace the two stale expected-name entries**

In the Russian expected-name dictionary replace:

```python
"ADISCORD_economic_system_mobilization": "Мобилизационная экономика",
```

with:

```python
"ADISCORD_economic_system_syndicalist": "Синдикалистская экономика",
```

In the English expected-name dictionary replace:

```python
"ADISCORD_economic_system_mobilization": "Mobilization Economy",
```

with:

```python
"ADISCORD_economic_system_syndicalist": "Syndicalist Economy",
```

- [ ] **Step 2: Check and commit only the plan alignment**

Run:

```powershell
git diff --check -- docs/superpowers/plans/2026-08-16-adiscord-law-localisation-rewrite.md
git add -- docs/superpowers/plans/2026-08-16-adiscord-law-localisation-rewrite.md
git diff --cached --check
git commit -m "docs: align law localisation plan with syndicalism"
```

---

### Task 5: Run the Release Gate Without Touching Protected Work

**Files:**
- Verify only; no planned production edits.

**Interfaces:**
- Consumes: Tasks 1-4 and the repository's existing validation entry points.
- Produces: static evidence plus a precise statement of the remaining manual runtime gate.

- [ ] **Step 1: Run the focused test and economy suites**

```powershell
python -B -m unittest tools.tests.test_adiscord_economic_system_laws
python -B -m unittest tools.tests.test_adiscord_economy_weekly_contracts
python -B tools/validators/validate_adiscord_economy_ai.py
```

Expected: all unittest modules PASS and the validator prints `A-DISCORD economy/AI validation: OK`.

- [ ] **Step 2: Prove the protected asset remains untouched and untracked at its original path**

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png'
git status --short -- 'gfx/interface/ideas/laws/Гражданско-ориентированная экономика ур1.png' 'tools/assets/source/laws.psd'
```

Expected: the hash matches the baseline captured at Task 1; both protected user files remain outside every task commit.

- [ ] **Step 3: Run the repository-wide static gate**

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: validator PASS and both diff checks clean. If the full validator reports a pre-existing unrelated failure, record the exact failure and demonstrate that the focused suites remain green; do not repair unrelated dirty work.

- [ ] **Step 4: Audit final scope and obsolete economic-system references**

```powershell
rg -n "ADISCORD_economic_system_mobilization|ADISCORD_economy_has_idea_economic_system_mobilization|ADISCORD_economy_model_is_mobilization" common interface localisation tools/tests tools/validators
git status --short
git log --oneline -6
```

Expected: no active hit for the three obsolete economic-system symbols. References to the separate vanilla-style economy laws, `tot_economic_mobilisation`, `ADISCORD_economy_model_allows_mobilization_economy`, demobilization, and protected user artwork are valid and must remain.

- [ ] **Step 5: Report the runtime follow-up accurately**

Report the focused/full static results, created commits, exact protected-file status, and the fact that Hearts of Iron IV was not launched. Request a full game restart and fresh-campaign UI check for icon loading, Russian text wrapping, STP/NOD/VAL/APH/OSF/CIN starts, and Clausewitz runtime behavior.
