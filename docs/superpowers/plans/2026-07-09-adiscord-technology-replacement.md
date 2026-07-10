# A-Discord Technology Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vanilla-era Hearts of Iron IV technology surface with an A-Discord 2100-2200 technology and equipment framework that fits the 2163 and 2183 bookmarks.

**Architecture:** Keep the current `ADISCORD_` namespace and preserve existing doctrine concepts, but split the technology database by domain and add first-class custom equipment files. Use the existing static validator as the migration gate so vanilla 1930s years, missing equipment unlocks, missing UI gridboxes, and conflicting vanilla database paths are caught before launch.

**Tech Stack:** Hearts of Iron IV `.txt` database files, Clausewitz GUI `.gui`, Paradox localisation `.yml`, Python 3 static validation, PowerShell for local commands.

## Global Constraints

- Campaign start is `2163.1.1.1`; the existing late bookmark is `2183.8.14.12`.
- Technology eras must use `2100`, `2120`, `2140`, `2163`, `2170`, `2183`, and `2200`.
- Use split A-Discord technology files by domain instead of one mixed `ADISCORD_technologies.txt`.
- Add custom or compatibility equipment for infantry weapons, support equipment, artillery, armor, trains, armored trains, railway guns, and air platforms.
- Preserve the new HOI4 doctrine database shape: `common/doctrines/grand_doctrines`, `common/doctrines/subdoctrines`, and `common/doctrines/tracks`.
- Do not copy the reference mod at `Z:/SteamLibrary/steamapps/workshop/content/394360/3607150697`; only follow its structural pattern.
- Do not rewrite unrelated country, economy, focus, map, or state files.
- Treat the existing dirty worktree as user-owned unless a file is directly part of this technology replacement.

---

## File Structure

- `tools/validate_adiscord_tech_doctrine.py`: migration gate for split technology files, equipment files, UI years/gridboxes, doctrine references, descriptor replace paths, and local tech references.
- `common/technologies/ADISCORD_industry.txt`: reconstruction, machine tools, factory automation, resources, distributed manufacturing.
- `common/technologies/ADISCORD_electronics.txt`: power grid, sensors, encryption, command networks, AI assistance.
- `common/technologies/ADISCORD_infantry.txt`: infantry weapons, protection kits, smart optics, medical drones, exoskeleton frames, field EW, command terminals, sapper kits.
- `common/technologies/ADISCORD_artillery.txt`: artillery, anti-tank, anti-air, rocket and precision munition unlocks.
- `common/technologies/ADISCORD_armor.txt`: restored chassis, remote weapons, recon drones, semi-autonomous modules, repair sections, heavy cores, battle AI, autonomous breakthrough platforms.
- `common/technologies/ADISCORD_logistics_trains.txt`: rail stock, armored trains, autonomous dispatch, hardened logistics, railway guns, railgun fire-control support.
- `common/technologies/ADISCORD_air.txt`: reclaimed jets, guided munitions, VTOL, drone wings, interceptors, strategic rockets, orbital tracking, deep strike.
- `common/technologies/ADISCORD_forbidden.txt`: legacy reactors, industrial swarms, neural command, dirty munitions, singularity cooling, black-grid protocol, forbidden automation.
- `common/units/equipment/ADISCORD_infantry_equipment.txt`: `infantry_equipment`, `infantry_equipment_0`, and A-Discord infantry weapon tiers.
- `common/units/equipment/ADISCORD_support_equipment.txt`: `support_equipment`, `support_equipment_1`, and A-Discord support tiers.
- `common/units/equipment/ADISCORD_artillery_equipment.txt`: `artillery_equipment`, `artillery_equipment_1`, and A-Discord artillery tiers.
- `common/units/equipment/ADISCORD_armor_equipment.txt`: A-Discord restored, remote, heavy, and autonomous armor variants.
- `common/units/equipment/ADISCORD_train_equipment.txt`: `train_equipment`, `train_equipment_1`, armored train, and autonomous train variants.
- `common/units/equipment/ADISCORD_railway_gun_equipment.txt`: `railway_gun_equipment`, `railway_gun_equipment_1`, and A-Discord railway gun variants.
- `common/units/equipment/ADISCORD_air_equipment.txt`: compatibility aircraft archetypes and A-Discord air variants.
- `common/raids/ADISCORD_no_raids.txt`: intentional empty replacement database so vanilla raid tech references stop loading.
- `common/operations/ADISCORD_no_operations.txt`: intentional empty replacement database so vanilla operations with vanilla tags stop loading.
- `common/units/names_railway_guns/ADISCORD_railway_gun_names.txt`: custom railway gun names without vanilla country tags.
- `interface/countrytechtreeview.gui`: visible technology folders, root gridboxes, and era labels.
- `interface/ADISCORD_technologies.gfx`: sprites for visible A-Discord technologies.
- `localisation/russian/ADISCORD_technology_doctrine_l_russian.yml`: Russian tech/equipment/tab names and descriptions.
- `localisation/english/ADISCORD_technology_doctrine_l_english.yml`: English fallback names and descriptions.
- `descriptor.mod`: total-conversion replace paths for conflicting vanilla databases.

