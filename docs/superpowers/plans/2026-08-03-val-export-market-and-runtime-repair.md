# VAL Export Market and Runtime Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WRK, STP, NOD, IVN, WIT, and NAM seek ordinary market access from VAL and prefer VAL equipment, while removing the VAL tier-transition runtime failures without changing the tier bonuses.

**Architecture:** `common/ai_strategy/VAL.txt` owns six buyer strategies, six matching VAL acceptance strategies, and VAL's existing rifle reserve. The administration, industry, and army families use one authoritative numeric level variable each; reputation keeps its existing authoritative variable. Scripted effects render exactly one hidden idea by deterministic remove/add operations, and initialization migrates old saves from completed VAL focuses.

**Tech Stack:** HOI4 1.19 Clausewitz script, Arms Against Tyranny international-market AI strategies, Python `unittest` contract tests, existing A-Discord validators, fresh HOI4 runtime logs.

## Global Constraints

- Preserve the exact buyer set: `WRK`, `STP`, `NOD`, `IVN`, `WIT`, `NAM`.
- Use normal AI diplomacy. Do not add `give_market_access`, equipment grants, periodic market on-actions, buyer subsidies, focuses, decisions, GUI, or localisation.
- Deactivate both halves of each relationship while that buyer is at war with VAL.
- Preserve all modifiers in `common/ideas/ADISCORD_VAL_rework_ideas.txt`; that file should remain unchanged.
- Preserve upward-only administration/industry/army progression, bidirectional reputation, hidden technical ideas, and existing economy dirty refreshes.
- Treat the current fresh `error.log` as a clean baseline for VAL: it contains unrelated errors but no currently executed VAL transition failure. Runtime verification must explicitly execute every tier effect before judging the repair.
- Do not touch or stage unrelated dirty changes, including the user's modified `localisation/russian/ADISCORD_VAL_rework_l_russian.yml`.
- Before claiming completion, invoke `superpowers:verification-before-completion` and inspect fresh command output.

---

### Task 1: RED tests for the export relationship

**Files:**
- Create: `tools/test_val_export_market.py`
- Read only: `common/ai_strategy/VAL.txt`

**Interfaces:**
- Fixed constant: `BUYERS = ("WRK", "STP", "NOD", "IVN", "WIT", "NAM")`.
- Expected buyer blocks: `ADISCORD_VAL_export_buyer_<TAG>`.
- Expected acceptance blocks: `ADISCORD_VAL_export_accept_<TAG>`.
- Reuse a local brace-aware `named_blocks(text, key)` helper matching the validator's parser.

- [ ] **Step 1: Add the exact market contract tests**

Create `ValExportMarketTests` with these assertions:

```python
BUYERS = ("WRK", "STP", "NOD", "IVN", "WIT", "NAM")

for buyer in BUYERS:
    buyer_block = only_block(ai_text, f"ADISCORD_VAL_export_buyer_{buyer}")
    self.assertIn(f"original_tag = {buyer}", buyer_block)
    self.assertIn('has_dlc = "Arms Against Tyranny"', buyer_block)
    self.assertIn("country_exists = VAL", buyer_block)
    self.assertRegex(buyer_block, r"NOT\s*=\s*\{\s*has_war_with\s*=\s*VAL\s*\}")
    self.assertIn("abort_when_not_enabled = yes", buyer_block)
    self.assert_ai_strategy(
        buyer_block,
        type="diplo_action_desire",
        id="VAL",
        target="market_access_rights",
        value="150",
    )
    self.assert_ai_strategy(
        buyer_block,
        type="equipment_market_trade_desire",
        id="VAL",
        value="100",
    )
```

For every `ADISCORD_VAL_export_accept_<TAG>` block, assert `original_tag = VAL`, the DLC gate, `country_exists = <TAG>`, the matching wartime guard, `abort_when_not_enabled = yes`, and:

```text
type = diplo_action_acceptance
id = <TAG>
target = market_access_rights
value = 200
```

Also assert that the two prefix-derived tag sets equal `set(BUYERS)` exactly, that `VAL_Wants_To_Sell_Stuff` contains only `equipment_market_for_sale_factor` market behavior, and that no changed market layer contains `give_market_access` or a VAL market-maintenance on-action.

- [ ] **Step 2: Run the focused test and confirm RED**

Run:

```powershell
python -B -m unittest tools.test_val_export_market -v
```

Expected: failures because the twelve relationship blocks do not exist and VAL still requests access from IVN, WRK, and WIT.

---

### Task 2: Implement VAL as seller and the six countries as buyers

**Files:**
- Modify: `common/ai_strategy/VAL.txt`
- Verify: `tools/test_val_export_market.py`

