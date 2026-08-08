# A-Discord Economy Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a readable four-policy economy, replace construction control with research investment, remove debt capacity, add non-spamming debt crises and notifications, and keep weekly accounting genuinely lightweight.

**Architecture:** Schema 12 preserves the scalar/cached accounting model. Tax, military, research, and social policies are five-level variables with targeted refresh effects. Construction expense follows real activity automatically. Debt risk is derived from income, interest, debt, and sustained deficit; it is reconciled after each settlement and debt action. GUI and scripted localisation consume cached previews instead of recalculating the economy.

**Tech Stack:** HOI4 scripted effects/triggers/ideas/GUI/scripted localisation/events, Russian and English localisation, Python contract tests and validators.

## Global Constraints

- Preserve treasury, debt principal, and every accounting-history variable during migration.
- Expose exactly four policies: taxation, military spending, research/science spending, and social spending.
- Construction remains an expense category but is not a player policy.
- There is no debt-capacity statistic, gameplay gate, hidden maximum, or replacement variable with the same semantics.
- Automatic borrowing covers only the uncovered negative treasury amount.
- Debt thresholds are exact: 10% strain, 25% crisis, 40% for four settlements emergency, then 13 settlements with negative weekly balance for default.
- AI uses the same inflation, debt, crisis, and default rules as the player.
- Weekly accounting may consume cached scalars but may not reach `has_idea`, full building recounts, `every_country`, or full spending-idea rebuilds.
- Russian and English new economy localisation have matching key sets; Russian remains UTF-8 BOM.
- `common/on_actions/00_ADISCORD_on_actions.txt` is read-only for this recovery. A missing cache invalidation is implemented inside the existing economy entry effects or `common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt`; if neither interface can express it safely, stop and revise the plan instead of conditionally taking ownership.

---

## Task 1: Replace Stale Economy Contracts with Schema-12 RED Tests

**Files:**
- Update: `tools/tests/test_adiscord_economy_weekly_contracts.py`
- Update: `tools/tests/test_validate_adiscord_gui_contracts.py`
- Update: `tools/validators/validate_adiscord_economy_ai.py`

- [ ] Add failing tests named `test_schema_twelve_maps_construction_policy_to_research_without_resetting_ledger`, `test_construction_policy_is_retired_and_construction_spend_tracks_real_activity`, and `test_research_policy_has_five_levels_and_level_five_construction_bonus_is_bounded`.
- [ ] Add failing tests named `test_debt_capacity_is_absent_from_runtime_and_public_modifier_api`, `test_automatic_borrowing_covers_full_uncovered_deficit_without_capacity_gate`, `test_debt_tiers_use_interest_share_and_four_thirteen_settlement_streaks`, `test_debt_notifications_are_first_loan_and_upward_transitions_only`, and `test_repayment_recalculates_interest_and_can_lower_debuff_immediately`.
- [ ] Add failing tests named `test_weekly_path_has_no_idea_query_building_recount_or_country_iteration`, `test_ai_assistance_is_bounded_reversible_and_never_player_visible`, and `test_recovery_owned_economy_localisation_has_bilingual_keys_and_russian_bom`.
- [ ] Add GUI RED tests for four named policy rows, expanded row/arrow hitboxes, next-level previews, disabled reasons, delayed value explanations, and a dynamic debt notification.
- [ ] Run the individual new tests and record expected failures before modifying engine files.
- [ ] Commit tests only as `test: define economy schema 12 contracts`.

## Task 2: Migrate Construction Policy to Research Policy

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_economy_triggers.txt`
- Update: `common/ideas/ADISCORD_economy_ideas.txt`
- Update: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`
- Update: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Set `ADISCORD_economy_schema_version` to 12 and add idempotent migration from the immediately previous schema.
- [ ] Introduce `ADISCORD_economy_research_spending_mode` clamped 1-5 and `ADISCORD_economy_research_budget_change_cooldown` clamped 0-3.
- [ ] Copy the old construction mode 1:1 into research mode, set the new research cooldown to 0, remove all five obsolete construction-policy ideas, clear obsolete construction control/signature variables, and preserve treasury, debt, income/expense history, and settlement counters.
- [ ] Replace construction increase/decrease availability and controls with research controls. Keep one policy action per cooldown period.
- [ ] Apply research expense multipliers `0.60 / 0.80 / 1.00 / 1.30 / 1.60` to the existing research expense base.
- [ ] Remove construction policy multipliers from construction expense and development calculations; automatic construction expense continues to use real installed/active construction scalars.
- [ ] Define five research ideas: research speed `-8% / -3% / 0 / +3% / +5%`; only level 5 adds `production_speed_buildings_factor = 0.02`, and no level may exceed +3% construction speed.
- [ ] Run the three schema/policy focused tests and the economy validator until GREEN.
- [ ] Commit as `feat(economy): migrate construction policy to research`.

