# A-DISCORD Economy and AI P0 Design

## Objective

Stabilize the custom economy, make its AI reversible and state-driven, and connect fiscal health to engine-native construction, production, research, and division-template choices without importing the heavy Expert AI scheduler or vanilla-specific content.

## Scope

This iteration fixes P0 and the safest P1 defects only:

- restore non-zero economic development progression;
- calculate war and demographic fatigue from new casualties rather than lifetime casualties;
- make money emission provide liquidity while retaining an inflation cost;
- make macro indicators deterministic and independent of GUI refresh count;
- replace one-way economic AI with a four-state policy machine using hysteresis;
- make secondary AI use a cheap but fiscally equivalent annual update;
- remove impossible military-production desires and gate expensive AI behavior by fiscal state;
- add compact AI strategies for custom economic buildings and staged division templates;
- add static semantic validation for the new invariants.

Country-specific focus strategy plans, map-specific tactical AI, naval AI, espionage, and broad define changes are explicitly deferred.

## Architecture

### Economy state

Each simulated country owns `ADISCORD_economy_ai_state`:

- `0` healthy;
- `1` stressed;
- `2` crisis;
- `3` recovery.

The state is derived once per economic tick from treasury, monthly balance, deficit/surplus streak, debt ratio, inflation, and fiscal stress. Entry and exit thresholds differ so the AI cannot oscillate every month. The state is exposed through cheap scripted triggers and used by both the budget policy and static `ai_strategy` blocks.

### Budget policy

AI performs at most one major discretionary fiscal action per tick. Priority is:

1. crisis liquidity or restructuring;
2. spending and taxation correction;
3. debt repayment and stabilization;
4. recovery of spending;
5. investment from sustained surplus.

War prevents indiscriminate army-budget cuts. Recovery restores one budget step at a time.

### Update tiers

Player and primary countries keep monthly simulation. Secondary AI remains yearly for performance, but the yearly tick applies the same semantics in aggregate: annual balance, bounded automatic debt, fiscal stress, inflation, fatigue decay/gain, and AI policy. No `every_country` call is added to country-scoped pulses.

### AI integration

Static strategies consume only cheap economic triggers. Crisis reduces wanted divisions and expensive armor/air demand while protecting basic infantry/support production. Healthy and recovery states permit custom economic construction and advanced templates. AI template upgrades require technology, sufficient factories/equipment, and a non-crisis economy.

Expert AI content is used only as a design reference. No vanilla tag aliases, map IDs, global technology scans, generated building-target matrices, self-rescheduling events, or bulk define overrides are copied.

## Data-flow corrections

- Initialization is versioned with `ADISCORD_economy_schema_version`; migrations run once.
- Building counters refresh before treasury-cap calculations.
- Derived macro values use one ordered pass with no feedback depending on prior refresh calls.
- Casualty snapshots store the previous cumulative value and derive a non-negative delta.
- Development has an explicit base gain before multipliers.
- Spending/crisis ideas refresh only after their source state can change.

## Balance guardrails

- A normal developed country must not default within the first two monthly ticks at default settings.
- Emission grants bounded immediate treasury and raises emission/price pressure.
- Loans are bounded by both debt-capacity room and treasury-cap room.
- Crisis behavior preserves minimum military readiness during war.
- Secondary AI cannot erase deficits merely by clamping treasury to zero.

## Compatibility and performance

- Existing variable names remain valid.
- New variables use guarded initialization and a schema version.
- Removed legacy building IDs are not recreated; migration initializes new counters from actual owned buildings.
- Monthly and yearly on-actions remain country-scoped.
- Regular ticks must not scan all countries, all states globally, or all technologies.

## Verification

Automated validation must check brace balance, referenced trigger/effect existence, state-machine completeness, casualty-delta use, non-zero development base, country-scoped pulses, bounded debt/emission operations, allowed AI equipment/building IDs, and absence of forbidden global-loop patterns.

Manual observer verification remains necessary for six scenarios: healthy peace, six-month deficit, debt crisis, weak wartime country, sustained resource shortage, and platform/air unlock.