- [ ] **Step 1: Retain VAL's sale reserve without reverse market requests**

Keep `VAL_Wants_To_Sell_Stuff`, add the AAT gate to `allowed`, preserve its current peace/economic-crisis enable conditions and infantry `equipment_market_for_sale_factor = 50`, and remove all three `diplo_action_desire` blocks that target IVN, WRK, and WIT.

- [ ] **Step 2: Add one self-removing buyer block per approved tag**

Use this exact structure for every buyer, substituting only `<TAG>`:

```hoi4
ADISCORD_VAL_export_buyer_<TAG> = {
	allowed = {
		original_tag = <TAG>
		has_dlc = "Arms Against Tyranny"
	}
	enable = {
		country_exists = VAL
		NOT = { has_war_with = VAL }
	}
	abort_when_not_enabled = yes

	ai_strategy = {
		type = diplo_action_desire
		id = VAL
		target = market_access_rights
		value = 150
	}
	ai_strategy = {
		type = equipment_market_trade_desire
		id = VAL
		value = 100
	}
}
```

- [ ] **Step 3: Add one self-removing VAL acceptance block per approved tag**

Use this exact structure for every buyer, substituting only `<TAG>`:

```hoi4
ADISCORD_VAL_export_accept_<TAG> = {
	allowed = {
		original_tag = VAL
		has_dlc = "Arms Against Tyranny"
	}
	enable = {
		country_exists = <TAG>
		NOT = { has_war_with = <TAG> }
	}
	abort_when_not_enabled = yes

	ai_strategy = {
		type = diplo_action_acceptance
		id = <TAG>
		target = market_access_rights
		value = 200
	}
}
```

- [ ] **Step 4: Run the market tests and confirm GREEN**

Run `python -B -m unittest tools.test_val_export_market -v`.

- [ ] **Step 5: Commit only the green market slice**

```powershell
git add -- common/ai_strategy/VAL.txt tools/test_val_export_market.py
git diff --cached --check
git commit -m "feat: make VAL the preferred arms exporter"
```

---

### Task 3: RED tests for engine-safe VAL tier transitions

**Files:**
- Create: `tools/test_validate_adiscord_val_rework.py`
- Read only: `common/scripted_effects/ADISCORD_VAL_rework_effects.txt`
- Read only: `common/ideas/ADISCORD_VAL_rework_ideas.txt`
- Read only: `common/national_focus/ADISCORD_national_focus_VAL.txt`

**Interfaces:**
- Authoritative variables: `VAL_contract_administration_level`, `VAL_contract_industry_level`, `VAL_contract_army_level`, and existing `VAL_contract_reputation_level`.
- Migration effect: `VAL_migrate_contract_tier_levels`.
- Existing public apply effects retain their names, so focus/event callers do not change.

- [ ] **Step 1: Prove every referenced tier ID is declared exactly once**

Build the four exact families in the test:

```python
FAMILIES = {
    "administration": tuple(f"VAL_contract_administration_{n}" for n in range(1, 4)),
    "industry": tuple(f"VAL_contract_industry_{n}" for n in range(1, 4)),
    "army": tuple(f"VAL_contract_army_{n}" for n in range(1, 4)),
    "reputation": tuple(f"VAL_contract_reputation_{n}" for n in range(4)),
}
```

Assert each ID has exactly one brace-aware definition inside `hidden_ideas` and every tier ID used by an apply effect belongs to this set.

- [ ] **Step 2: Lock deterministic rendering and directionality**

For administration, industry, and army apply effects, assert:

- no `has_idea` or `swap_ideas` appears;
- the matching authoritative variable is set to the target tier;
- all three family ideas are removed inside `hidden_effect`, then only the target is added;
- tier 1 and 2 effects contain an authoritative-level guard, preventing a lower call from replacing tier 2 or 3;
- administration and industry keep `ADISCORD_economy_mark_dirty = yes` inside the successful transition.

For reputation 0–3, assert every effect removes all four reputation ideas, adds only its target inside `hidden_effect`, contains neither `has_idea` nor `swap_ideas`, and remains selected by `VAL_refresh_contract_reputation`.

- [ ] **Step 3: Lock complete old-save migration coverage**

Parse every focus whose completion reward invokes one of the nine upward-only apply effects. Assert each caller focus ID occurs in the corresponding tier branch of `VAL_migrate_contract_tier_levels`, with tier 3 evaluated before tier 2 and tier 2 before tier 1. Assert `VAL_initialize_rework` invokes the migration effect.

- [ ] **Step 4: Run the focused test and confirm RED**

Run:

```powershell
python -B -m unittest tools.test_validate_adiscord_val_rework -v
```