### Task 1: Validator Contract

**Files:**
- Modify: `tools/validate_adiscord_tech_doctrine.py`

**Interfaces:**
- Consumes: existing helper functions `read_text`, `strip_comments`, `extract_block`, `top_level_keys`, `collect_technologies`, `collect_localisation_keys`, `collect_sprite_names`.
- Produces: additional validation errors that later tasks must satisfy.

- [ ] **Step 1: Add expected split files, equipment ids, descriptor paths, and era labels**

Add these constants near `NEW_DATA_FILES`:

```python
TECHNOLOGY_FILES = [
    "common/technologies/ADISCORD_industry.txt",
    "common/technologies/ADISCORD_electronics.txt",
    "common/technologies/ADISCORD_infantry.txt",
    "common/technologies/ADISCORD_artillery.txt",
    "common/technologies/ADISCORD_armor.txt",
    "common/technologies/ADISCORD_logistics_trains.txt",
    "common/technologies/ADISCORD_air.txt",
    "common/technologies/ADISCORD_forbidden.txt",
]

EQUIPMENT_FILES = [
    "common/units/equipment/ADISCORD_infantry_equipment.txt",
    "common/units/equipment/ADISCORD_support_equipment.txt",
    "common/units/equipment/ADISCORD_artillery_equipment.txt",
    "common/units/equipment/ADISCORD_armor_equipment.txt",
    "common/units/equipment/ADISCORD_train_equipment.txt",
    "common/units/equipment/ADISCORD_railway_gun_equipment.txt",
    "common/units/equipment/ADISCORD_air_equipment.txt",
]

EXPECTED_DESCRIPTOR_REPLACE_PATHS = [
    'replace_path="common/technologies"',
    'replace_path="common/units/equipment"',
    'replace_path="common/raids"',
    'replace_path="common/operations"',
    'replace_path="common/units/names_railway_guns"',
    'replace_path="common/doctrines/grand_doctrines"',
    'replace_path="common/doctrines/subdoctrines"',
    'replace_path="common/doctrines/tracks"',
]

EXPECTED_TECH_UI_YEARS = {"2100", "2120", "2140", "2163", "2170", "2183", "2200"}
LEGACY_TECH_UI_YEAR_RE = re.compile(r'\btext\s*=\s*"(19[0-9]{2}|20[0-8][0-9])"')
```

- [ ] **Step 2: Add equipment key collection**

Add this function after `collect_technologies`:

```python
def collect_equipment_keys() -> set[str]:
    equipment: set[str] = set()
    base = ROOT / "common" / "units" / "equipment"
    for path in base.glob("*.txt") if base.exists() else []:
        text = strip_comments(read_text(path))
        equipment.update(top_level_keys(text))
    return equipment
```

- [ ] **Step 3: Add checks for split files, UI years, equipment unlocks, and descriptor paths**

Add `check_split_technology_layout`, `check_equipment_unlocks`, `check_technology_ui_years`, and replace the old `check_technology_replace_path` body with a required-path checker:

```python
def check_split_technology_layout() -> list[str]:
    issues: list[str] = []
    for rel_path in TECHNOLOGY_FILES + EQUIPMENT_FILES:
        if not (ROOT / rel_path).exists():
            issues.append(f"missing split framework file {rel_path}")
    legacy = ROOT / "common" / "technologies" / "ADISCORD_technologies.txt"
    if legacy.exists() and "technologies = { }" not in strip_comments(read_text(legacy)):
        issues.append("common/technologies/ADISCORD_technologies.txt must be empty after split migration")
    return issues


def check_equipment_unlocks(tech_blocks: dict[str, str], equipment: set[str]) -> list[str]:
    issues: list[str] = []
    unlocked: set[str] = set()
    for tech, block in tech_blocks.items():
        for match in re.finditer(r"\benable_equipments\s*=\s*\{([^{}]*)\}", block, re.S):
            unlocked.update(re.findall(r"[A-Za-z0-9_]+", match.group(1)))
        for match in re.finditer(r"\benable_equipment_modules\s*=\s*\{([^{}]*)\}", block, re.S):
            unlocked.update(re.findall(r"[A-Za-z0-9_]+", match.group(1)))
    for eq in sorted(unlocked):
        if eq not in equipment:
            issues.append(f"technology unlocks undefined equipment {eq}")
    required_unlocks = {
        "infantry_equipment_0",
        "support_equipment_1",
        "artillery_equipment_1",
        "train_equipment_1",
        "armored_train_equipment_1",
        "railway_gun_equipment_1",
        "ADISCORD_light_combat_platform_2163",
        "ADISCORD_fighter_airframe_2163",
    }
    missing = sorted(required_unlocks - unlocked)
    for eq in missing:
        issues.append(f"no technology unlocks required equipment {eq}")
    return issues


def check_technology_ui_years() -> list[str]:
    gui_path = ROOT / "interface" / "countrytechtreeview.gui"
    if not gui_path.exists():
        return ["interface/countrytechtreeview.gui is missing"]
    text = strip_comments(read_text(gui_path))
    issues = []
    for match in LEGACY_TECH_UI_YEAR_RE.finditer(text):
        issues.append(f"interface/countrytechtreeview.gui:{line_for_offset(text, match.start())}: legacy tech UI year {match.group(1)}")
    for year in sorted(EXPECTED_TECH_UI_YEARS):
        if f'text = "{year}"' not in text:
            issues.append(f"technology UI is missing era label {year}")
    return issues


def check_technology_replace_path() -> list[str]:
    issues: list[str] = []
    descriptor_paths = [ROOT / "descriptor.mod", ROOT.parent / "A-Discord.mod"]
    for path in descriptor_paths:
        if not path.exists():
            issues.append(f"missing descriptor {path}")
            continue
        text = read_text(path)
        for required in EXPECTED_DESCRIPTOR_REPLACE_PATHS:
            if required not in text:
                issues.append(f"{rel(path) if path.is_relative_to(ROOT) else path.name} is missing {required}")
    return issues
```

- [ ] **Step 4: Wire checks into `main`**

Add `equipment = collect_equipment_keys()` beside the existing collectors and extend `issues`:

```python
equipment = collect_equipment_keys()
issues.extend(check_split_technology_layout())
issues.extend(check_equipment_unlocks(tech_blocks, equipment))
issues.extend(check_technology_ui_years())
```

- [ ] **Step 5: Run validator and confirm RED**

Run: `python tools/validate_adiscord_tech_doctrine.py`

Expected: FAIL with missing split framework files, missing required equipment unlocks, legacy tech UI years, and missing descriptor replace paths.

### Task 2: Split Technology Database and Equipment Baseline

**Files:**
- Create/Modify: all `common/technologies/ADISCORD_*.txt` files listed in File Structure
- Create: all `common/units/equipment/ADISCORD_*.txt` files listed in File Structure
- Modify: `common/technologies/ADISCORD_technologies.txt`

**Interfaces:**
- Consumes: `EXPECTED_TECHS`, `FORBIDDEN_TECHS`, and validator checks from Task 1.
- Produces: all existing `ADISCORD_tech_*` IDs remain defined, split by domain, with valid `enable_equipments` targets.

- [ ] **Step 1: Empty the legacy aggregate technology file**

Set `common/technologies/ADISCORD_technologies.txt` to:

```hoi4
technologies = {
}
```

- [ ] **Step 2: Move existing industry/economy technologies into `ADISCORD_industry.txt`**

Keep these IDs in the industry file with years on the new grid:

```text
ADISCORD_tech_salvage_standards
ADISCORD_tech_ruin_workshops
ADISCORD_tech_reconstruction_bureaus
ADISCORD_tech_modular_rebuilding
ADISCORD_tech_basic_fiscal_records
ADISCORD_tech_reconstruction_contracts
ADISCORD_tech_tax_census_network
ADISCORD_tech_state_debt_instruments
ADISCORD_tech_reserve_management
ADISCORD_tech_fiscal_administration_1
ADISCORD_tech_fiscal_administration_2
ADISCORD_tech_automated_bureaucracy
ADISCORD_tech_predictive_budgeting
ADISCORD_tech_standardized_machine_tools
ADISCORD_tech_industrial_cluster_planning
ADISCORD_tech_logistics_hub_networks
ADISCORD_tech_automated_assembly
ADISCORD_tech_synthetic_resource_cycles
ADISCORD_tech_predictive_maintenance
ADISCORD_tech_autonomous_factory_cells
ADISCORD_tech_distributed_manufacturing
```

- [ ] **Step 3: Move grid/electronics technologies into `ADISCORD_electronics.txt`**

Keep these IDs in the electronics file:

```text
ADISCORD_tech_local_grid_restoration
ADISCORD_tech_substation_networks
ADISCORD_tech_radiation_mapping
ADISCORD_tech_shielded_engineering_corps
ADISCORD_tech_reactor_safety_protocols
ADISCORD_tech_microreactor_blocks
ADISCORD_tech_dead_reactor_salvage
ADISCORD_tech_emergency_core_suppression
ADISCORD_tech_mesh_command_networks
ADISCORD_tech_encryption_rebuild
ADISCORD_tech_signal_intercept_arrays
ADISCORD_tech_battlefield_analytics
ADISCORD_tech_counterintelligence_filters
ADISCORD_tech_predictive_logistics
ADISCORD_tech_memetic_security_protocols
ADISCORD_tech_operational_ai_assistants
```

- [ ] **Step 4: Move infantry/support technologies into `ADISCORD_infantry.txt`**

Keep these IDs and add real equipment unlocks:

```text
ADISCORD_tech_postwar_weapon_standardization -> infantry_equipment_0 support_equipment_1
ADISCORD_tech_composite_protection_kits -> ADISCORD_infantry_equipment_2170
ADISCORD_tech_smart_optics -> ADISCORD_infantry_equipment_2183
ADISCORD_tech_battlefield_medical_drones -> ADISCORD_support_equipment_2170
ADISCORD_tech_exoskeleton_load_frames -> ADISCORD_support_equipment_2183
ADISCORD_tech_field_ew_units -> ADISCORD_support_equipment_2200
ADISCORD_tech_networked_command_terminals -> ADISCORD_command_equipment_2183
ADISCORD_tech_assault_sapper_kits -> ADISCORD_combat_engineer_equipment_2170
```

- [ ] **Step 5: Create `ADISCORD_artillery.txt`**

Define artillery and anti-armor unlock path with these IDs:

```text
ADISCORD_tech_restored_field_artillery -> artillery_equipment_1
ADISCORD_tech_smart_fire_control -> ADISCORD_artillery_equipment_2170
ADISCORD_tech_drone_spotted_batteries -> ADISCORD_artillery_equipment_2183
ADISCORD_tech_scrap_at_launchers -> ADISCORD_anti_tank_equipment_2163
ADISCORD_tech_coil_at_systems -> ADISCORD_anti_tank_equipment_2183
ADISCORD_tech_point_defense_aa -> ADISCORD_anti_air_equipment_2163
ADISCORD_tech_rail_assisted_aa -> ADISCORD_anti_air_equipment_2183
```

- [ ] **Step 6: Move armor technologies into `ADISCORD_armor.txt`**

Keep these IDs and add armor unlocks:

```text
ADISCORD_tech_restored_armored_chassis -> ADISCORD_light_combat_platform_2163
ADISCORD_tech_remote_weapon_stations -> ADISCORD_combat_platform_2170
ADISCORD_tech_drone_recon_swarms -> ADISCORD_recon_drone_carrier_2170
ADISCORD_tech_semi_autonomous_combat_modules -> ADISCORD_combat_platform_2183
ADISCORD_tech_remote_repair_sections -> ADISCORD_repair_platform_2183
ADISCORD_tech_heavy_platform_cores -> ADISCORD_heavy_combat_platform_2183
ADISCORD_tech_limited_battle_ai -> ADISCORD_combat_platform_2200
ADISCORD_tech_autonomous_breakthrough_platforms -> ADISCORD_heavy_combat_platform_2200
```

