# A-Discord Land Technology and Weapon Icon Expansion Design

Date: 2026-08-15

## Goal

Turn the infantry and armor tabs into dense, readable late-future research programmes instead of sparse linear timelines. Use the supplied weapon artwork as the visual identity of the infantry equipment generations, add meaningful anti-tank and night-combat sub-branches, and make armor research represent APCs, IFVs, tanks, protection, fire control, and autonomy.

This is the first implementation phase. Artillery, support, electronics, air, naval, and industry will be redesigned in later phases using the same visual and mechanical rules after the land tabs have passed a fresh-game UI smoke test.

## Source ownership

- `tools/builders/build_adiscord_technology_system.py` remains the source of truth for generated technologies, folders, GFX declarations, effects, and localisation.
- Supplied PNG artwork is imported into a repository-owned source directory and converted deterministically. Generated DDS files are not hand-painted or edited after generation.
- Existing unrelated dirty files and Vorkerland work remain outside this phase.
- TFR and The Darkest Hour are structural and balance references only. Their IDs, localisation, and implementation blocks are not copied wholesale.

## Visual contract

### Main equipment milestones

Major infantry weapon and armored-vehicle unlocks use wide `190x84` technology cards. The full weapon or vehicle silhouette must remain readable at normal UI scale.

### Compact research nodes

Supporting and effect-only technologies use compact `72x72` icons. In particular, the entire night-combat branch stays compact: optics, image intensifiers, thermal sensors, target fusion, counter-illumination, and networked observation do not use wide equipment cards.

### Weapon art tier assignment

The supplied `1893x831` transparent PNG compositions are ranked and assigned as follows:

1. `64be3d7a-216b-4e7a-b700-81bab90b4963.png` - improvised/reclaimed arsenal.
2. `38a56c82-2c56-4bd4-ac5d-fa3eb7ecb0c6.png` - recovered service rifle.
3. `8bc896f1-f59b-4033-81f1-0686f0190ec6.png` - standardized battle rifle.
4. `98ce80ac-90bc-4af1-a9d4-3ba8f0132069.png` - transitional modular weapon.
5. `1c351184-5837-48cc-aa0b-ccdc921476f8.png` - suppressed modern assault system.
6. `1b0ec7af-6f88-4910-91e6-3c20ce8ff8cb.png` - networked smart rifle.
7. `64ecc162-8368-4a24-b0e7-7ce2ec6e0554.png` - programmable-munition weapon.
8. `53942e54-1065-498c-bad8-c123fa9925d7.png` - advanced impulse weapon.
9. `b3efd823-cdcb-4fa1-8f07-52e8ecb71b37.png` - final resilient combat-network weapon.

`5b9855c0-7d17-438b-898b-136fe17008fb.png` is reserved as the visual source for compact night-operations and smart-optics crops. `3eabf3d3-b69d-4bb9-b186-2cad9ff6b5de.png` and `a0a12ff4-e484-4f53-97d0-b8c706feda24.png` are alternates for early equipment cards if downscale tests show better silhouette readability.

Conversion preserves alpha, fits the non-transparent content inside a safe margin, uses high-quality downsampling, and emits deterministic DDS output. A contact sheet is generated for visual review of tier order and crop legibility.

## Infantry tree

The infantry folder remains a horizontal time axis. It gains six visually separated programmes with cross-links at major capability gates.

### Service weapons

Nine equipment milestones progress from reclaimed weapons to networked late-future small arms. Milestones unlock actual equipment generations; intermediate research improves reliability, soft attack, defense, and production in small bounded increments.

### Squad weapons

Machine guns, grenade systems, programmable ammunition, suppression control, and distributed fire teams form a parallel branch. It supports the service-weapon line without duplicating the same modifier package.

### Anti-tank weapons

A distinct compact branch progresses through shaped-charge launchers, tandem warheads, guided missiles, top-attack seekers, loitering anti-armor cells, and late kinetic or directed terminal attack. It primarily improves infantry and anti-tank hard attack, piercing, and limited breakthrough. Major milestones may unlock later anti-tank equipment; effect-only nodes remain compact.

The approved incendiary-bottle icon is preserved byte-for-byte as a 72x72 runtime master; the icon builder copies that canonical DDS while rendering the later anti-tank tiers from their larger source art.

### Night combat

A fully compact branch progresses through passive intensifiers, thermal imagers, fused sights, squad target sharing, counter-illumination, and distributed night engagement. Its main effects are bounded `land_night_attack`, reconnaissance, coordination, and limited defense. It must not become a generic attack multiplier branch.

### Protection and specialist forces

Body protection, load carriage, combat medicine, CBRN protection, infiltration, urban entry, and specialist sustainment remain supporting programmes. Their layout is tightened and cross-linked to night combat and squad weapons where the dependency is mechanically credible.

## Armor tree

The armor folder uses major wide equipment cards surrounded by compact module and programme nodes.

### Vehicle families

- APC and protected mobility.
- IFV and reconnaissance combat vehicles.
- Main battle tanks.
- Heavy breakthrough tanks.
- Recovery and engineering vehicles.
- Late unmanned and optionally crewed platforms.

### Capability programmes

- mobility and powerpack;
- armor arrays and signature management;
- active protection and countermeasures;
- fire control and sensor fusion;
- main armament and ammunition;
- crew survival and maintainability;
- tactical networking and bounded autonomy.

Major equipment generations require appropriate programme gates. The graph contains real forks: survivability versus offensive overmatch, mass-producible vehicles versus advanced low-volume systems, and crewed resilience versus autonomy. Forks reconverge only at explicitly late integration technologies.

## Balance rules

- A research node should have one clear battlefield purpose.
- Repeated flat attack bonuses are avoided; bonuses are distributed among equipment stats, categories, terrain/night performance, reliability, production, and organisation-related values.
- Individual modifiers remain modest so a completed branch does not create runaway multiplicative stacking.
- Equipment unlocks appear at recognizable programme milestones rather than every year.
- IVN, VAD, and WRK retain the intended early access to advanced starting programmes; other countries research them through normal progression.
- AI weights must understand the new prerequisites and prioritize viable capability packages rather than isolated late nodes.

## Layout rules

- Time progresses left to right in infantry and armor.
- The main equipment line is visually dominant, with compact capability lanes above and below it.
- Year columns are close enough to create density without overlapping cards or connectors.
- Cross-links are limited to meaningful dependencies and must remain readable at the default zoom.
- Folder viewport width and technology coordinates are validated together so icons do not drift off-screen.

## Validation

The implementation is complete only after:

1. deterministic icon conversion and identical hashes on a second run;
2. generator `--check`, then explicit `--apply`, then idempotent second `--apply`;
3. focused generator, validator, icon-size, graph, prerequisite, and starting-access tests;
4. UTF-8 BOM verification for Russian localisation;
5. `python -B tools/validate_tc.py --limit 300`;
6. `git diff --check`;
7. full Hearts of Iron IV restart, fresh campaign, infantry and armor screenshots at normal zoom, and inspection of fresh logs.