Expected: the current transition code fails because it branches on `has_idea`, uses `swap_ideas`, has no authoritative level variables for three families, and has no old-save tier migration.

---

### Task 4: Replace the failing tier transition representation

**Files:**
- Modify: `common/scripted_effects/ADISCORD_VAL_rework_effects.txt`
- Modify: `tools/validate_adiscord_val_rework.py`
- Verify: `tools/test_validate_adiscord_val_rework.py`
- Do not modify: `common/ideas/ADISCORD_VAL_rework_ideas.txt`

- [ ] **Step 1: Replace administration, industry, and army transitions**

For each family, retain `VAL_apply_contract_<family>_1..3`. Use `NOT = { has_variable = <level_var> }` or `check_variable ... compare = less_than` as the only upgrade gate. On success, set the numeric level, then in `hidden_effect` remove all three family ideas and add the target idea. Keep the current dirty-state call for administration and industry only.

The tier-2 administration pattern is:

```hoi4
VAL_apply_contract_administration_2 = {
	if = {
		limit = {
			OR = {
				NOT = { has_variable = VAL_contract_administration_level }
				check_variable = {
					var = VAL_contract_administration_level
					value = 2
					compare = less_than
				}
			}
		}
		set_variable = { var = VAL_contract_administration_level value = 2 }
		hidden_effect = {
			remove_ideas = VAL_contract_administration_1
			remove_ideas = VAL_contract_administration_2
			remove_ideas = VAL_contract_administration_3
			add_ideas = VAL_contract_administration_2
			ADISCORD_economy_mark_dirty = yes
		}
	}
}
```

Apply the same literal structure to tiers 1 and 3 and to industry/army using their own variable and idea IDs. This makes lower calls no-ops after a higher tier and makes a successful transition idempotently exclusive.

- [ ] **Step 2: Replace reputation swaps with variable-driven deterministic rendering**

Keep `VAL_refresh_contract_reputation` unchanged as the selector. Each `VAL_apply_contract_reputation_0..3` must contain one hidden block that removes reputation 0, 1, 2, and 3 and then adds only the selected target. Do not add another reputation state variable.

- [ ] **Step 3: Add complete old-save migration before normal initialization**

Add `VAL_migrate_contract_tier_levels`, and for each missing level variable choose the highest completed caller tier:

| Family | Tier 3 caller focuses | Tier 2 caller focuses | Tier 1 caller focuses |
|---|---|---|---|
| Administration | `VAL_State_Contract` | `VAL_Central_Payment_Office`, `VAL_Provincial_Contract_Courts` | `VAL_The_Weaponry_Baron`, `VAL_Provincial_Brokers`, `VAL_Ministry_Auditors` |
| Industry | `VAL_Industrial_Mobilization_Plan` | `VAL_Standardize_Rifle_Lots`, `VAL_Standard_Cartridges`, `VAL_Three_Shift_Arsenals` | `VAL_Contract_Accounting_Office`, `VAL_Munitions_Board` |
| Army | `VAL_Contract_General_Staff`, `VAL_Army_Of_The_Ledger` | `VAL_Contractor_Officers`, `VAL_Motorized_Columns`, `VAL_Field_Repair_Corps`, `VAL_Contract_NCO_Schools`, `VAL_Logistics_Command` | `VAL_Count_The_Captains`, `VAL_The_Mercenary_State`, `VAL_Company_Rosters`, `VAL_Border_Survey_Corps`, `VAL_Company_Service_Code` |

Each branch calls the existing public apply effect for that tier, letting it initialize the variable and render the hidden idea. Invoke `VAL_migrate_contract_tier_levels = yes` at the start of `VAL_initialize_rework`.

- [ ] **Step 4: Update the existing validator from the disproved swap contract**

Remove requirements that tiers 2/3 and reputation use `swap_ideas`. Replace them with checks for:

- exact authoritative variable names;
- no `has_idea`/`swap_ideas` in any tier apply effect;
- exact remove-all/add-target hidden rendering;
- upward-only variable guards for administration/industry/army;
- all four bidirectional reputation renderers;
- complete migration focus coverage and initialization wiring;
- all thirteen tier idea IDs still declared under `hidden_ideas`.

- [ ] **Step 5: Run focused tests and VAL validator to GREEN**

```powershell
python -B -m unittest tools.test_validate_adiscord_val_rework -v
python -B tools/validate_adiscord_val_rework.py
```

- [ ] **Step 6: Commit only the green runtime-repair slice**

```powershell
git add -- common/scripted_effects/ADISCORD_VAL_rework_effects.txt tools/validate_adiscord_val_rework.py tools/test_validate_adiscord_val_rework.py
git diff --cached --check
git commit -m "fix: make VAL tier transitions runtime-safe"
```

