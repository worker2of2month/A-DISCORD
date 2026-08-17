# A-DISCORD Global Infantry Weapon Progression Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make all A-DISCORD infantry equipment select one global eight-model 3D weapon progression while preserving generic and country-specific soldier bodies.

**Architecture:** A late `zy_` asset defines neutral weapon wrappers and the generic base plus `_2`-`_8` infantry entity chain. The existing later `zz_` asset keeps custom country uniforms and attaches those same wrappers. The directly maintained equipment database selects visual levels `0, 0, 1, 2, 3, 4, 5, 6, 7`, while focused tests and the technology validator enforce the complete contract.

**Tech Stack:** HOI4 Clausewitz equipment and `.asset` syntax, Python 3 `unittest`, existing technology validator, PowerShell read-only vanilla-asset audit.

## Global Constraints

- Use the exact sequence Johnson M42, Arisaka, Mondragon M1908, Mauser 712, Bergmann MP-29, Thompson, PPSh-41, Mendoza RM2.
- Map the nine equipment generations to visual levels exactly `0, 0, 1, 2, 3, 4, 5, 6, 7`.
- Load Paradox weapon entities directly from Waking the Tiger and Man the Guns; do not copy, rename, crop, or edit vanilla meshes and textures.
- Preserve every existing soldier body, animation parent, scale, and non-weapon prop for generic, STP, NOD, VAL, CIN, OSF, APH infantry, and APH mountaineers.
- Remove direct ENG and USA weapon attachments only from A-DISCORD-owned custom infantry entities.
- Keep equipment IDs, stats, unlocks, technology layout, icons, localisation, AI, division templates, starting technology, and stockpiles unchanged.
- Target fresh campaigns only; add no save migration.
- Preserve unrelated dirty work. Do not stage or commit any path without explicit user authorization.
- Static validation is not runtime proof; the release gate requires a full HOI4 restart, fresh campaign, fresh logs, and visual inspection.

## File Structure

- Modify `common/units/equipment/ADISCORD_infantry_equipment.txt`: directly maintained visual-level selection for the nine infantry-equipment generations.
- Create `gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset`: neutral wrappers plus generic base and `_2`-`_8` entity definitions.
- Modify `gfx/entities/zz_ADISCORD_country_infantry.asset`: preserve custom bodies and add the global weapon wrapper attachments through `_8`.
- Modify `tools/validators/validate_adiscord_tech_doctrine.py`: production static contract for equipment levels, asset load order, entity coverage, wrapper mapping, and prohibited legacy attachments.
- Modify `tools/tests/test_build_adiscord_technology_system.py`: focused generated-equipment expectation.
- Create `tools/tests/test_adiscord_infantry_weapon_progression.py`: isolated entity parser and exact progression tests.
- Modify `tools/tests/test_validate_adiscord_technology_contracts.py`: negative validator checks for a regressed visual level and a missing weapon wrapper.

---

### Task 1: Lock the Equipment Visual-Level Contract

**Files:**
- Modify: `tools/tests/test_build_adiscord_technology_system.py:669-707`
- Modify: `common/units/equipment/ADISCORD_infantry_equipment.txt:20-150`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py:1435-1465`

**Interfaces:**
- Consumes: existing `validator.collect_equipment_blocks() -> dict[str, str]` and existing equipment IDs.
- Produces: the exact visual-level sequence that Tasks 2 and 3 map to entity suffixes.

- [ ] **Step 1: Change the focused test to the approved sequence**

Replace the final expectation in
`test_infantry_equipment_visual_levels_mark_real_weapon_generations` with:

```python
self.assertEqual(actual_levels, [0, 0, 1, 2, 3, 4, 5, 6, 7])
```

- [ ] **Step 2: Run the focused test and verify the contract fails**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system.CompactTechnologyTreeContractTests.test_infantry_equipment_visual_levels_mark_real_weapon_generations -v
```

Expected: `FAIL`; the current output is `[0, 1, 2, 2, 2, 3, 3, 3, 3]`.

- [ ] **Step 3: Update only the nine equipment visual levels**

Set the blocks in `common/units/equipment/ADISCORD_infantry_equipment.txt` to:

```text
infantry_equipment_0                    visual_level = 0
ADISCORD_infantry_equipment_2156       visual_level = 0
ADISCORD_infantry_equipment_2163       visual_level = 1
ADISCORD_infantry_equipment_2168       visual_level = 2
ADISCORD_infantry_equipment_2170       visual_level = 3
ADISCORD_infantry_equipment_2178       visual_level = 4
ADISCORD_infantry_equipment_2183       visual_level = 5
ADISCORD_infantry_equipment_2193       visual_level = 6
ADISCORD_infantry_equipment_2200       visual_level = 7
```

Do not change any adjacent stat, parent, resource, priority, or squad-weapon
block.

- [ ] **Step 4: Mirror the sequence in the production validator**

Replace `expected_levels` inside `check_infantry_visual_model_chain()` with:

```python
expected_levels = {
    "infantry_equipment_0": 0,
    "ADISCORD_infantry_equipment_2156": 0,
    "ADISCORD_infantry_equipment_2163": 1,
    "ADISCORD_infantry_equipment_2168": 2,
    "ADISCORD_infantry_equipment_2170": 3,
    "ADISCORD_infantry_equipment_2178": 4,
    "ADISCORD_infantry_equipment_2183": 5,
    "ADISCORD_infantry_equipment_2193": 6,
    "ADISCORD_infantry_equipment_2200": 7,
}
```

- [ ] **Step 5: Run the focused equipment test and validator**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system.CompactTechnologyTreeContractTests.test_infantry_equipment_visual_levels_mark_real_weapon_generations -v
python -B -m tools.builders.build_adiscord_technology_system
```

Expected: the unit test and builder-backed validator pass without a
visual-level mismatch.

- [ ] **Step 6: Review the scoped diff without staging it**

Run:

```powershell
git diff -- common/units/equipment/ADISCORD_infantry_equipment.txt tools/validators/validate_adiscord_tech_doctrine.py tools/tests/test_build_adiscord_technology_system.py
```

Expected: only the test, validator mapping, and nine visual-level lines differ.

---

### Task 2: Add Neutral Weapon Wrappers and the Generic Entity Chain

**Files:**
- Create: `tools/tests/test_adiscord_infantry_weapon_progression.py`
- Create: `gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py:1465-1540`

**Interfaces:**
- Consumes: visual level 0-7 from Task 1 and the vanilla DLC source entities listed below.
- Produces: the `ADISCORD_infantry_weapon_0_*_entity` through
  `ADISCORD_infantry_weapon_7_*_entity` wrapper families and generic
  `infantry_entity`/`generic_infantry_2_entity` through `_8`.

- [ ] **Step 1: Create an isolated parser and wrapper contract test**

Create `tools/tests/test_adiscord_infantry_weapon_progression.py` with these
constants and helpers:

```python
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tools.validators import validate_adiscord_tech_doctrine as validator


ROOT = Path(__file__).resolve().parents[2]
PROGRESSION_ASSET = ROOT / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
COUNTRY_ASSET = ROOT / "gfx/entities/zz_ADISCORD_country_infantry.asset"

SOURCE_PREFIXES = (
    "HOL_infantry_weapon_rifle",
    "SHX_infantry_weapon_rifle",
    "MEX_infantry_weapon_rifle",
    "XSM_infantry_weapon_mg",
    "HOL_infantry_weapon_mg",
    "YUN_infantry_weapon_mg",
    "PRC_infantry_weapon_mg",
    "MEX_infantry_weapon_mg",
)
POSES = ("right", "left", "long_idle")
ATTACHMENTS = (
    ("rifle1", "Right_Hand_node", "right"),
    ("rifle2", "Left_Hand_node", "left"),
    ("rifle3", "mid_back_node", "long_idle"),
    ("rifle4", "Root_node_2", "right"),
)


