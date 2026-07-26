# A-DISCORD Economy and AI P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize A-DISCORD's economy and make fiscal state drive efficient, reversible AI decisions.

**Architecture:** Keep the existing country-scoped scheduler, add a four-state economic AI machine with hysteresis, make primary and secondary tiers semantically consistent, and expose cheap scripted triggers to engine-native AI strategies. Extend the repository validator to encode the economy/AI invariants before changing production scripts.

**Tech Stack:** HOI4 Clausewitz script, Lua defines only if proven necessary, Python static validators, Git.

## Global Constraints

- Do not add `every_country` inside country-scoped monthly or yearly pulses.
- Do not import Expert AI's scheduler, map IDs, vanilla tag aliases, global research queue, generated target matrices, or bulk defines.
- Every new identifier uses the `ADISCORD_` prefix.
- Conditional AI strategies have `abort` or `abort_when_not_enabled`.
- Existing saves receive guarded, versioned variable migration.
- AI performs at most one major discretionary fiscal action per economic tick.
- Naval AI and country-specific focus plans are out of scope for this iteration.

---

### Task 1: Encode economy and AI invariants

**Files:**
- Create: `tools/validate_adiscord_economy_ai.py`
- Modify: `tools/validate_tc.py`

**Interfaces:**
- Consumes: economy effects, triggers, on-actions, AI strategies, AI templates, building and equipment definitions.
- Produces: a deterministic CLI validator returning exit code `0` only when all P0 invariants hold.

- [ ] Write tests that require schema versioning, a four-state AI variable, casualty snapshots/deltas, positive base development gain, bounded liquidity actions, no impossible default production roles, and no global loops in economic pulses.
- [ ] Run `python tools/validate_adiscord_economy_ai.py` and confirm it fails on the current implementation for the intended missing invariants.
- [ ] Implement only validator plumbing and integrate its result into `validate_tc.py`.
- [ ] Run the validator again and confirm it still fails on production defects rather than parser errors.

### Task 2: Correct the economy core

**Files:**
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_society_development_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt`
- Modify: `common/scripted_triggers/ADISCORD_economy_triggers.txt`

**Interfaces:**
- Produces: `ADISCORD_economy_schema_version`, casualty snapshot/delta variables, deterministic macro pass, useful emission, bounded debt operations, and non-zero development gain.

- [ ] Add guarded schema migration and initialize only missing variables after first setup.
- [ ] Refresh economic building counters before treasury cap and derived calculations.
- [ ] Replace lifetime-casualty threshold stacking with a snapshot and non-negative monthly casualty delta.
- [ ] Set an explicit positive base economic-development gain and preserve multiplier-based balancing.
- [ ] Reorder macro calculations into a single deterministic pass.
- [ ] Make emission grant bounded liquidity and account for it in the ledger.
- [ ] Bound borrowing and repayment by actual debt/capacity/treasury room.
- [ ] Remove extraction-quota double counting and mutually-exclusive stretched-idea stacking.
- [ ] Run `python tools/validate_adiscord_economy_ai.py` and `python tools/validate_tc.py`.

### Task 3: Implement reversible economic AI and secondary parity

**Files:**
- Modify: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Modify: `common/scripted_triggers/ADISCORD_economy_triggers.txt`
- Modify: `common/on_actions/00_ADISCORD_on_actions.txt`

**Interfaces:**
- Produces: states `healthy=0`, `stressed=1`, `crisis=2`, `recovery=3`; cheap `ADISCORD_economy_ai_is_*` triggers; one-action budget policy; aggregated yearly semantics.

- [ ] Add failing validator assertions for all state transitions and action exclusivity.
- [ ] Implement hysteretic state transitions from treasury, streaks, debt ratio, inflation, and fiscal stress.
- [ ] Replace independent AI policy `if` blocks with an ordered `if/else_if` decision chain.
- [ ] Preserve army spending during war unless fiscal crisis is severe; restore spending one step at a time in recovery.
- [ ] Add debt repayment, restructuring, tax adjustment, war taxes, stabilization, and surplus investment branches.
- [ ] Replace `monthly_balance × 12` secondary handling with bounded aggregate fiscal semantics.
- [ ] Run both validators and inspect the diff for accidental global loops.

### Task 4: Connect fiscal state to military and construction AI

**Files:**
- Create: `common/ai_strategy/ADISCORD_economy_ai.txt`
- Modify: `common/ai_strategy/default.txt`
- Replace: `common/ai_strategy/doctrines.txt`
- Modify: `common/ai_strategy/ADISCORD_technology_doctrine_ai.txt`
- Modify: `common/ai_templates/ADISCORD_land_templates.txt`
- Modify: `common/ai_strategy/VAL.txt`

**Interfaces:**
- Consumes: economic-state triggers and actual A-DISCORD building/equipment/technology identifiers.
- Produces: crisis division cap, essential stockpile protection, custom-building desires, gated research/air/platform behavior, and staged templates.

- [ ] Add validator assertions that every referenced building/equipment/technology exists and conditional strategies abort cleanly.
- [ ] Remove unsupported naval, bomber, marine, paratrooper, and mobile production desires from the generic profile.
- [ ] Replace the vanilla-cloned doctrine strategy with A-DISCORD-only doctrine/role behavior and non-stacking concentration profiles.
- [ ] Add crisis/stressed/recovery/healthy strategies for wanted divisions, core equipment, air/platform demand, and custom economic buildings.
- [ ] Convert land templates to staged base/standard/specialized chains gated by stockpile, technology, factories, and fiscal state.
- [ ] Correct VAL's equipment-market sale-factor sign.
- [ ] Run both validators.

### Task 5: Documentation, regression review, and commits

**Files:**
- Create: `docs/ADISCORD_ECONOMY_AI_AUDIT_2026-07-11.md`
- Modify: relevant Russian and English localisation only if new player-visible text is introduced.

**Interfaces:**
- Produces: audit trail, formula/state reference, test matrix, and reviewable Git history.

- [ ] Document original defects, adopted Expert AI patterns, rejected subsystems, formulas, state thresholds, save migration, and observer test steps.
- [ ] Run `python tools/validate_adiscord_economy_ai.py`.
- [ ] Run `python tools/validate_tc.py`.
- [ ] Run `python tools/validate_adiscord_tech_doctrine.py` after expanding the sparse checkout to required assets.
- [ ] Review `git diff --check`, brace balance, unknown references, and forbidden global loops.
- [ ] Commit focused changes on `codex/economy-ai-p0`, push the branch, and report exact validation evidence.