---

### Task 5: Static regression and clean-scope verification

**Files:**
- Verify all files from Tasks 1–4.

- [ ] **Step 1: Run the focused suites**

```powershell
python -B -m unittest tools.test_val_export_market tools.test_validate_adiscord_val_rework -v
python -B tools/validate_adiscord_val_rework.py
python -B tools/validate_adiscord_stp_val_crisis.py
```

- [ ] **Step 2: Run adjacent and project-wide static gates**

```powershell
python -B -m unittest tools.test_validate_adiscord_stp_val_crisis -v
python -B tools/validate_tc.py --limit 300
git diff --check -- common/ai_strategy/VAL.txt common/scripted_effects/ADISCORD_VAL_rework_effects.txt tools/validate_adiscord_val_rework.py tools/test_val_export_market.py tools/test_validate_adiscord_val_rework.py
```

If `validate_tc.py` or the broad STP/VAL suite reports pre-existing failures from dirty unrelated files, record them separately and prove the focused clean-index/scoped tests remain green; do not repair them in this change.

- [ ] **Step 3: Inspect only the intended patch**

```powershell
git status --short -- common/ai_strategy/VAL.txt common/scripted_effects/ADISCORD_VAL_rework_effects.txt common/ideas/ADISCORD_VAL_rework_ideas.txt localisation/russian/ADISCORD_VAL_rework_l_russian.yml tools/validate_adiscord_val_rework.py tools/test_val_export_market.py tools/test_validate_adiscord_val_rework.py
git diff -- common/ai_strategy/VAL.txt common/scripted_effects/ADISCORD_VAL_rework_effects.txt tools/validate_adiscord_val_rework.py tools/test_val_export_market.py tools/test_validate_adiscord_val_rework.py
```

Confirm the ideas and Russian localisation files have no task-owned diff and are not staged.

---

### Task 6: Fresh HOI4 runtime gate

**Files:**
- Runtime verify: `common/ai_strategy/VAL.txt`
- Runtime verify: `common/scripted_effects/ADISCORD_VAL_rework_effects.txt`
- Runtime verify: `common/ideas/ADISCORD_VAL_rework_ideas.txt`
- Inspect external log: `%USERPROFILE%\Documents\Paradox Interactive\Hearts of Iron IV\logs\error.log`

- [ ] **Step 1: Establish a genuinely fresh process and log boundary**

Exit every HOI4 process, record the current log timestamp, launch HOI4 with A-Discord and Arms Against Tyranny, and start a new game as VAL. Do not use a log that predates the tested build.

- [ ] **Step 2: Exercise all transition families in VAL scope**

Through the developer console, execute in order:

```text
effect VAL_initialize_rework = yes
effect VAL_apply_contract_administration_1 = yes
effect VAL_apply_contract_administration_2 = yes
effect VAL_apply_contract_administration_3 = yes
effect VAL_apply_contract_administration_1 = yes
effect VAL_apply_contract_industry_1 = yes
effect VAL_apply_contract_industry_2 = yes
effect VAL_apply_contract_industry_3 = yes
effect VAL_apply_contract_industry_1 = yes
effect VAL_apply_contract_army_1 = yes
effect VAL_apply_contract_army_2 = yes
effect VAL_apply_contract_army_3 = yes
effect VAL_apply_contract_army_1 = yes
```

Use the existing VAL debug reputation minimum and maximum controls, then minimum again. Verify the lower administration/industry/army calls do not replace tier 3, while reputation can move both directions.

- [ ] **Step 3: Exercise one ordinary market relationship**

Let the AI run from a fresh start long enough to load strategies. As one approved buyer, request VAL market access through the diplomacy UI and verify VAL accepts normally; inspect the international market with a controlled equipment shortage to confirm VAL remains an eligible/preferred seller. Start or simulate a war between the pair only in a disposable test and confirm the strategy relationship deactivates.

- [ ] **Step 4: Inspect the new log by source path**

```powershell
$log = "$env:USERPROFILE\Documents\Paradox Interactive\Hearts of Iron IV\logs\error.log"
rg -n "common/(ai_strategy/VAL.txt|scripted_effects/ADISCORD_VAL_rework_effects.txt|ideas/ADISCORD_VAL_rework_ideas.txt|national_focus/ADISCORD_national_focus_VAL.txt)" $log
```

Expected: no matches after all transition and market paths were exercised. Report unrelated paths separately; do not claim that this task fixed them.

- [ ] **Step 5: Final scoped status**

Confirm both scoped commits contain only the five intended production/test/validator paths, or squash them only if explicitly requested. Do not stage the user's localisation or any unrelated dirty file.
