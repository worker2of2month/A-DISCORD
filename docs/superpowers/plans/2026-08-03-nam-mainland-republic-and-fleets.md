# NAM Internal Uprising and Coastal Fleets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the island-based SLF story with a compact internal Svetlogorsk Uprising in state 688 and give NAM, EFL, and AZH proportionate coastal patrol forces.

**Architecture:** Existing NAM event/effect/OOB/localisation files remain the scenario boundary. A patrol-ship equipment pair and one matching mod-owned naval subunit are added because the total conversion replaces both vanilla equipment and vanilla unit definitions. State-history ports and existing country/OOB files provide the rest of the naval setup.

**Tech Stack:** HOI4 Clausewitz script, Python focused validator, Russian UTF-8-BOM localisation.

## Global Constraints

- States 225-231 remain NAM-owned non-core colonies.
- SLF receives no island core, claim, capital, or settlement.
- Exactly NAM, EFL, and AZH receive fleets; no other beneficiary does.
- Do not modify IVN intervention files or SLF flag assets/generator.
- Do not commit from the shared dirty worktree; parent integration owns commits.

---

### Task 1: Lock the scenario contracts

**Files:**
- Modify: `tools/validate_adiscord_nam_resource_war.py`

**Interfaces:**
- Consumes: existing NAM scenario files loaded by `read(relative)`.
- Produces: static failures for island SLF ownership, missing state-70 setup, public island-union prose, invalid fleet counts, ports, technologies, and ship equipment.

- [x] Add assertions that `ADISCORD_nam_resource_war_start_mainland_rebellion` transfers and cores only state 688 for SLF, that state 70 and all `225..231` tokens are absent from SLF settlement blocks, and that state 67 never transfers to SLF.
- [x] Add assertions for public text: `Союз свободных островов`, `островные освободительные`, and `Island Liberation Column` must be absent from NAM localisation, lore, effects, ideas, events, and SLF OOB.
- [x] Add assertions for one `ADISCORD_coastal_patrol_ship_1` archetype/equipment definition; fleet ship counts NAM=4, EFL=3, AZH=2; convoy stocks 30/20/15; ports 689/6495/493; and two explicit naval technologies in each country history.
- [x] Run `python -B tools/validate_adiscord_nam_resource_war.py`; expect failure on the old island implementation and absent naval setup.

### Task 2: Create the compact internal uprising

**Files:**
- Modify: `common/scripted_effects/ADISCORD_nam_resource_war_effects.txt`
- Modify: `events/ADISCORD_nam_resource_war_events.txt`
- Modify: `common/ideas/ADISCORD_nam_resource_war_ideas.txt`
- Modify: `history/units/SLF_nam_resource_war.txt`
- Modify: `localisation/russian/ADISCORD_nam_resource_war_l_russian.yml`
- Modify: `docs/lore/countries.md`

**Interfaces:**
- Produces: `ADISCORD_nam_resource_war_start_mainland_rebellion` and `ADISCORD_nam_insurgent_columns`.

- [x] Rename the island effect/spirit/OOB template and transfer state 688 into the SLF recipient scope, set SLF capital 688, add SLF core 688, spawn at province 689, and declare war only on NAM.
- [x] On SLF defeat, white-peace NAM, return state 688 to NAM, remove the temporary SLF core, and restore NAM control.
- [x] On coalition victory, transfer all NAM states 225-231 only to EFL/AZH; leave surviving SLF in state 688. On NAM victory, do not transfer an island to SLF and give a surviving uprising a separate armistice.
- [x] Replace the public name with `Светлогорское восстание`, party with `Временный штаб восстания`, and rewrite event/news/debug/lore prose around an internal army-state.

### Task 3: Add compact coastal patrol forces

**Files:**
- Modify: `common/units/equipment/ADISCORD_convoy_equipment.txt`
- Create: `common/units/ADISCORD_naval_units.txt`
- Modify: `common/script_enums.txt`
- Modify: `history/units/NAM.txt`
- Modify: `history/units/EFL.txt`
- Modify: `history/units/AZH.txt`
- Modify: `history/countries/NAM - NamestnikLand.txt`
- Modify: `history/countries/EFL - Eflor.txt`
- Modify: `history/countries/AZH - Azhar Black Basin.txt`
- Modify: `history/states/67-67.txt`
- Modify: `history/states/70-70.txt`
- Modify: `history/states/69-69.txt`

**Interfaces:**
- Produces: `ADISCORD_coastal_patrol_ship` archetype, active `ADISCORD_coastal_patrol_ship_1` equipment, and `ADISCORD_coastal_patrol_vessel` subunit using the engine `screen_ship` category.

- [x] Define the patrol ship with screen stats in the existing equipment file and a matching mod-owned naval subunit; register its IDs in the equipment bonus enum.
- [x] Add one fleet/task force per country using verified coastal locations: NAM 2038 with four ships, EFL 6495 with three, AZH 493 with two; keep the uprising supply port at 689.
- [x] Add convoy stockpiles of 30/20/15 to existing OOB `instant_effect` blocks.
- [x] Add level-2/2/1 naval bases and one dockyard to states 67/70/69 respectively.
- [x] Grant `ADISCORD_tech_coastal_patrols` and `ADISCORD_tech_convoy_routing` in each of the three existing country-history files.

### Task 4: Verify the integrated scenario

**Files:**
- Test: `tools/validate_adiscord_nam_resource_war.py`
- Test: `tools/test_vorkerland_nam_state_balance.py`

**Interfaces:**
- Consumes: all Task 2-3 outputs.
- Produces: evidence for parent integration; runtime remains a separate launch gate.

- [x] Run `python -B tools/validate_adiscord_nam_resource_war.py`; expect PASS.
- [x] Run `python -B -m unittest tools.test_vorkerland_nam_state_balance -q`; expect all tests PASS.
- [x] Run `python -B -m unittest tools.test_debug_decision_localisation -q`; expect PASS.
- [x] Run `python -B tools/validate_tc.py --limit 300`; expect every section `OK`.
- [x] Run scoped trailing-whitespace and forbidden-phrase scans; expect no findings.
- [ ] Complete one fresh HOI4 launch after the corrected SLF recipient scope and inspect the new logs.
