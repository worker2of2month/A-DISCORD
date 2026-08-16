# A-Discord Land Technology and Weapon Icon Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build deterministic custom weapon technology icons and replace the sparse infantry and armor timelines with dense, readable late-future capability graphs.

**Architecture:** A dedicated Pillow asset builder owns the supplied source PNG manifest, wide `190x84` weapon cards, compact `72x72` night-operation crops, and a review contact sheet. The existing technology-system builder remains the single gameplay owner and consumes stable semantic icon names while generating technologies, UI folders, effects, starting profiles, AI weights, GFX, and localisation.

**Tech Stack:** Python 3, Pillow 12, JSON manifests, HOI4 Clausewitz script, DDS textures, unittest-based focused tests, A-Discord validators.

## Global Constraints

- Preserve all unrelated dirty work; do not reset, checkout, bulk-format, stage, or commit files without an explicit user request.
- `tools/builders/build_adiscord_technology_system.py` remains the source of truth for generated technologies, folders, GFX declarations, effects, and localisation.
- Russian localisation remains UTF-8 with BOM.
- Main equipment milestones use wide `190x84` cards; every night-combat technology uses compact `72x72` icons.
- Time progresses left to right in infantry and armor.
- TFR and The Darkest Hour are references for graph density and modifier shape only; do not copy their IDs, localisation, or implementation blocks wholesale.
- Only IVN, VAD, and WRK receive the advanced 2160 land-start package.
- Run the generator in `--check` mode before `--apply`, then prove a second `--apply` is idempotent.
- Static validation cannot replace a full game restart and fresh-campaign UI/log smoke test.

---

## File map

- `tools/data/adiscord_technology_weapon_icons.json`: source provenance, semantic tier order, output names, output geometry, and optional compact crop boxes.
- `tools/assets/source/technology_weapons/*.png`: repository-owned copies of the supplied transparent source images.
- `tools/builders/build_adiscord_technology_icons.py`: deterministic alpha fitting, resizing, DDS emission, manifest validation, and contact-sheet rendering.
- `tools/build_adiscord_technology_icons.py`: thin command-line facade.
- `gfx/interface/technologies/ADISCORD_*.dds`: generated runtime technology art.
- `docs/superpowers/reports/2026-08-15-adiscord-technology-icon-contact-sheet.png`: generated visual review sheet.
- `tools/builders/build_adiscord_technology_system.py`: land branch definitions, graphs, icons, effects, AI dependencies, starting access, GFX, and generated localisation.
- `common/units/equipment/ADISCORD_infantry_equipment.txt`: additional infantry-equipment generations and their bounded stat progression.
- `tools/data/adiscord_technology_id_migrations.json`: explicit aliases only if an existing technology ID is retired.
- `tools/tests/test_build_adiscord_technology_icons.py`: asset-pipeline tests.
- `tools/tests/test_build_adiscord_technology_system.py`: branch, equipment, graph, layout, icon, localisation, and starting-profile tests.
- `tools/tests/test_validate_adiscord_technology_contracts.py`: public runtime contract tests.
- `tools/validators/validate_adiscord_tech_doctrine.py`: static validation of icon geometry, graphs, effects, AI coverage, and country access.
- Generated outputs: `common/technologies/ADISCORD_infantry.txt`, `common/technologies/ADISCORD_armor.txt`, `common/ai_strategy/ADISCORD_technology_doctrine_ai.txt`, `common/scripted_effects/ADISCORD_technology_baseline_effects.txt`, `interface/ADISCORD_technologies.gfx`, `interface/countrytechtreeview.gui`, `localisation/{russian,english}/ADISCORD_technology_doctrine_l_*.yml`, and `tools/data/adiscord_starting_technology_profiles.json`.

### Task 1: Lock the source-art manifest and tier order

**Files:**
- Create: `tools/data/adiscord_technology_weapon_icons.json`
- Create: `tools/assets/source/technology_weapons/*.png`
- Create: `tools/tests/test_build_adiscord_technology_icons.py`

