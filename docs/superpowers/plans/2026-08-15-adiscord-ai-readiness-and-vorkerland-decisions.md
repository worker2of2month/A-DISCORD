# A-Discord AI Readiness and Vorkerland Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ordinary AI countries progress from emergency formations to reachable field divisions and make Vorkerland claimants spend political power on available wartime decisions.

**Architecture:** Keep the existing role-separated AI-template system, but insert a reachable six-battalion field baseline before support-heavy designs and place production floors before every stock-gated upgrade. Add one bounded claimant-only PP strategy; decisions continue to use their own availability and `ai_will_do`.

**Tech Stack:** HOI4 Clausewitz script, Python 3 `unittest`, existing A-Discord validators.

## Global Constraints

- Preserve unrelated dirty changes in `history/states`, theatre manifests, and urban-VP documents.
- Do not stage or commit; the repository rules require explicit user approval for commits.
- The four-battalion northern collapse levy may hold a front only during the bounded collapse phase, but no four-battalion design may be mobile or armored.
- Do not add periodic global polling or scripted forced decision completion.
- Static tests do not prove runtime behavior; final acceptance requires a fully restarted HOI4 process and a fresh campaign.
- Russian localisation is out of this sub-plan and must not be rewritten.

---

### Task 1: Lock the reachable infantry and production contract

**Files:**
- Modify: `tools/tests/test_validate_adiscord_force_designs.py`
- Modify: `tools/validators/validate_adiscord_tech_doctrine.py:2818`
- Test: `tools/tests/test_validate_adiscord_force_designs.py`

**Interfaces:**
- Consumes: `named_block(text: str, name: str) -> str` from the existing test helper.
- Produces: source-level contracts for `ADISCORD_reconstruction_brigade`, `ADISCORD_line_brigade`, support/artillery production floors, and `target_min_match`.

- [ ] **Step 1: Write the failing progression tests**

Add these methods to `VorkerlandForceDesignTests`:

```python
def test_generic_field_baseline_is_six_battalions_and_immediately_reachable(self) -> None:
    templates = read("common/ai_templates/ADISCORD_land_templates.txt")
    baseline = named_block(templates, "ADISCORD_reconstruction_brigade")
    target = named_block(baseline, "target_template")
    self.assertRegex(target, r"regiments\s*=\s*\{[^{}]*infantry\s*=\s*6")
    self.assertNotIn("num_of_military_factories", baseline)
    self.assertNotIn("has_equipment", named_block(baseline, "can_upgrade_in_field"))
    self.assertIn("target_min_match = 0.65", baseline)

def test_four_battalion_designs_are_bounded_emergency_formations(self) -> None:
    templates = read("common/ai_templates/ADISCORD_land_templates.txt")
    garrison = named_block(templates, "ADISCORD_garrison_levy")
    northern = named_block(templates, "ADISCORD_vorkerland_northern_line_militia")
    self.assertIn("ADISCORD_militia = 4", garrison)
    self.assertIn("ADISCORD_militia = 4", northern)
    self.assertIn("ADISCORD_vorkerland_collapse_wars_started", northern)
    self.assertIn("ADISCORD_vorkerland_collapse_finished", northern)
    self.assertNotRegex(garrison + northern, r"(?m)^\s*role\s*=\s*(?:mobile|armor)\s*$")

def test_support_and_artillery_floors_precede_supported_line_template(self) -> None:
    default_ai = read("common/ai_strategy/default.txt")
    support = named_block(default_ai, "ADISCORD_produce_support_equipment_low_stock")
    artillery = named_block(default_ai, "ADISCORD_produce_artillery_low_stock")
    self.assertIn("num_of_military_factories > 1", support)
    self.assertIn("num_of_military_factories > 2", artillery)
    self.assertIn("id = support_equipment value = 1", support)
    self.assertIn("id = artillery_equipment value = 1", artillery)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_force_designs.VorkerlandForceDesignTests.test_generic_field_baseline_is_six_battalions_and_immediately_reachable tools.tests.test_validate_adiscord_force_designs.VorkerlandForceDesignTests.test_four_battalion_designs_are_bounded_emergency_formations tools.tests.test_validate_adiscord_force_designs.VorkerlandForceDesignTests.test_support_and_artillery_floors_precede_supported_line_template
```

Expected: the baseline-count and artillery-floor tests fail against the current four-infantry baseline and missing default artillery block.

- [ ] **Step 3: Strengthen the validator contract**

Extend `check_ai_force_progression()` with exact fragments and structural counts:

