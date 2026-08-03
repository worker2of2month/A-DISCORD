# VAL Export Market and Runtime Repair Design

**Date:** 2026-08-03  
**Status:** Approved
**Scope:** Make VAL function as the preferred arms supplier for a fixed set of major countries and remove current runtime errors originating from VAL-specific files.

## Goal

VAL should act as the setting's principal arms exporter. WRK, STP, NOD, IVN, WIT, and NAM should be more likely to request access to VAL's international market and prefer VAL equipment when they have a genuine purchasing need. The change must preserve ordinary HOI4 diplomacy rather than grant access automatically.

The same change set will repair all errors in a fresh `error.log` whose source path is a VAL-specific file. At design time, the reproducible targeted failures are repeated invalid-idea reports from `common/scripted_effects/ADISCORD_VAL_rework_effects.txt` during administration, industry, army, and reputation tier transitions.

## Non-goals

- Do not grant market access automatically at startup.
- Do not make access reciprocal merely so VAL can buy from the six partners.
- Do not give buyers free equipment, factories, subsidies, or hidden economic bonuses.
- Do not force purchases when a buyer has no equipment shortage or cannot afford a contract.
- Do not add focuses, decisions, visible indicators, GUI, or a second contract system.
- Do not repair unrelated errors from Vorkerland, convoy equipment, generic AI commands, assets, or other systems.
- Do not rebalance the effects of VAL's administration, industry, army, or reputation tiers unless an engine-compatible repair strictly requires a representation change.

## Market Architecture

The implementation will follow the vanilla `common/ai_strategy` pattern used for international-market partners.

Each fixed buyer receives a dedicated, self-removing AI strategy block:

- WRK
- STP
- NOD
- IVN
- WIT
- NAM

The block is allowed only for its named original tag while the `Arms Against Tyranny` DLC is active. It is enabled while VAL exists and the buyer is not at war with VAL, and it uses `abort_when_not_enabled = yes` so hostility cannot leave stale preferences behind. The matching VAL acceptance blocks use the same DLC gate.

While enabled, the buyer will:

1. Have increased `diplo_action_desire` to request `market_access_rights` from VAL.
2. Have increased `equipment_market_trade_desire` toward VAL, making VAL the preferred seller when normal AI purchasing logic decides that equipment is needed.

VAL will receive matching `diplo_action_acceptance` preferences for market-access requests from the six buyers. These preferences will use the same existence and hostility guards.

The existing strategy named `VAL_Wants_To_Sell_Stuff` currently makes VAL request access to IVN, WRK, and WIT, which models VAL as a buyer. Those reversed desires will be removed. VAL's existing infantry sale-reserve behavior will remain unless runtime evidence shows it prevents the approved export loop from functioning.

## Market Data Flow

1. A fixed buyer evaluates its strategy and sees that VAL exists and is not its wartime enemy.
2. The buyer gains a strong desire to request access to VAL's market.
3. VAL evaluates the incoming request with a matching positive acceptance preference.
4. After ordinary diplomacy grants access, the buyer's equipment-market preference points toward VAL.
5. The normal HOI4 market AI decides whether the buyer has a shortage and enough civilian-industrial capacity to purchase equipment.
6. If war begins between the two countries, both the request and acceptance preferences deactivate.

No periodic scripted effect, automatic `give_market_access`, equipment transfer, or daily on-action is required.

## VAL Runtime Repair

The runtime repair will follow an evidence-first sequence:

1. Record the current fresh-log failures and the exact VAL source lines they reference.
2. Add a regression check covering every idea identifier read or written by the VAL administration, industry, army, and reputation transition effects.
3. Compare the failing transition structure with a complete working vanilla or installed TFR hidden-idea transition using the same HOI4 version.
4. State and test one root-cause hypothesis at a time.
5. Apply the smallest engine-compatible change that preserves the existing tier bonuses and permitted upgrade/downgrade behavior.

The intended tier behavior remains:

- Administration, industry, and army progress upward without accidental downgrades.
- Reputation may move both upward and downward.
- Exactly one tier in each family is active after a transition.
- Technical tiers remain hidden from the ordinary national-spirit display.
- Economy dirty-state refreshes remain connected where currently required.

The repair must not be declared complete merely because the static parser accepts the files. The corresponding effects must execute in a fresh HOI4 process without producing targeted VAL errors.

## Validation Design

### Automated regression tests

Add focused tests that fail before the market change and prove:

- The fixed buyer set is exactly WRK, STP, NOD, IVN, WIT, and NAM.
- Buyer and seller strategy blocks are gated behind `Arms Against Tyranny`.
- Every buyer desires `market_access_rights` from VAL.
- Every buyer has `equipment_market_trade_desire` toward VAL.
- VAL has matching acceptance preferences for all six buyers.
- Buyer and seller preferences deactivate during a war between the pair.
- VAL no longer requests access from IVN, WRK, or WIT as part of its supplier strategy.
- No automatic `give_market_access` or periodic market-maintenance on-action is introduced.
- Every VAL tier identifier referenced by transition effects resolves to one declared idea.
- Tier transitions retain their approved directionality and exclusivity contracts.

### Static gates

Run:

- The focused new market/runtime regression tests.
- `python tools/validate_adiscord_val_rework.py`
- `python tools/validate_adiscord_stp_val_crisis.py`
- The relevant VAL/STP regression-test modules.
- `python tools/validate_tc.py --limit 300`
- `git diff --check` for the complete scoped change.

### Runtime gate

Start a fresh HOI4 process and a fresh game with the current DLC set. Use existing VAL debug controls to initialize the rework and exercise minimum and maximum reputation. Exercise administration, industry, and army tier changes through the narrowest available debug or focus-completion path.

Then verify:

- The six buyer strategies load without unknown strategy, action, trigger, or effect errors.
- Market-access requests can be made and accepted through ordinary diplomacy.
- At least one controlled or observed buyer can obtain access to VAL's market and treats VAL as a preferred equipment partner when it needs equipment.
- No fresh `error.log` entry points to a VAL-specific file after all tier families are exercised.
- Existing non-VAL errors are reported separately and are not presented as regressions caused by this scope.

## Change Boundaries

Expected production changes are limited to the existing VAL AI-strategy and tier-transition layers. Tests or validator changes may be added under `tools/`. Russian localisation is changed only if a repaired runtime representation requires a player-facing string; the market AI preferences themselves require no new UI text.

The worktree contains extensive unrelated changes. Only the coherent VAL market/runtime subset and its tests may be staged or committed. Existing changes in Vorkerland, map, weather, economy, technology, portraits, localisation, and scenario content must remain untouched.

## Acceptance Criteria

The implementation is complete only when all of the following are true:

1. The six approved buyers use ordinary diplomacy to seek VAL market access.
2. Their equipment-market preference points to VAL without forcing unaffordable or unnecessary purchases.
3. VAL is biased to accept their requests and no longer behaves as the buyer in the old supplier strategy.
4. War between VAL and a buyer disables the relationship preferences.
5. All targeted automated and static gates pass.
6. A fresh runtime exercise covers all four VAL tier families and produces zero errors sourced from VAL-specific files.
7. Unrelated dirty work and unrelated runtime errors remain outside the commit.