**Interfaces:**
- Consumes: the twelve `1893x831` RGBA PNGs supplied in `C:/Users/Admin/Desktop/tech`.
- Produces: manifest entries with `key: str`, `source: str`, `source_sha256: str`, `tier: int`, `kind: "wide" | "compact"`, `output: str`, and optional `crop: [left, top, right, bottom]`.

- [ ] **Step 1: Write the failing manifest contract test**

```python
def test_manifest_has_unique_ranked_weapon_sources(self) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wide = [entry for entry in manifest["icons"] if entry["kind"] == "wide"]
    self.assertEqual([entry["tier"] for entry in wide], list(range(1, 10)))
    self.assertEqual(len({entry["key"] for entry in manifest["icons"]}), len(manifest["icons"]))
    self.assertEqual(len({entry["source"] for entry in wide}), 9)
    for entry in manifest["icons"]:
        self.assertRegex(entry["source_sha256"], r"^[0-9a-f]{64}$")
```

- [ ] **Step 2: Run the test and verify the missing manifest fails**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_icons -v`

Expected: FAIL because `adiscord_technology_weapon_icons.json` does not exist.

- [ ] **Step 3: Import the sources with stable semantic filenames and hashes**

Use the approved tier sequence:

```text
01_reclaimed_arsenal.png                 <- 64be3d7a-216b-4e7a-b700-81bab90b4963.png
02_recovered_service_rifle.png           <- 38a56c82-2c56-4bd4-ac5d-fa3eb7ecb0c6.png
03_standardized_battle_rifle.png         <- 8bc896f1-f59b-4033-81f1-0686f0190ec6.png
04_transitional_modular_weapon.png       <- 98ce80ac-90bc-4af1-a9d4-3ba8f0132069.png
05_suppressed_assault_system.png         <- 1c351184-5837-48cc-aa0b-ccdc921476f8.png
06_networked_smart_rifle.png             <- 1b0ec7af-6f88-4910-91e6-3c20ce8ff8cb.png
07_programmable_munition_weapon.png      <- 64ecc162-8368-4a24-b0e7-7ce2ec6e0554.png
08_advanced_impulse_weapon.png           <- 53942e54-1065-498c-bad8-c123fa9925d7.png
09_resilient_combat_network_weapon.png   <- b3efd823-cdcb-4fa1-8f07-52e8ecb71b37.png
night_operations_source.png              <- 5b9855c0-7d17-438b-898b-136fe17008fb.png
alternate_early_a.png                    <- 3eabf3d3-b69d-4bb9-b186-2cad9ff6b5de.png
alternate_early_b.png                    <- a0a12ff4-e484-4f53-97d0-b8c706feda24.png
```

The manifest must record every original UUID and exact SHA-256 so later replacement is explicit rather than accidental.

- [ ] **Step 4: Run the manifest contract test**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_icons -v`

Expected: PASS for manifest uniqueness, hashes, dimensions, alpha, and tier sequence.

### Task 2: Build deterministic wide and compact DDS assets

**Files:**
- Create: `tools/builders/build_adiscord_technology_icons.py`
- Create: `tools/build_adiscord_technology_icons.py`
- Modify: `tools/tests/test_build_adiscord_technology_icons.py`
- Create: `gfx/interface/technologies/ADISCORD_*.dds`
- Create: `docs/superpowers/reports/2026-08-15-adiscord-technology-icon-contact-sheet.png`

**Interfaces:**
- Consumes: `load_manifest(path: Path) -> tuple[IconSpec, ...]`.
- Produces: `render_icon(spec: IconSpec) -> Image.Image`, `render_outputs(root: Path) -> dict[Path, bytes]`, and a CLI supporting `--check` and `--apply`.

- [ ] **Step 1: Write failing alpha-fit and geometry tests**

```python
def test_wide_outputs_are_exactly_190_by_84_rgba(self) -> None:
    outputs = builder.render_outputs(ROOT)
    for path, payload in outputs.items():
        if path.suffix.lower() != ".dds" or "weapon_" not in path.name:
            continue
        with Image.open(BytesIO(payload)) as image:
            self.assertEqual(image.size, (190, 84))
            self.assertEqual(image.mode, "RGBA")

def test_night_outputs_are_compact(self) -> None:
    outputs = builder.render_outputs(ROOT)
    night = [payload for path, payload in outputs.items() if "night_" in path.name]
    self.assertGreaterEqual(len(night), 6)
    for payload in night:
        with Image.open(BytesIO(payload)) as image:
            self.assertEqual(image.size, (72, 72))
```