def entity_blocks(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    blocks: dict[str, str] = {}
    for match in re.finditer(r"(?m)^\s*entity\s*=\s*\{", text):
        block = validator.extract_block(text, match.start())
        name = re.search(r'\bname\s*=\s*"([A-Za-z0-9_]+)"', block)
        if name:
            blocks[name.group(1)] = block
    return blocks


def generic_entity_name(level: int) -> str:
    return "infantry_entity" if level == 0 else f"generic_infantry_{level + 1}_entity"


def custom_entity_name(prefix: str, level: int) -> str:
    return f"{prefix}_entity" if level == 0 else f"{prefix}_{level + 1}_entity"
```

Add the first contract test:

```python
class GlobalInfantryWeaponProgressionTests(unittest.TestCase):
    def test_all_weapon_wrappers_clone_the_approved_vanilla_entities(self) -> None:
        blocks = entity_blocks(PROGRESSION_ASSET)
        for level, source_prefix in enumerate(SOURCE_PREFIXES):
            for pose in POSES:
                wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                source = f"{source_prefix}_{pose}_entity"
                with self.subTest(level=level, pose=pose):
                    self.assertIn(wrapper, blocks)
                    self.assertRegex(
                        blocks[wrapper],
                        rf'\bclone\s*=\s*"{re.escape(source)}"',
                    )
                    self.assertNotRegex(blocks[wrapper], r"\bpdxmesh\s*=")
```

- [ ] **Step 2: Add the generic selection-chain test**

Append:

```python
    def test_generic_entity_chain_attaches_the_matching_wrapper_level(self) -> None:
        blocks = entity_blocks(PROGRESSION_ASSET)
        for level in range(8):
            entity = generic_entity_name(level)
            with self.subTest(level=level, entity=entity):
                self.assertIn(entity, blocks)
                for attachment, node, pose in ATTACHMENTS:
                    wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                    self.assertRegex(
                        blocks[entity],
                        rf'attach\s*=\s*\{{\s*name\s*=\s*"{attachment}"\s+'
                        rf'{node}\s*=\s*"{wrapper}"\s*\}}',
                    )
```

- [ ] **Step 3: Run the new tests and verify they fail because the asset is absent**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_infantry_weapon_progression -v
```

Expected: `ERROR` or `FAIL` naming
`gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset`.

- [ ] **Step 4: Create the 24 neutral wrapper entities**

At the top of `zy_ADISCORD_infantry_weapon_progression.asset`, document the
load order and create exactly three blocks per level. The complete mapping is:

```text
level 0 -> HOL_infantry_weapon_rifle_{right,left,long_idle}_entity
level 1 -> SHX_infantry_weapon_rifle_{right,left,long_idle}_entity
level 2 -> MEX_infantry_weapon_rifle_{right,left,long_idle}_entity
level 3 -> XSM_infantry_weapon_mg_{right,left,long_idle}_entity
level 4 -> HOL_infantry_weapon_mg_{right,left,long_idle}_entity
level 5 -> YUN_infantry_weapon_mg_{right,left,long_idle}_entity
level 6 -> PRC_infantry_weapon_mg_{right,left,long_idle}_entity
level 7 -> MEX_infantry_weapon_mg_{right,left,long_idle}_entity
```

Every block uses this exact Clausewitz form, substituting the concrete level,
pose, and source from the table:

```text
entity = {
    clone = "HOL_infantry_weapon_rifle_right_entity"
    name = "ADISCORD_infantry_weapon_0_right_entity"
}
```

Do not add `pdxmesh`, scale, transform, animation, or state lines to wrappers.

- [ ] **Step 5: Add the generic base and `_2`-`_8` entity chain**

Define `infantry_entity` from `infantry_rifle_entity` with
`generic_western_european_rifle_infantry_mesh`, existing lighter/cigarette
props, scale `0.8`, and level-0 wrappers. Define
`generic_infantry_2_entity` from `infantry_2_entity` with
`generic_western_european_mg_infantry_mesh`, the same props and scale, and
level-1 wrappers. Define `_3` through `_8` from `infantry_2_entity` with the
same MG body, props, and scale; each contains the four concrete attachments
for visual levels 2-7.

Each level's weapon portion must use these exact names:

```text
visual 0: ADISCORD_infantry_weapon_0_right_entity, ADISCORD_infantry_weapon_0_left_entity, ADISCORD_infantry_weapon_0_long_idle_entity
visual 1: ADISCORD_infantry_weapon_1_right_entity, ADISCORD_infantry_weapon_1_left_entity, ADISCORD_infantry_weapon_1_long_idle_entity
visual 2: ADISCORD_infantry_weapon_2_right_entity, ADISCORD_infantry_weapon_2_left_entity, ADISCORD_infantry_weapon_2_long_idle_entity
visual 3: ADISCORD_infantry_weapon_3_right_entity, ADISCORD_infantry_weapon_3_left_entity, ADISCORD_infantry_weapon_3_long_idle_entity
visual 4: ADISCORD_infantry_weapon_4_right_entity, ADISCORD_infantry_weapon_4_left_entity, ADISCORD_infantry_weapon_4_long_idle_entity
visual 5: ADISCORD_infantry_weapon_5_right_entity, ADISCORD_infantry_weapon_5_left_entity, ADISCORD_infantry_weapon_5_long_idle_entity
visual 6: ADISCORD_infantry_weapon_6_right_entity, ADISCORD_infantry_weapon_6_left_entity, ADISCORD_infantry_weapon_6_long_idle_entity
visual 7: ADISCORD_infantry_weapon_7_right_entity, ADISCORD_infantry_weapon_7_left_entity, ADISCORD_infantry_weapon_7_long_idle_entity
```

For each row, `rifle1`/`rifle4` use the listed right entity, `rifle2` uses the
listed left entity, and `rifle3` uses the listed long-idle entity.

- [ ] **Step 6: Extend the production validator for the progression asset**

Inside `check_infantry_visual_model_chain()` add:

```python
progression_asset = (
    ROOT / "gfx" / "entities" / "zy_ADISCORD_infantry_weapon_progression.asset"
)
if not progression_asset.exists():
    issues.append("global infantry weapon progression asset missing")
else:
    progression_text = read_text(progression_asset)
    if progression_asset.name.casefold() >= canonical_asset.name.casefold():
        issues.append("weapon progression asset must load before country infantry asset")
```

Use the same eight `SOURCE_PREFIXES` values from the test to check all 24
wrapper names and their exact `clone` parents. Check all eight generic entity
names and four matching wrapper attachments. Keep the constants local to this
function so the validator remains self-contained.

- [ ] **Step 7: Run the isolated tests and production validator**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_infantry_weapon_progression -v
python -B -m tools.builders.build_adiscord_technology_system
```

Expected: wrapper and generic tests pass. Validator failures, if any, are
limited to custom country levels not yet added in Task 3.

- [ ] **Step 8: Review the scoped diff without staging it**

Run:

```powershell
git diff -- gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset tools/tests/test_adiscord_infantry_weapon_progression.py tools/validators/validate_adiscord_tech_doctrine.py
```

Expected: one new progression asset, one focused test module, and validator
contract additions only.

---

### Task 3: Preserve Custom Uniforms Through Visual Level 7

**Files:**
- Modify: `tools/tests/test_adiscord_infantry_weapon_progression.py`
- Modify: `gfx/entities/zz_ADISCORD_country_infantry.asset`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py:1490-1540`

**Interfaces:**
- Consumes: Task 2's neutral wrappers and the exact helper functions in the focused test module.
- Produces: complete base plus `_2`-`_8` custom entity families with unchanged body identity.

- [ ] **Step 1: Add the custom-family coverage and attachment test**

Append to `GlobalInfantryWeaponProgressionTests`:

```python
    def test_custom_uniform_families_cover_every_visual_level(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        families = (
            "STP_infantry",
            "NOD_infantry",
            "VAL_infantry",
            "CIN_infantry",
            "OSF_infantry",
            "APH_infantry",
            "APH_mountaineers",
        )
        for prefix in families:
            for level in range(8):
                entity = custom_entity_name(prefix, level)
                with self.subTest(prefix=prefix, level=level):
                    self.assertIn(entity, blocks)
                    for attachment, node, pose in ATTACHMENTS:
                        wrapper = f"ADISCORD_infantry_weapon_{level}_{pose}_entity"
                        self.assertRegex(
                            blocks[entity],
                            rf'attach\s*=\s*\{{\s*name\s*=\s*"{attachment}"\s+'
                            rf'{node}\s*=\s*"{wrapper}"\s*\}}',
                        )

    def test_custom_uniform_asset_has_no_legacy_regional_weapon_attach(self) -> None:
        text = COUNTRY_ASSET.read_text(encoding="utf-8")
        self.assertNotRegex(text, r'"(?:ENG|USA)_infantry_weapon_')

    def test_custom_family_base_meshes_remain_unchanged(self) -> None:
        blocks = entity_blocks(COUNTRY_ASSET)
        expected_meshes = {
            "STP_infantry_entity": "STP_infantry_hedonist_mesh",
            "VAL_infantry_entity": "VAL_infantry_mesh",
            "CIN_infantry_entity": "ETH_irregular_infantry_mesh",
            "OSF_infantry_entity": "ETH_irregular_infantry_mesh",
            "APH_infantry_entity": "APH_irregular_infantry_mesh",
            "APH_mountaineers_entity": "APH_afg_militia_rifle_mesh",
            "APH_mountaineers_2_entity": "APH_afg_militia_mg_mesh",
        }
        for entity, mesh in expected_meshes.items():
            with self.subTest(entity=entity):
                self.assertRegex(
                    blocks[entity],
                    rf'\bpdxmesh\s*=\s*"{re.escape(mesh)}"',
                )
```

- [ ] **Step 2: Run the new custom-family tests and verify they fail**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_infantry_weapon_progression.GlobalInfantryWeaponProgressionTests.test_custom_uniform_families_cover_every_visual_level tools.tests.test_adiscord_infantry_weapon_progression.GlobalInfantryWeaponProgressionTests.test_custom_uniform_asset_has_no_legacy_regional_weapon_attach tools.tests.test_adiscord_infantry_weapon_progression.GlobalInfantryWeaponProgressionTests.test_custom_family_base_meshes_remain_unchanged -v
```

Expected: `FAIL`; current families end at `_3`, and ENG/USA attachments remain.

- [ ] **Step 3: Replace custom-family weapon attachments with neutral wrappers**

For every base and `_2` entity already containing four weapon attachments,
replace the source names with the exact level-0 or level-1 wrappers. Keep all
existing `clone`, `pdxmesh`, props, and scale lines.

For each of the seven named families, make the selection suffixes and levels
exact:

```text
base entity -> level 0 wrappers
_2 entity   -> level 1 wrappers
_3 entity   -> level 2 wrappers
_4 entity   -> level 3 wrappers
_5 entity   -> level 4 wrappers
_6 entity   -> level 5 wrappers
_7 entity   -> level 6 wrappers
_8 entity   -> level 7 wrappers
```

The prefixes are exactly `STP_infantry`, `NOD_infantry`, `VAL_infantry`,
`CIN_infantry`, `OSF_infantry`, `APH_infantry`, and `APH_mountaineers`.

- [ ] **Step 4: Add concrete `_4`-`_8` entities without changing bodies**

For STP, VAL, CIN, OSF, and APH infantry, clone the family's `_2` body entity,
then declare the four wrapper attachments for that concrete level. For NOD,
clone the corresponding STP level so its body remains shared, then redeclare
the same four level wrappers. For APH mountaineers, clone
`APH_mountaineers_2_entity` so the existing MG soldier body remains, then
declare the level wrappers.

Every new entity uses this complete shape with concrete names and numbers:

```text
entity = {
    clone = "STP_infantry_2_entity"
    name = "STP_infantry_4_entity"

    attach = { name = "rifle1" Right_Hand_node = "ADISCORD_infantry_weapon_3_right_entity" }
    attach = { name = "rifle2" Left_Hand_node = "ADISCORD_infantry_weapon_3_left_entity" }
    attach = { name = "rifle3" mid_back_node = "ADISCORD_infantry_weapon_3_long_idle_entity" }
    attach = { name = "rifle4" Root_node_2 = "ADISCORD_infantry_weapon_3_right_entity" }
}
```

Repeat the explicit block for every family and level; do not leave template
tokens in the asset.

- [ ] **Step 5: Expand the production validator's custom coverage**

Replace the current fixed entity tuple and three-clone check with a loop:

```python
custom_prefixes = (
    "STP_infantry",
    "NOD_infantry",
    "VAL_infantry",
    "CIN_infantry",
    "OSF_infantry",
    "APH_infantry",
    "APH_mountaineers",
)
for prefix in custom_prefixes:
    for level in range(8):
        suffix = "" if level == 0 else f"_{level + 1}"
        entity = f"{prefix}{suffix}_entity"
        if not re.search(rf'\bname\s*=\s*"{re.escape(entity)}"', asset_text):
            issues.append(f"A-Discord infantry asset is missing {entity}")
```

Also report an issue if `asset_text` matches:

```python
r'"(?:ENG|USA)_infantry_weapon_'
```

Reuse the entity-block extraction already present in the function to validate
the four matching wrapper attachments for all 56 custom entities.

- [ ] **Step 6: Run focused tests and the production validator**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_infantry_weapon_progression -v
python -B -m unittest tools.tests.test_build_adiscord_technology_system -v
python -B -m tools.builders.build_adiscord_technology_system
```

Expected: all commands pass with no missing entity, wrong wrapper, legacy
regional attachment, or visual-level issue.

- [ ] **Step 7: Review the country-asset diff without staging it**

Run:

```powershell
git diff -- gfx/entities/zz_ADISCORD_country_infantry.asset tools/tests/test_adiscord_infantry_weapon_progression.py tools/validators/validate_adiscord_tech_doctrine.py
```

Expected: body meshes and props are preserved; only weapon sources and
selection-level coverage change.

---

### Task 4: Add Validator Regression Fixtures and Audit the Vanilla Chains

**Files:**
- Modify: `tools/tests/test_validate_adiscord_technology_contracts.py`
- Verify: `tools/validators/validate_adiscord_tech_doctrine.py`
- Verify: installed HOI4 files under `Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/`

**Interfaces:**
- Consumes: completed static validator from Tasks 1-3.
- Produces: proof that representative regressions are detected and every external source chain exists.

- [ ] **Step 1: Add a negative test for a visual-level regression**

Add `import re` beside the existing standard-library imports, then add this
test to `TechnologyValidatorNegativeTests`:

```python
    def test_infantry_visual_contract_rejects_regressed_equipment_level(self) -> None:
        equipment_path = (
            validator.ROOT
            / "common/units/equipment/ADISCORD_infantry_equipment.txt"
        )
        equipment = validator.read_text(equipment_path)
        match = re.search(
            r"(?m)^\s*ADISCORD_infantry_equipment_2200\s*=\s*\{",
            equipment,
        )
        self.assertIsNotNone(match)
        start = match.start()
        block = validator.extract_block(equipment, start)
        self.assertIn("visual_level = 7", block)
        broken_block = block.replace("visual_level = 7", "visual_level = 3", 1)
        broken_equipment = (
            equipment[:start] + broken_block + equipment[start + len(block):]
        )

        original_read = validator.read_text

        def fake_read(path: Path) -> str:
            return broken_equipment if path == equipment_path else original_read(path)

        with patch.object(validator, "read_text", side_effect=fake_read):
            issues = validator.check_infantry_visual_model_chain()
        self.assertTrue(
            any("ADISCORD_infantry_equipment_2200" in issue for issue in issues),
            issues,
        )
```

- [ ] **Step 2: Add a negative test for a missing wrapper**

Add this fixture, which intercepts only the progression asset read:

```python
    def test_infantry_visual_contract_rejects_missing_weapon_wrapper(self) -> None:
        progression_path = (
            validator.ROOT
            / "gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset"
        )
        progression = validator.read_text(progression_path)
        broken_progression = progression.replace(
            'name = "ADISCORD_infantry_weapon_7_right_entity"',
            'name = "ADISCORD_infantry_weapon_7_right_entity_BROKEN"',
            1,
        )
        self.assertNotEqual(progression, broken_progression)
        original_read = validator.read_text

        def fake_read(path: Path) -> str:
            if path == progression_path:
                return broken_progression
            return original_read(path)

        with patch.object(validator, "read_text", side_effect=fake_read):
            issues = validator.check_infantry_visual_model_chain()
        self.assertTrue(
            any("ADISCORD_infantry_weapon_7_right_entity" in issue for issue in issues),
            issues,
        )
```

- [ ] **Step 3: Run validator fixture tests**

Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_technology_contracts -v
```

Expected: all tests pass, proving the validator catches both regressions.

- [ ] **Step 4: Audit all source entities and mesh identifiers**

Run:

```powershell
$gameRoot = 'Z:\SteamLibrary\steamapps\common\Hearts of Iron IV'
$entityRoots = @(
  "$gameRoot\integrated_dlc\dlc022_waking_the_tiger\gfx\entities",
  "$gameRoot\integrated_dlc\dlc023_man_the_guns\gfx\entities"
)
rg -n 'name = "(HOL|SHX|MEX|XSM|YUN|PRC)_infantry_weapon_(rifle|mg)_(right|left|long_idle)_entity"' $entityRoots
rg -n 'pdxmesh = "(HOL|SHX|MEX|XSM|YUN|PRC)_infantry_weapon_(rifle|mg)_mesh"' $entityRoots
```

Expected: right, left, and long-idle definitions exist for each of the eight
approved source families, and each family resolves to its audited mesh ID.

- [ ] **Step 5: Audit mesh files and embedded texture references**

Run explicit `Test-Path` checks for:

```text
dlc023_man_the_guns/gfx/models/units/HOL_rifle_johnson_m42.mesh
dlc022_waking_the_tiger/gfx/models/units/SHX_rifle_arisaka.mesh
dlc023_man_the_guns/gfx/models/units/MEX_rifle_mondragon_m1908.mesh
dlc022_waking_the_tiger/gfx/models/units/XSM_smg_mauser712.mesh
dlc023_man_the_guns/gfx/models/units/HOL_smg_bergmann_mp_29.mesh
dlc022_waking_the_tiger/gfx/models/units/YUN_smg_thompson.mesh
dlc022_waking_the_tiger/gfx/models/units/PRC_smg_ppsh41.mesh
dlc023_man_the_guns/gfx/models/units/MEX_smg_mendoza_rm2.mesh
```

Use `rg -a` on every `.mesh` to list embedded `.dds` references, then run
`Test-Path` on every returned diffuse, normal, specular, or gloss texture.
Expected: eight mesh checks and every referenced texture check return `True`.

- [ ] **Step 6: Review the complete scoped diff without staging it**

Run:

```powershell
git diff -- common/units/equipment/ADISCORD_infantry_equipment.txt gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset gfx/entities/zz_ADISCORD_country_infantry.asset tools/validators/validate_adiscord_tech_doctrine.py tools/tests/test_build_adiscord_technology_system.py tools/tests/test_adiscord_infantry_weapon_progression.py tools/tests/test_validate_adiscord_technology_contracts.py
```

Expected: no equipment-stat, technology-layout, localisation, icon, AI,
template, or stockpile changes.

---

### Task 5: Run the Static Release Gate and Fresh-Campaign Runtime Gate

**Files:**
- Verify: all files changed in Tasks 1-4
- Inspect after authorized game launch: fresh HOI4 `error.log` and live division models

**Interfaces:**
- Consumes: completed progression and all focused contracts.
- Produces: static release evidence plus explicit runtime acceptance or a bounded runtime blocker report.

- [ ] **Step 1: Run all focused tests**

Run:

```powershell
python -B -m unittest tools.tests.test_adiscord_infantry_weapon_progression -v
python -B -m unittest tools.tests.test_build_adiscord_technology_system -v
python -B -m unittest tools.tests.test_validate_adiscord_technology_contracts -v
```

Expected: all tests pass.

- [ ] **Step 2: Run the technology and repository validators**

Run:

```powershell
python -B -m tools.builders.build_adiscord_technology_system
python -B tools/validate_tc.py --limit 300
```

Expected: both commands exit 0. The technology builder's check mode must not
rewrite the directly maintained equipment or entity asset files.

- [ ] **Step 3: Check whitespace and preserve the dirty-tree boundary**

Run:

```powershell
git diff --check
git diff --cached --check
git status --short
```

Expected: both diff checks exit 0. Status includes the explicitly scoped
progression work plus the pre-existing unrelated dirty paths; nothing is
staged by this plan.

- [ ] **Step 4: Obtain authorization before launching HOI4**

Do not launch or restart the game implicitly. Ask the user to authorize the
runtime check or to provide a fresh-campaign screenshot and fresh log set.

- [ ] **Step 5: Inspect generic and custom models in a fresh campaign**

After a full restart, use a fresh campaign and inspect at least:

```text
generic country: visual levels 0, 3, 7
STP or VAL custom uniform: visual levels 0, 3, 7
APH mountaineers: visual levels 0, 3, 7
```

Expected: soldier bodies remain unchanged; level 0 shows Johnson, level 3
shows Mauser 712, and level 7 shows Mendoza RM2. If console research or
equipment grants are used, they are runtime inspection aids only and are not
saved as mod content.

- [ ] **Step 6: Inspect fresh logs and report the runtime result**

Search the fresh logs for:

```text
ADISCORD_infantry_weapon_
zy_ADISCORD_infantry_weapon_progression
generic_infantry_4_entity
generic_infantry_8_entity
missing entity
missing mesh
missing texture
duplicate entity
```

Expected: no progression-attributable missing entity, mesh, texture,
animation, or duplicate-name errors. If the engine rejects the late generic
override, stop and report that exact runtime evidence; do not copy the full
vanilla `units_infantry.asset` without a new design decision.

- [ ] **Step 7: Hand off without committing**

Report the exact changed paths, focused/static command results, vanilla asset
audit result, and runtime evidence. Leave all paths unstaged and uncommitted
unless the user separately authorizes a scoped commit.