- [ ] **Step 7: Create `ADISCORD_logistics_trains.txt`**

Define rail and railway-gun path:

```text
ADISCORD_tech_restored_rail_stock -> train_equipment_1
ADISCORD_tech_armored_rail_convoys -> armored_train_equipment_1
ADISCORD_tech_autonomous_rail_dispatch -> ADISCORD_autonomous_train_equipment_2183
ADISCORD_tech_hardened_logistics_nodes -> ADISCORD_hardened_train_equipment_2183
ADISCORD_tech_railway_gun_reactivation -> railway_gun_equipment_1
ADISCORD_tech_over_the_horizon_fire_control -> ADISCORD_railway_gun_equipment_2200
```

- [ ] **Step 8: Move air technologies into `ADISCORD_air.txt`**

Keep these IDs and add air unlocks:

```text
ADISCORD_tech_reclaimed_jet_platforms -> ADISCORD_fighter_airframe_2163
ADISCORD_tech_guided_munitions -> ADISCORD_cas_airframe_2170
ADISCORD_tech_vtol_assault_frames -> ADISCORD_vtol_airframe_2170
ADISCORD_tech_drone_air_wings -> ADISCORD_drone_airframe_2183
ADISCORD_tech_high_altitude_interceptors -> ADISCORD_interceptor_airframe_2183
ADISCORD_tech_strategic_rocket_architecture -> ADISCORD_rocket_strike_platform_2183
ADISCORD_tech_orbital_tracking_relics -> ADISCORD_orbital_tracking_platform_2200
ADISCORD_tech_deep_strike_targeting -> ADISCORD_deep_strike_airframe_2200
```

- [ ] **Step 9: Move forbidden technologies into `ADISCORD_forbidden.txt`**

Keep every ID in `FORBIDDEN_TECHS`; each block must include `allow = { ADISCORD_has_forbidden_legacy_access = yes }` or `allow = { ADISCORD_has_black_grid_access = yes }` and must not use `allow = { always = yes }`.

- [ ] **Step 10: Create equipment files**

Use compatibility equipment IDs required by history and production (`infantry_equipment_0`, `support_equipment_1`, `artillery_equipment_1`, `train_equipment_1`, `armored_train_equipment_1`, `railway_gun_equipment_1`) plus A-Discord variants named in the technology unlock lists. Each buildable variant must include `year`, `archetype`, `priority`, `visual_level`, and sane cost/stat fields matching the archetype.

- [ ] **Step 11: Run validator and confirm technology/equipment GREEN**

Run: `python tools/validate_adiscord_tech_doctrine.py`

Expected: remaining failures are limited to UI era labels, missing UI gridboxes, descriptor replace paths, and localisation/sprite gaps introduced by new IDs.

### Task 3: Technology UI Folders, Era Labels, and Localisation

**Files:**
- Modify: `interface/countrytechtreeview.gui`
- Modify: `interface/ADISCORD_technologies.gfx`
- Modify: `localisation/russian/ADISCORD_technology_doctrine_l_russian.yml`
- Modify: `localisation/english/ADISCORD_technology_doctrine_l_english.yml`

**Interfaces:**
- Consumes: technology root IDs and folder names from Task 2.
- Produces: visible A-Discord branches in infantry, artillery, armor, air, industry, electronics, and support/logistics folders with no 1930s labels.

- [ ] **Step 1: Replace year labels**

In every visible technology folder container, replace vanilla labels with the A-Discord era grid. The only bare year labels left in `interface/countrytechtreeview.gui` must be:

```text
2100
2120
2140
2163
2170
2183
2200
```

- [ ] **Step 2: Keep and add root gridboxes**

For each root technology with no incoming `leads_to_tech`, ensure the folder container has a gridbox named `<root>_tree`. The validator determines roots by reading the tech graph; do not hardcode roots in GUI without matching the tech data.

- [ ] **Step 3: Add localisation for new artillery/logistics/equipment IDs**