- [ ] **Step 2: Run tests and verify the missing builder fails**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_icons -v`

Expected: FAIL because `render_outputs` is unavailable.

- [ ] **Step 3: Implement deterministic transparent-content fitting**

Implement these exact rules:

```python
WIDE_SIZE = (190, 84)
COMPACT_SIZE = (72, 72)
WIDE_MARGIN = (5, 4)
COMPACT_MARGIN = (4, 4)

def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("source image has no visible alpha content")
    return bbox

def fit_rgba(image: Image.Image, size: tuple[int, int], margin: tuple[int, int]) -> Image.Image:
    visible = image.convert("RGBA").crop(alpha_bbox(image.convert("RGBA")))
    limit = (size[0] - margin[0] * 2, size[1] - margin[1] * 2)
    visible.thumbnail(limit, Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    canvas.alpha_composite(visible, ((size[0] - visible.width) // 2, (size[1] - visible.height) // 2))
    return canvas
```

Write DDS with `format="DDS", pixel_format="DXT5"`, compare complete output bytes in `--check`, and use the repository's existing atomic write pattern for `--apply`.

- [ ] **Step 4: Render the contact sheet**

The sheet must show tiers 1-9 left to right with semantic keys below, followed by a second row of the six compact night icons at native scale enlarged only for the report. It is a review artifact, not a runtime sprite.

- [ ] **Step 5: Run focused tests and prove idempotence**

Run:

```powershell
python -B tools/build_adiscord_technology_icons.py --check
python -B tools/build_adiscord_technology_icons.py --apply
python -B tools/build_adiscord_technology_icons.py --check
python -B tools/build_adiscord_technology_icons.py --apply
python -B -m unittest tools.tests.test_build_adiscord_technology_icons -v
```

Expected: the first check reports planned outputs, the second check is clean, the second apply changes zero bytes, and all tests pass.

### Task 3: Add nine infantry-equipment generations

**Files:**
- Modify: `common/units/equipment/ADISCORD_infantry_equipment.txt`
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `tools/tests/test_build_adiscord_technology_system.py`

**Interfaces:**
- Consumes: semantic weapon milestone keys and wide DDS names from Task 2.
- Produces: nine ordered equipment IDs and `ENABLE_EQUIPMENT` mappings at the corresponding research milestones.

- [ ] **Step 1: Write failing equipment-chain tests**

```python
EXPECTED_INFANTRY_GENERATIONS = (
    "ADISCORD_infantry_equipment_2150",
    "ADISCORD_infantry_equipment_2156",
    "ADISCORD_infantry_equipment_2163",
    "ADISCORD_infantry_equipment_2168",
    "ADISCORD_infantry_equipment_2174",
    "ADISCORD_infantry_equipment_2180",
    "ADISCORD_infantry_equipment_2186",
    "ADISCORD_infantry_equipment_2193",
    "ADISCORD_infantry_equipment_2200",
)

def test_infantry_generations_form_a_parent_chain(self) -> None:
    blocks = equipment_blocks(INFANTRY_EQUIPMENT)
    for previous, current in pairwise(EXPECTED_INFANTRY_GENERATIONS):
        self.assertRegex(blocks[current], rf"\bparent\s*=\s*{previous}\b")
```

- [ ] **Step 2: Run the test and verify missing generations fail**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_system -v`

Expected: FAIL listing the absent generation IDs.

- [ ] **Step 3: Implement bounded equipment progression**

Each generation inherits from the prior generation. Use monotonic but modest gains in `soft_attack`, `hard_attack`, `defense`, `breakthrough`, `reliability`, and `build_cost_ic`; do not improve every stat at every tier. Keep infantry consumption and archetype compatibility unchanged.

Map the nine milestone technology IDs to the nine equipment IDs in `ENABLE_EQUIPMENT`, and map them to `ADISCORD_weapon_01` through `ADISCORD_weapon_09` in `EQUIPMENT_UNLOCK_ICONS`.

- [ ] **Step 4: Add generated RU/EN equipment names**

Use terse series names rather than generic role labels. Keep technical IDs ASCII and localisation natural, for example the naming shape `БТ-63 «Рёв»` / `BT-63 “Roar”`, without country prefixes on global equipment keys.

- [ ] **Step 5: Run equipment and localisation tests**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_system -v`

Expected: PASS with all nine equipment definitions, parent links, tech unlocks, icons, and RU/EN names present.

### Task 4: Replace the infantry timeline with six dense programmes

**Files:**
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py`
- Generated: `common/technologies/ADISCORD_infantry.txt`
- Generated: `interface/countrytechtreeview.gui`
- Generated: `localisation/{russian,english}/ADISCORD_technology_doctrine_l_*.yml`

**Interfaces:**
- Consumes: `Branch`, `Tech`, `BranchGraph`, and the custom icon mapping.
- Produces: branch keys `infantry`, `squad`, `anti_tank_infantry`, `night_combat`, `protection`, and `special_forces` in `infantry_folder`.

- [ ] **Step 1: Write failing branch-density and night-icon tests**

```python
def test_infantry_folder_has_six_capability_programmes(self) -> None:
    self.assertEqual(
        generator.FOLDER_BRANCHES["infantry_folder"],
        {"infantry", "squad", "anti_tank_infantry", "night_combat", "protection", "special_forces"},
    )

def test_night_combat_is_compact_only(self) -> None:
    branch = generator.BRANCH_BY_KEY["night_combat"]
    self.assertGreaterEqual(len(branch.techs), 10)
    for index, tech in enumerate(branch.techs):
        self.assertNotIn(tech.id, generator.ENABLE_EQUIPMENT)
        self.assertLessEqual(max(generator.technology_icon_size(generator.icon_for_technology(branch, index))), 72)
```

- [ ] **Step 2: Run focused tests and verify missing branches fail**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_system -v`

Expected: FAIL because `anti_tank_infantry` and `night_combat` do not exist.

- [ ] **Step 3: Define programme content**

Create at least these milestone sequences:

```text
service weapons: reclaimed -> recovered -> standardized -> modular -> suppressed -> networked -> programmable -> impulse -> resilient network
squad weapons: recovered belt feed -> grenade systems -> remote tripods -> programmable airburst -> distributed fire teams -> autonomous suppression
anti-tank: shaped charge -> disposable cells -> tandem warheads -> guided missile -> top attack -> loitering anti-armor -> cooperative seekers -> terminal overmatch
night combat: passive intensifier -> thermal channel -> fused sight -> squad target sharing -> counter-illumination -> distributed night engagement
protection: composite kit -> trauma plate -> load distribution -> sealed suit -> combat medicine -> CBRN survival -> powered load carriage
special forces: fieldcraft -> infiltration -> urban entry -> vertical insertion -> sensor denial -> augmented teams
```

Use original RU/EN localisation and restrained programme names. No placeholder titles such as “Advanced Infantry Technology III”.

- [ ] **Step 4: Build a readable horizontal DAG**

Use one dominant service-weapons lane and five compact lanes. Major dependencies cross lanes only at capability gates: smart optics gates networked weapons, thermal sights gate late night combat, and guided seekers gate the later anti-tank programme. Validate that no node overlaps and that every node is reachable from a pre-2160 seed.

- [ ] **Step 5: Assign bounded effect packages**

Night nodes use only bounded combinations of `land_night_attack`, `category_recon`, coordination, and defense. Anti-tank nodes use infantry/anti-tank `hard_attack`, `ap_attack`, and limited breakthrough. Service and squad nodes distribute soft attack, reliability, defense, production, and suppression instead of repeating flat attack.

- [ ] **Step 6: Run focused graph and effect tests**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system -v
python -B tools/validators/validate_adiscord_tech_doctrine.py
```

Expected: PASS with six programmes, compact night icons, no unreachable nodes, no cycles, no overlaps, and no unsupported modifier keys.

### Task 5: Densify the armor tree around vehicle families and capability gates

**Files:**
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py`
- Generated: `common/technologies/ADISCORD_armor.txt`
- Generated: `interface/countrytechtreeview.gui`
- Generated: `localisation/{russian,english}/ADISCORD_technology_doctrine_l_*.yml`

**Interfaces:**
- Consumes: existing armor equipment archetypes and vanilla vehicle icon aliases.
- Produces: dense `recon_armor`, `combat_armor`, and `heavy_armor` DAGs with explicit carrier, IFV, MBT, heavy, recovery, and unmanned milestones.

- [ ] **Step 1: Write failing armor-capability tests**

```python
def test_armor_graphs_contain_required_capability_programmes(self) -> None:
    required = {
        "mobility", "protection", "active_protection", "fire_control",
        "armament", "crew_survival", "networking", "autonomy",
    }
    for key in ("recon_armor", "combat_armor", "heavy_armor"):
        self.assertTrue(required.issubset(set(generator.BRANCH_PROGRAMMES[key])))
        self.assertGreaterEqual(len(generator.BRANCH_BY_KEY[key].techs), 20)
```

- [ ] **Step 2: Run the test and verify the old 16-node branches fail**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_system -v`

Expected: FAIL because the current branches have only 16 nodes and incomplete programme labels.

- [ ] **Step 3: Expand vehicle milestones and capability nodes**

Keep existing equipment IDs and add research around them rather than inventing redundant platform archetypes. Represent APC, IFV/recon, MBT, heavy breakthrough, recovery/engineering, and late unmanned roles as milestone techs. Add module nodes for powerpacks, armor arrays, signature control, active protection, counter-UAS, fire control, ammunition, crew survival, repairability, networking, and bounded autonomy.

- [ ] **Step 4: Implement three meaningful forks**

The graph must expose:

```text
mass-producible mobility <-> advanced low-volume protection
offensive overmatch <-> survivability and active protection
crewed resilience <-> optionally crewed autonomy
```

Each choice remains open research rather than `xor`, but consumes time and leads to different modifier packages. Reconvergence occurs only at late integration nodes.

- [ ] **Step 5: Validate wide milestone cards and compact modules**

Vehicle/equipment unlocks may use wide cards up to `190x84`; module nodes must remain at most `72x72`. Ensure the armor viewport and x-axis width include the final 2200 columns without drifting icons.

- [ ] **Step 6: Run focused armor tests and validator**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system -v
python -B tools/validators/validate_adiscord_tech_doctrine.py
```

Expected: PASS with no cycles, overlaps, dangling prerequisites, invalid icons, or unsupported effects.

### Task 6: Restrict the advanced starting package and teach the AI the new graphs

**Files:**
- Modify: `tools/builders/build_adiscord_technology_system.py`
- Modify: `tools/tests/test_build_adiscord_technology_system.py`
- Modify: `tools/tests/test_validate_adiscord_technology_contracts.py`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py`
- Generated: `tools/data/adiscord_starting_technology_profiles.json`
- Generated: `common/scripted_effects/ADISCORD_technology_baseline_effects.txt`
- Generated: `common/ai_strategy/ADISCORD_technology_doctrine_ai.txt`

**Interfaces:**
- Consumes: final land graph prerequisite closure from Tasks 4-5.
- Produces: a new `advanced_land_2160` profile assigned only to `IVN`, `VAD`, and `WRK`, plus AI weights for coherent research packages.

- [ ] **Step 1: Write failing country-access tests**

```python
def test_advanced_land_start_is_exclusive(self) -> None:
    advanced = {
        tag for tag, profiles in generator.COUNTRY_PROFILE_ASSIGNMENTS.items()
        if "advanced_land_2160" in profiles
    }
    self.assertEqual(advanced, {"IVN", "VAD", "WRK"})
```

- [ ] **Step 2: Run the test and verify the profile is absent**

Run: `python -B -m unittest tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts -v`

Expected: FAIL because `advanced_land_2160` is not defined.

- [ ] **Step 3: Add the exclusive profile with prerequisite closure**

Grant only the 2160 advanced service-weapon milestone, first modern night-optic milestone, first guided anti-tank milestone, carrier/IFV entry, and early MBT integration needed by those three powers. Include every prerequisite automatically; do not grant post-2160 successors.

- [ ] **Step 4: Add AI programme weights**

Teach AI to prefer complete packages in this order: current service weapon, squad support, anti-tank response if hostile armor exists, night capability for organized powers, carrier/IFV before late MBT, and repair/protection before autonomous end nodes. Penalize research more than one milestone beyond the country's current prerequisites.

- [ ] **Step 5: Run starting-profile and AI coverage tests**

Run:

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts -v
python -B tools/validators/validate_adiscord_tech_doctrine.py
```

Expected: PASS; only IVN/VAD/WRK contain `advanced_land_2160`, and every new technology has a valid AI path.

### Task 7: Regenerate, prove idempotence, and perform static release gates

**Files:**
- Modify only generator-owned outputs listed in the file map.

**Interfaces:**
- Consumes: completed icon and technology builders.
- Produces: a clean deterministic generated-output set and recorded static verification evidence.

- [ ] **Step 1: Run both builders in check mode**

```powershell
python -B tools/build_adiscord_technology_icons.py --check
python -B tools/build_adiscord_technology_system.py --check
```

Expected: both report the exact pending generated files and no validation exception.

- [ ] **Step 2: Apply generated outputs explicitly**

```powershell
python -B tools/build_adiscord_technology_icons.py --apply
python -B tools/build_adiscord_technology_system.py --apply
```

- [ ] **Step 3: Hash owned outputs and prove a second apply is identical**

Record SHA-256 for the icon DDS files and every technology-system `OUTPUTS` path, run both `--apply` commands again, and assert the before/after hash maps are identical.

- [ ] **Step 4: Run focused suites**

```powershell
python -B -m unittest tools.tests.test_build_adiscord_technology_icons tools.tests.test_build_adiscord_technology_system tools.tests.test_validate_adiscord_technology_contracts -v
python -B tools/validators/validate_adiscord_tech_doctrine.py
```

- [ ] **Step 5: Verify localisation BOM and repository-wide static gates**

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
```

Also assert the first three bytes of `localisation/russian/ADISCORD_technology_doctrine_l_russian.yml` are `EF BB BF`.

- [ ] **Step 6: Audit the final diff boundary**

Run `git status --short` and `git diff --stat`. Confirm no unrelated Vorkerland, map-state, theatre-manifest, or division-template file was changed by this plan.

### Task 8: Runtime UI and fresh-log smoke test

**Files:**
- Read-only runtime artifacts under the user's Hearts of Iron IV logs and screenshots.

**Interfaces:**
- Consumes: a fully restarted game with the changed mod loaded and a new campaign.
- Produces: evidence that the player-visible tree is readable and error-free at runtime.

- [ ] **Step 1: Fully close and restart Hearts of Iron IV**

Do not reuse a running process or old save because technology, GFX, GUI, and localisation databases load at startup.

- [ ] **Step 2: Start a fresh 2160 campaign as WRK**

Confirm WRK sees the advanced land-start package, all other listed templates remain available, and the infantry-equipment production list contains only researched generations.

- [ ] **Step 3: Inspect infantry at normal zoom**

Capture a screenshot showing the nine wide service-weapon milestones and compact squad, anti-tank, night, protection, and special-forces lanes. Confirm no clipped cards, shifted columns, overlapping connectors, or wide night icons.

- [ ] **Step 4: Inspect armor at normal zoom**

Capture a screenshot showing APC/IFV, MBT, heavy, recovery, and autonomy paths with readable capability forks and no off-screen final columns.

- [ ] **Step 5: Verify exclusive access in a second fresh campaign**

Open a non-IVN/VAD/WRK country and confirm it does not receive `advanced_land_2160` while retaining the common recovered baseline.

- [ ] **Step 6: Inspect fresh logs**

Check `error.log`, `game.log`, and `system.log` created by this restart for unknown technology, invalid modifier, missing sprite, missing texture, duplicate localisation, and GUI parsing errors. Separate unrelated engine/DLC/workshop warnings from A-Discord errors.