## Task 3: Add Targeted Policy Refresh and Preview Caches

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`
- Update: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Add preview variables for each `tax|army|research|social` and `increase|decrease`: target level and weekly balance delta.
- [ ] Implement `ADISCORD_economy_refresh_policy_previews` using fixed multiplier tables and cached pre-tax/expense-category scalars.
- [ ] Implement `ADISCORD_economy_refresh_tax_policy`, `_army_policy`, `_research_policy`, and `_social_policy`, plus `ADISCORD_economy_sum_expenses`.
- [ ] On a policy click, recalculate only the dependent income/expense category, debt interest if income changed, totals, weekly forecast, that policy idea, previews, and GUI.
- [ ] Prohibit policy-click paths from invoking the full building recount or unrelated spending-idea refresh.
- [ ] Test exact preview inputs against the same multiplier tables used by accounting so tooltip numbers cannot silently drift.
- [ ] Commit as `perf(economy): refresh only changed policy data`.

## Task 4: Remove Debt Capacity Atomically

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_economy_triggers.txt`
- Update: `common/modifier_definitions/00_ADISCORD_economy_modifiers_definition.txt`
- Update: `common/synchronized_dynamic_tokens/ADISCORD_tokens.txt`
- Update: `common/ideas/_economic.txt`
- Update: `common/ideas/ADISCORD_laws.txt`
- Update: `common/ideas/ADISCORD_VAL_rework_ideas.txt`
- Update: `localisation/russian/ADISCORD_economy_modifiers_l_russian.yml`
- Update: `docs/economy/economic-modifiers.md`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Make `test_debt_capacity_is_absent_from_runtime_and_public_modifier_api` fail against all capacity variables, triggers, tokens, modifiers, documentation, UI, and localisation.
- [ ] Delete capacity calculations, ratio-as-capacity logic, capacity-room triggers, manual-loan room checks, the synchronized token, and the public modifier definition in one commit.
- [ ] Replace each idea/law `ADISCORD_economy_debt_capacity_factor = X` with same-sign `ADISCORD_economy_creditworthiness_factor = X`; merge with an existing creditworthiness entry in the same modifier block rather than duplicating the key.
- [ ] Keep only a non-gameplay numeric-overflow/corruption guard. A stored-debt clamp such as `debt <= 5000` is prohibited because it becomes a hidden capacity.
- [ ] Update modifier documentation and localisation to explain creditworthiness without mentioning debt room.
- [ ] Run focused capacity-removal tests, modifier validation, economy AI validation, and `rg -n "debt_capacity" common interface events localisation docs tools` with only explicitly versioned migration/debt-report exceptions allowed.
- [ ] Do not commit an intermediate state after this step; immediately complete Task 5 because removal of the old capacity API and replacement of its borrowing callers form one atomic change.

