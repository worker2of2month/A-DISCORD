# A-Discord Modern Land Warfare Implementation Plan

> Scope: the first playable APC/IFV vertical slice, mechanized armored formations,
> bounded strong-power starting access, and AI production reachability. This plan
> deliberately leaves country-specific model variants and the wider presentation
> pass to a following bounded change.

## Acceptance contract

- Add one custom mechanized transport archetype with three generations:
  `ADISCORD_armored_carrier_2163`, `ADISCORD_ifv_2170`, and
  `ADISCORD_networked_ifv_2183`.
- Add `ADISCORD_mechanized_infantry`; it must consume both infantry equipment
  and the custom carrier archetype, and use that archetype as its transport.
- Add a compact three-node generated technology programme in the armor tab.
  The nodes unlock the three vehicle generations; the first node also unlocks
  the mechanized battalion.
- Grant the recovered first generation and early MBT package only to `IVN`,
  `VAD`, and `WRK`.
- Convert AI and collapse armored formations from foot infantry to mechanized
  infantry. Preserve four tank battalions, support companies, and the bounded
  claimant reserve role.
- Give claimant setup enough first-generation carriers for its one armored
  group and make the claimant AI sustain both tank and carrier production.
- Add neutral global equipment names. Vorkerland-specific `VK... type` names
  remain a later country-variant presentation task so other countries do not
  inherit Vorkerland nomenclature.

## Task 1: Executable negative contracts

1. Add controlled-fixture tests for a modern land-force validator contract:
   archetype/variant inheritance, mechanized transport needs, technology
   unlock ownership, mechanized armored composition, and carrier production.
2. Add generator tests for the compact programme and bounded starting profile.
3. Run the focused tests and observe the expected failures before production
   changes.

## Task 2: Equipment and battalion

1. Add the carrier archetype and three variants to
   `common/units/equipment/ADISCORD_armor_equipment.txt`.
2. Add `ADISCORD_mechanized_infantry` to
   `common/units/ADISCORD_land_units.txt`.
3. Register the new technical IDs in `common/script_enums.txt`.
4. Implement the validator contract and prove the equipment/subunit portion.

## Task 3: Generated technology programme

1. Extend `tools/builders/build_adiscord_technology_system.py` with the compact
   mechanized programme, dependencies, unlocks, and `armored_core` starting
   profile.
2. Assign that profile only to `IVN`, `VAD`, and `WRK`; all other countries
   reach the programme through research.
3. Run the builder in check mode, apply explicitly, then run check again to
   prove idempotency. Never hand-edit generated technologies or generated tech
   localisation.

## Task 4: AI and collapse formations

1. Add a reachable mechanized formation and convert all armored AI target
   templates from foot infantry to `ADISCORD_mechanized_infantry`.
2. Add carrier stock gates and carrier production floors alongside MBT floors.
3. Convert the three claimant OOB templates and add carrier technologies and
   stockpile deliveries before their OOB load.
4. Update the force-design behavior tests before changing their expected
   compositions.

## Task 5: Neutral names and verification

1. Add the hand-maintained RU/EN equipment names and descriptions while
   preserving UTF-8 BOM.
2. Run focused unit/generator/technology/collapse tests and validators.
3. Run `python -B tools/validate_tc.py --limit 300` and `git diff --check`.
4. Record that full HOI4 restart, fresh campaign, and fresh logs remain required
   for runtime acceptance.
