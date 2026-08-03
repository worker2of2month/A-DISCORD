# NAM Total Partition and EFL-AZH Alliance Design

## Goal

Replace the current fragmented NAM peace outcome with a deterministic settlement in which NAM and the temporary SLF uprising never survive the war, while EFL and AZH fight in one alliance that remains in place after every outcome.

## Current Problem

The resource-war start effect makes EFL and AZH declare separate wars on NAM. The scripted coalition settlement then ends those wars with white peace and transfers only a fixed subset of NAM states. It deliberately preserves NAM in state 689 and can preserve SLF in state 688, producing the disconnected post-war map reported by the player.

## Required Behaviour

### Alliance and war

- Immediately before hostilities, EFL and AZH leave any obsolete faction ties left by the Vorkerland collapse.
- EFL creates a permanent faction from `faction_template_ADISCORD_standard` and becomes its leader.
- AZH joins that faction before combat begins.
- EFL declares the annexation war on NAM.
- AZH joins EFL's existing war through `add_to_war`; the scenario must not create a second independent EFL-AZH war against NAM.
- The faction is never dismantled by any NAM resource-war outcome. It therefore exists during the war and after a coalition victory, a NAM victory, or a timeout settlement.
- The faction has a dedicated Russian localisation key and player-visible name.

### Temporary uprising

- SLF remains a temporary wartime uprising in state 688 so the existing event, forces, and third front are preserved.
- SLF must never become a surviving post-war country.
- Capitulation of NAM to SLF routes to the same coalition settlement used when EFL or AZH defeats NAM; the separate republican-victory route is not reachable in normal or debug gameplay.
- The obsolete debug action and news outcome that establish a permanent Svetlogorsk Republic are removed or redirected so they cannot restore the discarded result.

### Coalition settlement

The scripted settlement first ends the scenario wars and then partitions all relevant territory:

| Recipient | States | Rationale |
| --- | --- | --- |
| EFL | `67`, `225`, `228`, `230`, `231`, `688` | Northern and western resource belt, including Svetlogorsk |
| AZH | `226`, `227`, `229`, `689` | Southern and eastern depots, including the former NAM port remnant |

- The existing recipient cores and state-controller updates are retained and extended to states 688 and 689.
- EFL annexes SLF, thereby taking state 688; the settlement then applies the intended EFL core and controller there.
- After AZH receives its listed states, EFL annexes any remaining NAM territory as a safety net. This prevents a new NAM remnant if NAM gains an unexpected state during the war.
- Annexation cleanup must not transfer defeated NAM or SLF divisions into the victors unless an existing engine requirement makes troop transfer necessary.
- At completion, both `country_exists = NAM` and `country_exists = SLF` must be false, while EFL and AZH remain in the same faction.

### NAM victory

- The existing NAM victory settlement against EFL and AZH remains otherwise unchanged.
- Before that settlement completes, NAM recovers state 688 and annexes SLF if the uprising is still active.
- EFL and AZH remain independent countries and remain members of their common faction after the war.

### Other scenario behaviour

- Existing mobilisation, OOB loading, equipment grants, AI strategies, timeout duration, and temporary national spirits remain unchanged.
- The territorial assignment for a coalition victory is deterministic and does not use the peace-conference AI.
- No unrelated Vorkerland collapse, map-generation, country-history, fleet, or economy work is modified.

## Implementation Boundaries

Expected implementation files are limited to the NAM scenario effect, capitulation router, validator, debug decision wiring, NAM resource-war localisation, and testing documentation. Existing dirty or untracked NAM/map work outside those exact files must be preserved.

## Verification

The NAM validator will gain contracts that fail on the current implementation and require:

- creation of the EFL-led permanent faction before the declaration of war;
- AZH membership and `add_to_war` participation in the same conflict;
- no production or debug path to a surviving SLF republic;
- exact coalition state allocation, including EFL state 688 and AZH state 689;
- cleanup annexations for both SLF and NAM;
- SLF cleanup in the NAM-victory path;
- no faction teardown in any resolution effect;
- presence of the Russian faction localisation while retaining UTF-8 BOM.

After the focused red-green validator cycle, run the focused NAM validation, the related NAM/Vorkerland state-balance tests, `python -B tools/validate_tc.py --limit 300`, and `git diff --check` for the coherent implementation subset. Static checks establish script wiring and state contracts; a fresh in-game scenario remains necessary to prove runtime faction membership and the final map visually.