## Task 5: Implement Interest-Pressure Debt Metrics and Full Deficit Borrowing

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_economy_triggers.txt`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Add `ADISCORD_economy_weekly_interest`, `ADISCORD_economy_interest_share_income`, `ADISCORD_economy_debt_income_ratio`, and `ADISCORD_economy_debt_pressure`.
- [ ] Implement `ADISCORD_economy_calculate_debt_metrics`: weekly interest equals monthly debt service times `3/13`; interest share equals weekly interest times 100 divided by max(weekly gross income, 0.1); debt/income ratio equals debt times 100 divided by max(annualized monthly gross income, 1); pressure equals `0.20 * debt_income_ratio + 1.50 * interest_share + 2 * deficit_streak`, clamped 0-100.
- [ ] Ensure the calculation order is debt/income -> creditworthiness/rate -> interest/share -> state, with at most one interest recomputation after a state change and no double counter increment.
- [ ] Rewrite automatic borrowing to add exactly the uncovered negative-treasury amount to debt and treasury, with no capacity-room calculation and no full spending-idea refresh.
- [ ] Rewrite manual bonds/external loan/restructuring availability against debt state, interest share, creditworthiness, treasury room, and existing monthly cooldown only.
- [ ] On repayment, reduce principal, recalculate rate/interest/pressure immediately, and call the downward reconciler without advancing weekly streaks.
- [ ] Run automatic borrowing, debt metric, repayment, and weekly performance tests.
- [ ] Commit Tasks 4-5 atomically as `feat(economy): replace debt capacity with interest pressure` after both tasks' focused tests pass.

## Task 6: Add Persistent Debt States, Debuffs, and Non-Spam Notifications

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/ideas/ADISCORD_economy_ideas.txt`
- Update: `events/ADISCORD_economy_events.txt`
- Update: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`
- Update: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`
- Update: `localisation/russian/ADISCORD_economy_l_russian.yml`
- Create: `localisation/english/ADISCORD_economy_l_english.yml`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Add `ADISCORD_economy_debt_state` values 0 healthy, 1 fiscal strain, 2 debt crisis, 3 budget emergency, 4 default; add emergency/default streaks and last-notified/first-loan flags.
- [ ] Implement `ADISCORD_economy_update_debt_state_after_settlement`: state 1 at interest share >=10%; state 2 at >=25%; emergency streak increments at >=40% and state 3 after four settlements; default streak increments while >=40% and weekly balance is negative and state 4 after thirteen settlements; reset a streak immediately when its condition fails.
- [ ] Implement `ADISCORD_economy_reconcile_debt_state_after_action` for immediate downward state/debuff changes after repayment without incrementing streaks.
- [ ] Define debuffs exactly: strain PP gain -0.02; crisis PP -0.05 and research -1%; emergency PP -0.10, research -3%, construction -4%, stability -3%; default PP -0.18, research -7%, construction -8%, factory output -5%, stability -8%.
- [ ] Add pending notification kind 1 first loan, 2 strain, 3 crisis, 4 emergency, 5 default, plus amount/previous/new-state caches and `ADISCORD_economy_queue_debt_notification`.
- [ ] Allow one modal per settlement. If first borrowing and tier rise coincide, show the higher-tier notice with the borrowed amount/cause. Do not notify routine later borrowing.
- [ ] Lower `last_notified_debt_state` when the country genuinely improves so a later deterioration can notify again.
- [ ] Add player-visible event/popup text with cause, current debt, weekly interest, interest share, current effect, and next risk.
- [ ] Run transition, notification, repayment, idea, event-ID, and localisation tests.
- [ ] Commit as `feat(economy): add persistent debt state transitions`.

## Task 7: Make the Weekly Call Graph Actually Lightweight

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/scripted_effects/ADISCORD_economy_modifier_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_economy_triggers.txt`
- Update: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Replace the current direct-text check with a transitive scripted-effect/trigger call-graph test rooted at weekly prepare/light update/settlement.
- [ ] Require weekly reachability to reject `has_idea`, building counts, country iteration, law/idea wrappers, full modifier collection, full spending-idea rebuild, and full GUI policy rebuild.
- [ ] Cache taxation, industrial, welfare, education, policy, and law scalars on initialization, migration, monthly/full refresh, and exact dirty events.
- [ ] Ensure automatic borrowing updates debt metrics/state/notification only and never calls `ADISCORD_economy_refresh_spending_ideas`.
- [ ] Keep full building recount on initialization, migration, quarterly/full refresh, GUI-open explicit refresh, and relevant ownership/building changes only.
- [ ] Run the transitive graph test and existing scheduling tests.
- [ ] Commit as `perf(economy): isolate weekly accounting from heavy queries`.

## Task 8: Update Economy AI and Bound Assistance

**Files:**
- Update: `common/scripted_effects/ADISCORD_economy_effects.txt`
- Update: `common/ai_strategy/ADISCORD_economy_ai.txt`
- Update: `common/ideas/ADISCORD_minor_optimization_ideas.txt`
- Update: `common/scripted_effects/ADISCORD_minor_optimization_effects.txt`
- Update: `common/scripted_triggers/ADISCORD_minor_optimization_triggers.txt`
- Update: `common/on_actions/00_ADISCORD_minor_optimization_on_actions.txt`
- Update: `tools/validators/validate_adiscord_minor_optimization.py`
- Update: `tools/validators/validate_adiscord_economy_ai.py`
- Test: `tools/tests/test_adiscord_economy_weekly_contracts.py`

- [ ] Replace construction-policy AI decisions with research-policy decisions while preserving at most one policy action per AI tick and a political-power/story reserve.
- [ ] During deficit/crisis, allow AI to reduce research after tax and nonessential spending actions; during recovery/healthy states, return research toward 3 and allow 4 only with a real surplus.
- [ ] Add `ADISCORD_economy_ai_assistance_base` at +5% overall income/equivalent and +5% military-factory output, civil-war assistance at at most -10% supply consumption, and retreat assistance at +5% defense.
- [ ] Keep the three assistance ideas in the existing minor-optimization idea file, while economy effects own their cached economic inputs. Do not define a second copy in `ADISCORD_economy_ideas.txt`.
- [ ] Implement a cached-signature refresh using `is_ai`, simulation tier, the Vorkerland phase/country war state, and surrender progress >0.35; remove each assistance idea immediately when its condition ends.
- [ ] Replace periodic minor-optimization repair with initialization, war-start, war-end, and economy-tier hooks. The existing on_action may route bounded country-scoped events but may not scan the world monthly or rebuild the ideas weekly.
- [ ] Prohibit player application, attack bonuses, free technologies, equipment, cash, inflation immunity, capacity, or alternate debt rules.
- [ ] Verify existing claimant modifiers plus assistance do not exceed the intended assistance bounds during runtime.
- [ ] Run AI policy, minor-optimization, assistance, economy, and collapse integration tests.
- [ ] Commit as `feat(economy): add bounded reversible AI assistance`.

## Task 9: Rebuild the Policy Rows and Debt Modal

**Files:**
- Update: `interface/ADISCORD_economy.gui`
- Update: `common/scripted_guis/ADISCORD_economy_scripted_gui.txt`
- Update: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`
- Test: `tools/tests/test_validate_adiscord_gui_contracts.py`

