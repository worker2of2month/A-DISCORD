# A-DISCORD: Global Infantry Weapon Model Progression

Date: 2026-08-16
Status: approved

## Objective

Give every A-DISCORD infantry-equipment generation a deliberate, visible 3D
weapon progression instead of selecting unrelated regional weapon sets. The
progression is global: country identity continues to come from the soldier
model, uniform, and animation set, while the equipped weapon comes from the
same equipment tier for every country.

This design supersedes the 3D mapping described in
`2026-08-16-adiscord-small-arms-and-personal-antitank-design.md`. In
particular, HOI4 maps `visual_level = 0` to the base infantry entity,
`visual_level = 1` to the `_2` entity, and so on. The earlier document's use
of only levels 0-3 is not the target architecture.

## Approved progression

The existing nine infantry-equipment IDs remain stable. Eight distinct
vanilla weapon meshes are used, so the first two equipment generations share
the Johnson M42 model. Every later generation advances by exactly one model.

| Equipment | Year | Visual level | Selected entity level | Weapon mesh |
| --- | ---: | ---: | --- | --- |
| `infantry_equipment_0` | 2140 | 0 | base infantry entity | `HOL_rifle_johnson_m42.mesh` |
| `ADISCORD_infantry_equipment_2156` | 2156 | 0 | base infantry entity | `HOL_rifle_johnson_m42.mesh` |
| `ADISCORD_infantry_equipment_2163` | 2163 | 1 | `_2` | `SHX_rifle_arisaka.mesh` |
| `ADISCORD_infantry_equipment_2168` | 2168 | 2 | `_3` | `MEX_rifle_mondragon_m1908.mesh` |
| `ADISCORD_infantry_equipment_2170` | 2170 | 3 | `_4` | `XSM_smg_mauser712.mesh` |
| `ADISCORD_infantry_equipment_2178` | 2178 | 4 | `_5` | `HOL_smg_bergmann_mp_29.mesh` |
| `ADISCORD_infantry_equipment_2183` | 2183 | 5 | `_6` | `YUN_smg_thompson.mesh` |
| `ADISCORD_infantry_equipment_2193` | 2193 | 6 | `_7` | `PRC_smg_ppsh41.mesh` |
| `ADISCORD_infantry_equipment_2200` | 2200 | 7 | `_8` | `MEX_smg_mendoza_rm2.mesh` |

The order is an in-world visual progression, not a claim that the original
historical production dates occur in A-DISCORD's chronology.

## Asset policy

The meshes, their material bindings, and their textures are loaded directly
from the installed vanilla DLC asset databases. The mod does not copy or
rename Paradox meshes or textures.

The complete audited chains are:

- Man the Guns: HOL Johnson rifle, HOL Bergmann SMG, MEX Mondragon rifle, and
  MEX Mendoza SMG;
- Waking the Tiger: SHX Arisaka rifle, XSM Mauser 712, YUN Thompson, and PRC
  PPSh-41.

Each source already provides right-hand, left-hand, and long-idle weapon
entities with the required transforms and animations. A-DISCORD wrapper
entities clone those existing entities rather than recreating transforms by
hand. This makes Waking the Tiger and Man the Guns graphical dependencies for
the full progression; missing-DLC behavior must be checked in a fresh runtime
before release.

## Entity architecture

### Shared weapon wrappers

A late-loaded asset file,
`gfx/entities/zy_ADISCORD_infantry_weapon_progression.asset`, owns a neutral
wrapper family for levels 0-7. Each level contains:

- `ADISCORD_infantry_weapon_<level>_right_entity`;
- `ADISCORD_infantry_weapon_<level>_left_entity`;
- `ADISCORD_infantry_weapon_<level>_long_idle_entity`.

Each wrapper clones the matching vanilla country weapon entity. The wrappers
do not define a new mesh, transform, animation, or scale when the source
entity already supplies it.

The `zy_` prefix is deliberate: this file loads after the vanilla and DLC
infantry assets, but before `zz_ADISCORD_country_infantry.asset`. Therefore all
clone parents exist before the wrapper layer, and all wrapper entities exist
before the custom-uniform layer attaches them.

### Generic infantry entities

The same late asset layer owns the weapon attachments of the generic infantry
selection chain:

- `infantry_entity` for visual level 0;
- `generic_infantry_2_entity` through `generic_infantry_8_entity` for visual
  levels 1-7.

The soldier body, animations, props, and scale continue to come from the
existing generic infantry parents. Only the four named weapon attachments are
set by A-DISCORD:

- `rifle1` on `Right_Hand_node` uses the level's right-hand wrapper;
- `rifle2` on `Left_Hand_node` uses the level's left-hand wrapper;
- `rifle3` on `mid_back_node` uses the level's long-idle wrapper;
- `rifle4` on `Root_node_2` uses the level's right-hand wrapper.

The late-load override is intentionally narrow. It does not copy the full
vanilla `units_infantry.asset`. Runtime validation must confirm that the
engine's last-loaded entity definitions are selected without duplicate-name
errors. If that premise fails, implementation stops for an architecture
revision rather than silently copying the entire vanilla database.

### Custom uniforms

`gfx/entities/zz_ADISCORD_country_infantry.asset` continues to own the custom
soldier bodies for:

- STP and its NOD clone;
- VAL;
- CIN;
- OSF;
- APH infantry and APH mountaineers.

Every custom family receives a complete base plus `_2` through `_8` selection
chain. The existing `pdxmesh`, body animation parent, scale, and non-weapon
props are preserved. The four weapon attachments point to the same neutral
wrapper used by the generic entity at that visual level. Existing direct ENG
and USA weapon attachments are removed from this A-DISCORD-owned file.

No country receives a separate regional equipment progression. NOD continues
to share the STP uniform family, but its selected weapon is still determined
only by equipment visual level.

## Data ownership

`common/units/equipment/ADISCORD_infantry_equipment.txt` is a directly
maintained gameplay source. It is not listed among the technology builder's
generated outputs. Its exact visual-level sequence becomes:

`0, 0, 1, 2, 3, 4, 5, 6, 7`

`tools/validators/validate_adiscord_tech_doctrine.py` and focused tests mirror
that sequence as an acceptance contract. The entity asset files are also
directly maintained source files, with focused tests treating their
wrapper-to-vanilla mapping and entity coverage as a contract.

The equipment IDs, statistics, unlock technologies, research layout, icons,
and player-facing weapon series names do not change as part of this 3D model
work.

## Validation contract

Implementation begins test-first. Focused tests must fail before production
changes and then prove all of the following:

1. The nine generated equipment blocks contain exactly the approved visual
   levels in approved order.
2. All 24 neutral wrapper entities exist and clone the exact approved vanilla
   right, left, and long-idle source entities.
3. The generic base entity and `_2` through `_8` entities exist and contain
   the correct four wrapper attachments.
4. STP, NOD, VAL, CIN, OSF, APH infantry, and APH mountaineers have complete
   entity coverage through `_8` and preserve their existing body meshes.
5. No direct ENG or USA infantry-weapon attachment remains in the
   A-DISCORD-owned country infantry asset.
6. Every referenced source entity, pdxmesh identifier, `.mesh` file, and
   texture in the audited vanilla chains exists in the installed game tree.
7. The technology builder still passes `--check`, proving that the equipment
   visual change did not disturb generated technology outputs.
8. Focused tests, `python -B tools/validate_tc.py --limit 300`, and both
   unstaged and cached `git diff --check` pass.

Static checks cannot establish Clausewitz load order or visual selection. The
runtime acceptance gate is a complete HOI4 restart followed by a fresh
campaign. At minimum, one generic country and one custom-uniform country must
be inspected at early, middle, and late equipment levels. Fresh `error.log`
must contain no missing entity, mesh, texture, animation, or duplicate-entity
errors attributable to this progression.

## Out of scope

- no new 3D models or textures;
- no copying of vanilla DLC assets into the mod;
- no regional or country-specific weapon progression;
- no change to soldier uniforms, country graphical cultures, or battalion
  models;
- no change to equipment stats, technology effects, AI, division templates,
  starting technologies, or starting stockpiles;
- no old-save migration or compatibility repair.

## Acceptance result

On a fresh campaign, researching or receiving the next infantry-equipment
generation visibly advances the global weapon sequence while every country
retains its intended soldier model. The 2140 and 2156 equipment share Johnson;
each generation from 2163 through 2200 advances to the next approved model,
ending with Mendoza RM2.
