# NAM internal uprising and coastal fleets

## Scope

Remove the public Free Islands Union concept while preserving the requested
rebel-country participant.  States 225-231 remain NAM-owned non-core colonies.
No IVN or Vorkerland central-war logic is changed.

## Internal uprising

SLF becomes the Svetlogorsk Uprising, an army-state formed by deserters,
underground organisers, and local opponents of the governor system. It takes
only compact state 688, a connected coastal cluster split by the state
generator from NAM mainland state 67. Province 689 is its capital, victory
point, port, and division spawn. EFL loses no territory.

SLF declares war only on NAM. If SLF is defeated, state 688 returns to NAM and
its temporary SLF core is removed. If SLF survives a NAM victory, it receives a
separate armistice and keeps its enclave. A coalition victory divides NAM's
remaining holdings between EFL and AZH; SLF never receives an island core,
claim, capital, or settlement.

## Coastal forces

The total-conversion replacement removes both vanilla ship equipment and unit
definitions, so the existing convoy equipment file receives one compact coastal
patrol archetype using the engine `screen_ship` category, while a mod-owned
naval subunit consumes that archetype. Existing country OOB files receive
exactly three small fleets:

- NAM: four patrol ships and 30 convoys;
- EFL: three patrol ships and 20 convoys;
- AZH: two patrol ships and 15 convoys.

Ports use verified coastal provinces: NAM 2038 in residual state 67 at level 1,
Svetlogorsk 689 in state 688 at level 2, EFL 6495 in state 70 at level 2, and
AZH 493 in state 69 at level 1. The single original NAM dockyard follows the
physical cluster into state 688; EFL and AZH each receive one dockyard. Country
history grants only the two basic existing naval technologies needed to
represent coastal patrol and convoy operation.

## Text and assets

Russian localisation, events, news, debug descriptions, national-spirit names,
OOB template names, and lore describe an internal Svetlogorsk uprising. Public
text contains no Free Islands Union or island-liberation narrative.  Existing
SLF flag assets and their generator are intentionally left untouched for a
separate replacement.

## Verification

The NAM validator must prove state 688 is the only SLF territorial base, state
70 never transfers to SLF, states 225-231 remain outside SLF effects, only
NAM/EFL/AZH receive fleets, all fleet equipment and ports exist, and public
localisation/lore contains none of the removed island-union/republic phrases.
The state-balance suite protects the generator-owned state split and NAM
colony/core geography.