- [ ] Replace the construction row with research and show rows in the order tax, military, research, social.
- [ ] Make the whole row a useful hover surface, make five levels hoverable, enlarge both arrow hitboxes, and retain exactly eight connected change actions.
- [ ] Show current level and short effect in the row; arrow tooltip shows next level, weekly delta, effect delta, cooldown, and exact disabled reason (boundary, cooldown, or unavailable country scope).
- [ ] Repurpose the obsolete auto-loan popup into the queued dynamic debt notification with cause/state/next-risk selectors.
- [ ] Remove visible diagnostic slogans including variants of 'money is calculated automatically' and clarify that policy changes take effect immediately while the three-month restriction is a cooldown.
- [ ] Run GUI node/action/size/scripted-loc resolution tests.
- [ ] Commit as `feat(economy-ui): expose policies and debt warnings`.

## Task 10: Write Bilingual Short and Delayed Tooltips

**Files:**
- Update: `localisation/russian/ADISCORD_economy_l_russian.yml`
- Update: `localisation/english/ADISCORD_economy_l_english.yml`
- Update: `common/scripted_localisation/ADISCORD_economy_scripted_loc.txt`
- Update: `docs/economy/economy-player-and-runtime.md`
- Update: `docs/economy/economic-modifiers.md`

- [ ] Give short tooltips one-screen answers: meaning, current value/change, and healthy/unhealthy status.
- [ ] Give delayed inflation tooltip current value, weekly change, sources, expense multiplier, gameplay effects, thresholds, and reduction methods.
- [ ] Give delayed debt tooltip principal, weekly interest, interest share, current tier, automatic borrowing behavior, tier streaks, default risk, and repayment consequences; omit debt capacity everywhere.
- [ ] Give treasury/balance tooltip cash, source breakdown, expense categories, weekly balance, recommended reserve, and deficit runway.
- [ ] Give each policy tooltip current/next effect and cost, cooldown, and blocker.
- [ ] Keep RU/EN key sets identical only for new/substantially rewritten recovery-owned economy content and preserve Russian BOM. Do not translate untouched legacy economy text in this project.
- [ ] Update player/runtime documentation for schema 12, exact thresholds, migration, and notification behavior.
- [ ] Run localisation uniqueness/key-resolution/BOM tests and GUI contracts.
- [ ] Commit as `docs(economy): explain schema 12 and debt states`.

## Task 11: Economy Static and Runtime Verification

- [ ] Run focused economy weekly, GUI, localisation, and AI tests.
- [ ] Run `python -B tools/validate_adiscord_economy_ai.py` through its compatibility facade.
- [ ] Run full unit discovery, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`.
- [ ] Fully restart HOI4 and test a fresh campaign plus a pre-schema-12 save.
- [ ] At 1366x768 and 1920x1080, verify four rows, row/arrow hitboxes, boundary/cooldown reasons, preview deltas, short and delayed tooltips, and modal layout.
- [ ] Verify weekly balance settles within seven days; research modes affect cost/speed and only level 5 gives +2% construction speed.
- [ ] Trigger first loan, 10%, 25%, four-week 40%, and thirteen-week negative-balance transitions; verify one notification per genuine transition and immediate downgrade after repayment.
- [ ] Verify AI assistance appears/removes under exact conditions while the AI still pays inflation/interest and can default.
- [ ] Inspect fresh `error.log`, `game.log`, and `system.log`; do not claim success from static tests or hot reload.
