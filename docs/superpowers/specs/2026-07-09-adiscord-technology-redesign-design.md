# A-Discord Technology Redesign

## Context

A-Discord is a Hearts of Iron IV total conversion that starts on
2163.1.1, with a later bookmark on 2183.8.14. The current custom
technology file uses vanilla-era years from 1936 through 1949, while
the visible campaign timeline is 2163 through 2183 and the desired
technology horizon is roughly the 2100s through 2200.

The current technology implementation is concentrated in
`common/technologies/ADISCORD_technologies.txt`. Several vanilla
technology files in `common/technologies` exist as empty `technologies`
blocks. Fresh `error.log` output shows that vanilla raids, doctrines,
operations, and railway-gun name files still load and reference vanilla
technologies or country tags that no longer exist in this total
conversion. The largest repeated error is:

`common/raids/categories/raid_categories.txt:15: has_tech: Invalid tech`

This indicates a root cause in mixed vanilla and total-conversion
database state, not only bad display years.

## Goals

Build a careful custom technology system for A-Discord that:

- Uses a setting-appropriate date grid: 2100, 2120, 2140, 2163, 2170,
  2183, and 2200.
- Splits technology files by domain instead of keeping one large mixed
  file.
- Adds real unlockable equipment for infantry weapons, support
  equipment, artillery, armor, trains, armored trains, railway guns, and
  air platforms.
- Keeps the `ADISCORD_` namespace for custom technologies and equipment
  where practical.
- Fixes total-conversion load errors by replacing only the vanilla
  database paths that conflict with the custom system.
- Preserves existing country, economy, map, focus, and scripted systems
  unless a direct technology dependency must be updated.

## Non-Goals

- Do not copy the reference mod implementation wholesale.
- Do not redesign the economy, state history, national focuses, or
  country setup as part of this task.
- Do not add a complete naval equipment system in the first pass unless
  an existing error or dependency makes it necessary.
- Do not remove existing custom doctrine concepts; migrate their tech
  dependencies to the new technology names instead.

## Reference Pattern

The workshop reference mod at
`Z:/SteamLibrary/steamapps/workshop/content/394360/3607150697` uses a
healthy total-conversion structure:

- Technology files are split by domain, such as infantry, support,
  armor, artillery, industry, air, and naval.
- Equipment files are split by domain under `common/units/equipment`,
  such as infantry equipment, trains, railway guns, armor, artillery,
  and aircraft.
- Technology files define coordinate constants at the top, such as
  year rows and line columns, then reuse those constants in folder
  positions.
- Technologies use `enable_equipments` and `enable_subunits` for real
  unlocks, not only modifiers.
- The descriptor uses broad but intentional `replace_path` entries for
  total-conversion database areas.

A-Discord should adopt the structure and safety principles, not the
content.

## Proposed File Layout

Technology files:

- `common/technologies/ADISCORD_industry.txt`
- `common/technologies/ADISCORD_electronics.txt`
- `common/technologies/ADISCORD_infantry.txt`
- `common/technologies/ADISCORD_artillery.txt`
- `common/technologies/ADISCORD_armor.txt`
- `common/technologies/ADISCORD_logistics_trains.txt`
- `common/technologies/ADISCORD_air.txt`
- `common/technologies/ADISCORD_forbidden.txt`

Equipment files:

- `common/units/equipment/ADISCORD_infantry_equipment.txt`
- `common/units/equipment/ADISCORD_support_equipment.txt`
- `common/units/equipment/ADISCORD_artillery_equipment.txt`
- `common/units/equipment/ADISCORD_armor_equipment.txt`
- `common/units/equipment/ADISCORD_train_equipment.txt`
- `common/units/equipment/ADISCORD_railway_gun_equipment.txt`
- `common/units/equipment/ADISCORD_air_equipment.txt`

Interface and localisation:

- Keep `interface/ADISCORD_technologies.gfx`, extending it with new
  sprites as technologies and equipment are added.
- Keep technology localisation in
  `localisation/russian/ADISCORD_technology_doctrine_l_russian.yml`
  unless the file becomes too large; then split by domain.
- English localisation may remain minimal fallback text.

## Date Model

Use the following semantic eras:

- 2100: pre-collapse or deep legacy prototypes.
- 2120: late old-world military and industrial systems.
- 2140: degraded but recoverable post-collapse technology.
- 2163: campaign-start baseline and common working technology.
- 2170: first generation of post-start modernization.
- 2183: late-bookmark and high-tier regional power technology.
- 2200: rare, experimental, forbidden, or near-future capstone systems.

Technology files should define constants for row placement, for example:

`@y_2100 = 0`
`@y_2120 = 2`
`@y_2140 = 4`
`@y_2163 = 6`
`@y_2170 = 8`
`@y_2183 = 10`
`@y_2200 = 12`

Column constants should describe lanes, not arbitrary positions, such
as `@small_arms_lane`, `@support_lane`, `@rail_lane`, and
`@forbidden_lane`.

## Technology Domains

### Industry