Append Russian and English fallback localisation keys for all new IDs introduced in Task 2. Each technology gets `<id>` and `<id>_desc`; each equipment item gets `<id>` and `<id>_desc`.

- [ ] **Step 4: Reuse existing sprite icons safely**

For new technology IDs, add `spriteType` entries in `interface/ADISCORD_technologies.gfx` pointing to existing base-game or current mod textures. The validator must confirm each `GFX_<tech>_medium` sprite exists and the texture file resolves.

- [ ] **Step 5: Run validator and confirm UI/localisation GREEN**

Run: `python tools/validate_adiscord_tech_doctrine.py`

Expected: remaining failures are limited to descriptor replace paths and external vanilla load conflicts.

### Task 4: Descriptor Replace Paths and Vanilla Conflict Cleanup

**Files:**
- Modify: `descriptor.mod`
- Modify: `../A-Discord.mod` if it exists and is the active launcher descriptor
- Create: `common/raids/ADISCORD_no_raids.txt`
- Create: `common/operations/ADISCORD_no_operations.txt`
- Create: `common/units/names_railway_guns/ADISCORD_railway_gun_names.txt`

**Interfaces:**
- Consumes: valid custom technology/equipment/doctrine database from Tasks 2 and 3.
- Produces: vanilla raids, operations, railway-gun names, technology files, equipment files, and old doctrine subdatabases no longer load over the total conversion.

- [ ] **Step 1: Add required replace paths**

Add these exact lines to both descriptors when the file exists:

```text
replace_path="common/technologies"
replace_path="common/units/equipment"
replace_path="common/raids"
replace_path="common/operations"
replace_path="common/units/names_railway_guns"
replace_path="common/doctrines/grand_doctrines"
replace_path="common/doctrines/subdoctrines"
replace_path="common/doctrines/tracks"
```

- [ ] **Step 2: Provide empty replacement databases**

Use valid empty root blocks where the database expects a root. For raids and operations, keep files empty only if the game accepts that path replacement; otherwise create an empty root block matching the vanilla parser shape found in the base-game file.

- [ ] **Step 3: Add custom railway gun names**

Create a custom names file with no vanilla tag references:

```hoi4
ADISCORD = {
    railway_gun = {
        "Индекс-2163"
        "Громовая линия"
        "Черный перегон"
        "Станция Ноль"
    }
}
```

- [ ] **Step 4: Run validator and confirm descriptor GREEN**

Run: `python tools/validate_adiscord_tech_doctrine.py`

Expected: `A-DISCORD technology/doctrine validation: OK`.

### Task 5: Final Verification and Fresh Error Log Pass

**Files:**
- Read: `C:/Users/Admin/Documents/Paradox Interactive/Hearts of Iron IV/logs/error.log`
- Read/Modify only if validation requires it: files touched by Tasks 1-4

**Interfaces:**
- Consumes: all implemented database files and validators.
- Produces: final evidence for the user and a focused list of any remaining external or unrelated errors.

- [ ] **Step 1: Run the focused validator**

Run: `python tools/validate_adiscord_tech_doctrine.py`

Expected: `A-DISCORD technology/doctrine validation: OK`.

- [ ] **Step 2: Run the broad total-conversion validator**

Run: `python tools/validate_tc.py`

Expected: no new technology, equipment, doctrine, raid, operation, or railway-gun errors caused by this work. Existing unrelated country/map/focus issues may remain and must be reported separately.

- [ ] **Step 3: Inspect fresh error log**

Run:

```powershell
$log = "$env:USERPROFILE\Documents\Paradox Interactive\Hearts of Iron IV\logs\error.log"
if (Test-Path $log) {
    Select-String -Path $log -Pattern "Invalid tech|Invalid equipment|doctrines|raid_categories|operation|railway_gun|ADISCORD" | Select-Object -First 120
}
```

Expected: the repeated vanilla `raid_categories.txt` invalid-tech spam and vanilla special-forces doctrine invalid-tech spam are gone after a fresh game launch. If the log timestamp predates the edits, report that the log is stale and ask for one launch cycle.

- [ ] **Step 4: Report final state**

Summarize changed files, validators run, whether a fresh log was available, and any residual risks. Do not claim launch-log success if the log timestamp predates the replacement-path edits.