```python
required_template_fragments.update({
    "reachable six-battalion field baseline": "ADISCORD_reconstruction_brigade",
    "gradual baseline matching": "target_min_match = 0.65",
})
default_strategy = strip_comments(read_text(ROOT / "common/ai_strategy/default.txt"))
for label, fragment in {
    "early support production floor": "ADISCORD_produce_support_equipment_low_stock",
    "early artillery production floor": "ADISCORD_produce_artillery_low_stock",
}.items():
    if fragment not in default_strategy:
        issues.append(f"AI strategies missing {label}")
```

- [ ] **Step 4: Run the validator and confirm it also fails before implementation**

Run: `python -B tools/validate_adiscord_tech_doctrine.py`

Expected: non-zero exit with the missing early-artillery or target-match contract.

- [ ] **Step 5: Record a no-commit checkpoint**

Run: `git status --short`

Expected: only the design/plan, Task 1 test/validator edits, and pre-existing unrelated paths are listed.

---

### Task 2: Implement reachable infantry progression and production floors

**Files:**
- Modify: `common/ai_templates/ADISCORD_land_templates.txt:51-116`
- Modify: `common/ai_strategy/default.txt:37-64`
- Test: `tools/tests/test_validate_adiscord_force_designs.py`

**Interfaces:**
- Consumes: Task 1 source contracts.
- Produces: six-battalion generic baseline; supported line upgrade; early support/artillery factory floors.

- [ ] **Step 1: Make the field baseline independently reachable**

Change `ADISCORD_reconstruction_brigade` to:

```hoi4
ADISCORD_reconstruction_brigade = {
    reinforce_prio = 1
    upgrade_prio = { base = 5 }
    can_upgrade_in_field = { always = yes }
    target_min_match = 0.65
    target_template = { regiments = { infantry = 6 } }
    replace_at_match = 0.95
    replace_with = ADISCORD_line_brigade
}
```

- [ ] **Step 2: Lower the supported-line gate without removing its material requirements**

Use `num_of_military_factories > 2`, support stock `> 150`, artillery stock `> 80`, and in-field gates `> 250`/`> 140`. Add `target_min_match = 0.75`. Keep six infantry plus engineer and support artillery; the later defensive design remains the seven-infantry/line-artillery destination.

- [ ] **Step 3: Put support production before the supported template**

Change the support block to enable at `num_of_military_factories > 1`, abort below two factories or above 700 support equipment, and retain one minimum factory.

- [ ] **Step 4: Add the early artillery production block**

Insert after the support block:

```hoi4
ADISCORD_produce_artillery_low_stock = {
    enable = {
        num_of_military_factories > 2
        has_equipment = { artillery_equipment < 180 }
    }
    abort = {
        OR = {
            num_of_military_factories < 3
            has_equipment = { artillery_equipment > 450 }
        }
    }
    ai_strategy = { type = equipment_production_min_factories_archetype id = artillery_equipment value = 1 }
}
```

- [ ] **Step 5: Run the focused suite and verify GREEN**

Run: `python -B -m unittest tools.tests.test_validate_adiscord_force_designs`

Expected: all force-design tests pass after updating any old assertions that intentionally encoded four-infantry generic baselines; collapse OOB assertions remain unchanged in this sub-plan.

- [ ] **Step 6: Run the technology/AI validator**

Run: `python -B tools/validate_adiscord_tech_doctrine.py`

Expected: `OK` with the existing technology/doctrine counts and the strengthened AI progression contract.

- [ ] **Step 7: Record a no-commit checkpoint**

Run: `git diff --check -- common/ai_templates/ADISCORD_land_templates.txt common/ai_strategy/default.txt tools/tests/test_validate_adiscord_force_designs.py tools/validators/validate_adiscord_tech_doctrine.py`

Expected: no output.

---

### Task 3: Add bounded claimant PP spending