Industry should cover reconstruction, machine tools, factory
efficiency, resource cycles, and distributed manufacturing. It should
mostly convert existing industrial ideas from the old
`ADISCORD_technologies.txt`, but with years moved onto the new grid and
positions made readable through constants.

### Electronics

Electronics should cover grid restoration, computing, encryption,
decryption, battlefield analytics, and command networks. Existing
doctrine dependencies on network and AI technologies should be migrated
to this domain.

### Infantry

Infantry should introduce real small-arms equipment tiers, plus
infantry kit and optics/support-weapons improvements. The first pass
should include enough equipment to satisfy country stockpiles and
production:

- baseline salvage weapons at 2140
- standardized weapons at 2163
- smart optics and modern kits at 2170
- advanced composite or directed systems at 2183
- experimental systems at 2200 in the forbidden or late-game lane

### Artillery

Artillery should add field artillery, anti-tank, anti-air, and rocket
or smart-munition branches. Existing `artillery_equipment_1` stockpile
usage must be mapped to a valid custom or compatibility equipment item.

### Armor

Armor should add restored chassis, remote weapon stations, combat
modules, heavy platform cores, and autonomous breakthrough platforms.
The first pass will use simplified buildable armor equipment variants
rather than a full tank designer overhaul. The requirement is valid
equipment IDs, sane production costs, and clean technology unlocks.

### Logistics and Trains

This domain should add trains, armored trains, hardened logistics,
railway guns, and railway support technology. It should also fix the
railway gun name errors by replacing vanilla railway gun names with the
custom A-Discord list.

### Air

Air should add reclaimed jets, VTOL frames, drone wings, interceptors,
rocketry, orbital tracking relics, and deep-strike targeting. Existing
custom air doctrine dependencies should continue to work after any tech
ID migration.

### Forbidden

Forbidden technologies should remain locked behind existing scripted
triggers such as legacy or black-grid access. They should sit at 2183
and 2200, not in the ordinary 2163 baseline path. Each forbidden
technology should pair a strong bonus with an explicit stability,
war-support, or access-cost drawback.

## Descriptor and Replace Path Policy

Replace paths should be added in small, justified groups. The minimum
candidate set for this redesign is:

- `common/technologies`
- `common/units/equipment`
- `common/raids`
- `common/operations`
- `common/units/names_railway_guns`

Potential additional paths after verification:

- `common/doctrines`
- `common/doctrines/grand_doctrines`
- `common/doctrines/subdoctrines`
- `common/doctrines/tracks`

Do not add broad `replace_path` entries without ensuring the mod has a
valid replacement database for that path. For `common/raids` and
`common/operations`, the first implementation pass should intentionally
disable vanilla content with the existing empty custom files, then
confirm with a fresh log pass that the game accepts the replacement.

## Compatibility Rules

- Existing history files that use `infantry_equipment_0`,
  `support_equipment_1`, or `artillery_equipment_1` must either keep
  valid compatibility equipment IDs or be migrated in one pass to new
  custom IDs.
- Existing scripted triggers and effects that check old
  `ADISCORD_tech_*` IDs should be updated when IDs move or split.
- Existing doctrine files must not reference missing technologies.
- AI equipment and production files must reference valid equipment
  archetypes and buildable variants.

## Migration Phases

1. Descriptor and conflict cleanup:
   add only the required `replace_path` entries and ensure custom
   replacement folders contain valid files.

2. Equipment baseline:
   create custom equipment archetypes and first buildable variants for
   infantry, support, artillery, armor, trains, railway guns, and air.

3. Technology split:
   split the current large custom technology file into domain files,
   convert years to the 2100-2200 grid, and keep dependency paths valid.

4. History and AI migration:
   update country starting technologies, stockpiles, production lines,
   and AI equipment references to valid new IDs.

5. Interface and localisation:
   add or reuse sprites and Russian localisation for all visible
   technologies and equipment.

6. Error-log pass:
   launch the game or use available validation tooling, then inspect the
   fresh `error.log`. Fix missing tech, missing equipment, invalid
   doctrine, invalid country tag, and invalid database-object errors in
   priority order.

## Validation

Use existing tooling where useful:

- `tools/validate_tc.py`
- `tools/validate_adiscord_tech_doctrine.py`

Add focused validation if necessary to check:

- every `has_tech` target exists
- every `leads_to_tech` target exists
- every `enable_equipments` target exists
- every history stockpile equipment ID exists
- every doctrine technology dependency exists
- every visible technology has localisation and a sprite

Manual validation:

- Start the 2163 bookmark and open the technology UI.
- Confirm year labels show the 2100-2200 grid.
- Confirm equipment can be researched and appears in production.
- Confirm trains and railway guns have valid names and variants.
- Re-check a fresh `error.log`; the repeated `Invalid tech` spam from
  vanilla raids and special-forces doctrines must be gone.

## Safety Constraints

- Keep each phase reviewable and reversible.
- Do not rewrite unrelated country, economy, focus, map, or state files.
- Do not delete existing custom technology concepts until their
  replacements are in place.
- Stage and commit only intentional files.
- Treat the existing dirty worktree as user-owned unless a change is
  directly part of this redesign.