**Files:**
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`
- Modify: `common/ai_strategy/default.txt:30-35`
- Modify: `common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt`
- Modify: `tools/validators/validate_adiscord_vorkerland_collapse.py`
- Test: `tools/tests/test_validate_adiscord_vorkerland_collapse.py`

**Interfaces:**
- Consumes: collapse flags `ADISCORD_vorkerland_collapse_wars_started` and `ADISCORD_vorkerland_collapse_finished`.
- Produces: `ADISCORD_vorkerland_claimant_decision_spending`, a war-bounded AI strategy block.

- [ ] **Step 1: Write the failing PP contract test**

Add to the collapse test class:

```python
def test_main_claimant_ai_has_bounded_wartime_decision_budget(self) -> None:
    default_ai = read("common/ai_strategy/default.txt")
    reserve = named_block(default_ai, "ADISCORD_default_pp_reserve")
    self.assertIn("pp_spend_amount id = decision value = 100", reserve)

    collapse_ai = read("common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt")
    spending = named_block(collapse_ai, "ADISCORD_vorkerland_claimant_decision_spending")
    for token in (
        "is_ai = yes",
        "tag = WKR",
        "tag = VAD",
        "tag = TVA",
        "has_war = yes",
        "has_global_flag = ADISCORD_vorkerland_collapse_wars_started",
        "NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }",
        "pp_spend_priority id = decision value = 100",
        "pp_spend_amount id = decision value = 125",
        "abort_when_not_enabled = yes",
    ):
        self.assertIn(token, spending)
    self.assertNotIn("complete_effect", spending)
    self.assertNotIn("country_event", spending)
```

- [ ] **Step 2: Run the focused test and verify RED**

Run: `python -B -m unittest tools.tests.test_validate_adiscord_vorkerland_collapse.VorkerlandCollapseTests.test_main_claimant_ai_has_bounded_wartime_decision_budget`

Expected: failure because the strategy block is absent and the default decision amount is 75.

- [ ] **Step 3: Restore the baseline decision budget**

Change only `ADISCORD_default_pp_reserve` decision amount from 75 to 100; keep the idea amount at 100.

- [ ] **Step 4: Add the claimant wartime strategy**

Append this independent block to `ADISCORD_vorkerland_collapse_ai.txt`:

```hoi4
ADISCORD_vorkerland_claimant_decision_spending = {
    enable = {
        is_ai = yes
        OR = { tag = WKR tag = VAD tag = TVA }
        has_war = yes
        has_global_flag = ADISCORD_vorkerland_collapse_wars_started
        NOT = { has_global_flag = ADISCORD_vorkerland_collapse_finished }
    }
    abort_when_not_enabled = yes
    ai_strategy = { type = pp_spend_priority id = decision value = 100 }
    ai_strategy = { type = pp_spend_amount id = decision value = 125 }
}
```

- [ ] **Step 5: Mirror the exact contract in the collapse validator**

Read the new block with the validator's existing `named_block()` helper and report one issue per missing token from the same tuple used by the unit test. Also reject `complete_effect` and `country_event` inside the strategy block.

- [ ] **Step 6: Run focused tests and validators**

Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_vorkerland_collapse.VorkerlandCollapseTests.test_main_claimant_ai_has_bounded_wartime_decision_budget
python -B tools/validate_adiscord_vorkerland_collapse.py
```

Expected: test passes and the validator reports zero new PP-contract issues.

- [ ] **Step 7: Record a no-commit checkpoint**

Run: `git diff --check -- common/ai_strategy/default.txt common/ai_strategy/ADISCORD_vorkerland_collapse_ai.txt tools/tests/test_validate_adiscord_vorkerland_collapse.py tools/validators/validate_adiscord_vorkerland_collapse.py`

Expected: no output.

---

### Task 4: Close the static gate for the first sub-plan

**Files:**
- Verify only: all files from Tasks 1-3

**Interfaces:**
- Consumes: reachable templates, production floors, and bounded PP strategy.
- Produces: a statically validated AI-readiness slice ready for later modern-equipment work and runtime smoke testing.

- [ ] **Step 1: Run both focused test modules**

Run:

```powershell
python -B -m unittest tools.tests.test_validate_adiscord_force_designs tools.tests.test_validate_adiscord_vorkerland_collapse
```

Expected: all tests pass; report the exact count instead of estimating it.

- [ ] **Step 2: Run focused validators**

Run:

```powershell
python -B tools/validate_adiscord_tech_doctrine.py
python -B tools/validate_adiscord_vorkerland_collapse.py
python -B tools/validate_adiscord_economy_ai.py
python -B tools/validators/validate_adiscord_division_templates.py
```

Expected: each command exits zero.

- [ ] **Step 3: Run the repository baseline**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
```

Expected: validation exits zero; `git diff --check` prints no errors. If unrelated dirty map work fails a broad check, rerun scoped checks and report the unrelated path separately rather than modifying it.

- [ ] **Step 4: Inspect fresh runtime prerequisites without claiming runtime success**

Run `Get-Process hoi4 -ErrorAction SilentlyContinue` and record whether the currently running process predates these changes. Do not restart or close the user's game. Runtime acceptance remains pending until the user starts a fresh process and campaign.

- [ ] **Step 5: Record final no-commit scope**

Run: `git status --short`

Expected: no staging; unrelated state/theatre changes remain untouched.
