# WRK Fresh-Campaign Civil-War Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the WRK/Vorkerland civil war progress from verified gameplay state, eliminate the confirmed runtime and interface errors, and leave one verified final commit containing every task-owned change.

**Architecture:** Keep the existing phase flags and bounded event graph as the sole campaign controller. Replace the global monthly war clock with transition-driven legitimacy, control, coalition, theatre, and recovery effects; retain only tag-specific monthly factory scaling. Restore vanilla interface inheritance and guarantee every late division template immediately before its unit spawn.

**Tech Stack:** Hearts of Iron IV Clausewitz script, GUI/GFX definitions, Python 3 validators and `unittest`/`pytest`, PowerShell, Git.

**Spec:** `docs/superpowers/specs/2026-08-22-wrk-civil-war-hardening-design.md`

## Global Constraints

- Fresh campaigns only; do not add old-save migration or recurring repair.
- Preserve claimant identities, borders, focus rewards, regional wars, central outcomes, and reunification results.
- The phase flags are the only campaign progression state; do not add replacement 6-, 18-, or 30-month events.
- Preserve unrelated dirty work and current custom additions in `interface/goals_shine.gfx`.
- Russian localisation touched by the work must retain UTF-8 BOM.
- Generated output remains owned by its builder; update source and regenerate rather than hand-editing generated output.
- The user requested one final implementation commit, so tasks end with verified working-tree checkpoints rather than intermediate commits.
- Suggested delegation: Luna Medium handles Tasks 1 and 6; Sol Medium handles Task 2. The primary agent owns the scope-sensitive and integration tasks.

---

### Task 1: Split focus-decision sources without changing behavior

**Suggested owner:** Luna Medium

**Files:**
- Create: `common/decisions/ADISCORD_vorkerland_focus_operations_decisions.txt`
- Create: `common/decisions/ADISCORD_vorkerland_allied_support_decisions.txt`
- Delete: `common/decisions/ADISCORD_vorkerland_focus_decisions.txt`
- Modify: `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py:34-36,2880-2920`
- Modify: `tools/validators/validate_adiscord_vorkerland_collapse.py:808-865,3635-3668`
- Modify: `tools/validators/validate_adiscord_vorkerland_diplomacy.py:23-50`
- Modify: `tools/validators/validate_adiscord_vorkerland_focus_decisions.py:16-35`
- Modify: `tools/validators/validate_adiscord_vorkerland_recovery.py:23-35`
- Modify: `tools/tests/test_adiscord_vorkerland_showdown_recovery.py:70-90`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py:320-390,1180-1210`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_focus_decisions.py:1-40`

**Interfaces:**
- Consumes: the two existing top-level categories at lines 1 and 765 of `ADISCORD_vorkerland_focus_decisions.txt`.
- Produces: `FOCUS_DECISION_FILES`, a tuple containing the operations file first and allied-support file second; validators concatenate the two sources with one newline.

- [ ] **Step 1: Add a failing split-source test**

Add this contract to `test_validate_adiscord_vorkerland_focus_decisions.py`:

```python
def test_focus_decision_categories_have_separate_owner_files(self) -> None:
    operations = ROOT / "common/decisions/ADISCORD_vorkerland_focus_operations_decisions.txt"
    support = ROOT / "common/decisions/ADISCORD_vorkerland_allied_support_decisions.txt"
    legacy = ROOT / "common/decisions/ADISCORD_vorkerland_focus_decisions.txt"
    self.assertTrue(operations.is_file())
    self.assertTrue(support.is_file())
    self.assertFalse(legacy.exists())
    operations_source = operations.read_text(encoding="utf-8-sig")
    support_source = support.read_text(encoding="utf-8-sig")
    self.assertEqual(operations_source.count("ADISCORD_vorkerland_focus_operations_category = {"), 1)
    self.assertEqual(support_source.count("ADISCORD_vorkerland_allied_support_category = {"), 1)
```

- [ ] **Step 2: Run the test and verify the expected failure**

Run:

```powershell
python -B -m pytest tools/tests/test_validate_adiscord_vorkerland_focus_decisions.py -q
```

Expected: FAIL because the two new decision files do not exist and the legacy file still exists.

- [ ] **Step 3: Split the file at the existing category boundary**

Move the complete `ADISCORD_vorkerland_focus_operations_category` block into the operations file and the complete `ADISCORD_vorkerland_allied_support_category` block into the support file. Preserve bytes inside each block; do not reformat decisions or alter localisation keys.

- [ ] **Step 4: Teach every validator to read both sources**

Use this module-local shape in each affected validator:

```python
FOCUS_DECISION_FILES = (
    Path("common/decisions/ADISCORD_vorkerland_focus_operations_decisions.txt"),
    Path("common/decisions/ADISCORD_vorkerland_allied_support_decisions.txt"),
)

focus_decisions = "\n".join(read(path) for path in FOCUS_DECISION_FILES)
```

Where the validator's `read` helper also accepts `root` and `issues`, retain that signature for each tuple member. Update direct test reads to concatenate the same two files. Do not add a compatibility stub at the deleted legacy path.

- [ ] **Step 5: Run focused validators and tests**

Run:

```powershell
python -B -m pytest tools/tests/test_validate_adiscord_vorkerland_focus_decisions.py tools/tests/test_adiscord_vorkerland_showdown_recovery.py tools/tests/test_validate_adiscord_vorkerland_collapse.py -q
python -B tools/validate_adiscord_vorkerland_focus_decisions.py
python -B tools/validate_adiscord_vorkerland_diplomacy.py
```

Expected: PASS; both decision categories are found exactly once.

- [ ] **Step 6: Record a working-tree checkpoint**

Run `git diff --check -- common/decisions tools/validators tools/tests` and report the exact changed paths to the primary agent. Do not commit.

---

### Task 2: Repair focus definition order and replace the calendar gate

**Suggested owner:** Sol Medium

**Files:**
- Modify: `common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt:1-100,7800-10000`
- Modify: `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py:873-885,2080-2100,2880-2945,4000-4050,5498-5550`
- Modify: `tools/tests/test_adiscord_vorkerland_civil_war_focus.py:850-910,2087-2125`

**Interfaces:**
- Consumes: existing focus IDs, coordinates, prerequisites, and `SHOWDOWN_PHASE`.
- Produces: `_check_focus_reference_order(source, blocks)` and central-showdown-only availability for all `DEPTH_LATE_WAR_FOCUSES`.

- [ ] **Step 1: Add failing order and phase tests**

Add tests with these assertions:

```python
def test_every_relative_anchor_is_defined_before_its_consumer(self) -> None:
    offsets = {
        match.group(1): match.start()
        for match in re.finditer(
            r"(?ms)^\s*focus\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_]+)",
            self.focus,
        )
    }
    for focus_id, block in self.blocks.items():
        anchor = _relative_anchor(block)
        if anchor is not None:
            self.assertIn(anchor, offsets)
            self.assertLess(offsets[anchor], offsets[focus_id], (focus_id, anchor))

def test_late_war_depth_branches_wait_for_central_showdown(self) -> None:
    self.assertNotIn("ADISCORD_vorkerland_war_month", self.focus)
    for focus_id in DEPTH_LATE_WAR_FOCUSES:
        available = _blocks(self.blocks[focus_id], "available")[0]
        self.assertEqual(_phase_flags(available), {SHOWDOWN_PHASE})
```

- [ ] **Step 2: Verify the tests fail for the four forward anchors and war clock**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_civil_war_focus.py -q
```

Expected: FAIL naming the four known forward relationships and the existing `war_month` token.

- [ ] **Step 3: Reorder the four complete focus blocks**

Move each anchor block before its consumer without changing block contents:

```text
WKR_train_shopfloor_officers        before WKR_authorize_retreat_levies
VAD_inventory_eastern_works         before VAD_standardize_district_logistics
TVA_select_trial_protocol           before TVA_raise_technical_battalions
TVA_integrate_field_results         before TVA_seal_the_approaches
```

- [ ] **Step 4: Replace late-focus availability**

For each focus in `DEPTH_LATE_WAR_FOCUSES`, remove the `check_variable` war-clock condition and make its `available` phase set exactly:

```hoi4
available = {
    has_global_flag = ADISCORD_vorkerland_phase_central_showdown
}
```

Retain the existing `allow_branch` phase set so branches remain visible before availability. Introduce `LATE_WAR_AVAILABLE_PHASE_FLAGS = {SHOWDOWN_PHASE}` rather than reusing a visibility constant.

- [ ] **Step 5: Add validator order enforcement**

Implement `_check_focus_reference_order(source, blocks)` using source offsets. It must report both a missing anchor and `consumer references anchor before its definition`. Call it from `collect_issues()` before layout resolution.

- [ ] **Step 6: Run focused verification**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_civil_war_focus.py -q
python -B tools/validate_adiscord_vorkerland_civil_war_focus.py
```

Expected: PASS with unchanged resolved coordinates and no `war_month` reference in the focus source.

- [ ] **Step 7: Record a working-tree checkpoint**

Run `git diff --check -- common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt tools/validators/validate_adiscord_vorkerland_civil_war_focus.py tools/tests/test_adiscord_vorkerland_civil_war_focus.py`. Do not commit.

---

### Task 3: Consolidate claimant and premature-release interfaces

**Owner:** Primary agent

**Files:**
- Modify: `common/scripted_triggers/ADISCORD_vorkerland_collapse_triggers.txt:90-125`
- Modify: `common/scripted_triggers/ADISCORD_vorkerland_stalemate_triggers.txt:1-25`
- Create: `common/scripted_effects/ADISCORD_vorkerland_release_effects.txt`
- Modify: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt:220-430`
- Modify: `common/on_actions/05_ADISCORD_vorkerland_stalemate_on_actions.txt:1-20`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_stalemate_effects.txt:1-50`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_story_effects.txt:430-455`
- Modify: `common/scripted_effects/ZZ_ADISCORD_capitulation_distribution_effects.txt:20-45`
- Modify: `tools/validators/validate_adiscord_vorkerland_collapse.py:632-700,1640-1670,3640-3710`
- Modify: `tools/validators/validate_adiscord_vorkerland_recovery.py:1714-1885`
- Modify: `tools/validators/validate_adiscord_vorkerland_stalemate.py:170-205`
- Modify: `tools/tests/test_adiscord_vorkerland_recovery.py:490-610`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py:920-950,1150-1180,2930-3010`

**Interfaces:**
- Consumes: `ADISCORD_vorkerland_is_main_claimant` and existing premature-WRK routing effects.
- Produces: `ADISCORD_vorkerland_release_requires_interception` trigger and `ADISCORD_vorkerland_intercept_premature_wrk_release` effect.

- [ ] **Step 1: Add failing consolidation tests**

Assert that `ADISCORD_vorkerland_is_central_claimant` is absent repository-wide under `common`, every former consumer uses `ADISCORD_vorkerland_is_main_claimant`, and each release hook contains exactly one call to the shared interception effect.

```python
for hook_name in ("on_puppet", "on_release_as_puppet", "on_release_as_free"):
    hook = named_block(on_actions, hook_name)
    self.assertEqual(hook.count("ADISCORD_vorkerland_intercept_premature_wrk_release = yes"), 1)
    self.assertIn("ADISCORD_vorkerland_release_requires_interception = yes", hook)
```

- [ ] **Step 2: Run tests and verify the duplication failure**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_recovery.py tools/tests/test_validate_adiscord_vorkerland_collapse.py -q
```

Expected: FAIL because the alias and three copied bodies still exist.

- [ ] **Step 3: Remove the duplicate claimant trigger**

Replace every use of `ADISCORD_vorkerland_is_central_claimant = yes` with `ADISCORD_vorkerland_is_main_claimant = yes`, then delete the duplicate definition from `ADISCORD_vorkerland_stalemate_triggers.txt`. Update validators to require exactly one canonical main-claimant definition.

- [ ] **Step 4: Add the release trigger and effect**

Add this trigger to the collapse trigger owner:

```hoi4
ADISCORD_vorkerland_release_requires_interception = {
    OR = {
        ADISCORD_vorkerland_is_premature_wrk = yes
        AND = {
            NOT = { has_global_flag = ADISCORD_vorkerland_premature_wrk_subject_cleanup_active }
            FROM = { ADISCORD_vorkerland_is_premature_wrk = yes }
        }
    }
}
```

Implement `ADISCORD_vorkerland_intercept_premature_wrk_release` with the exact shared behavior now present at lines 313-338, 358-383, and 395-420: when the current country is premature WRK, set `ADISCORD_vorkerland_premature_wrk_release_intercepted_v1`, dissolve it through `FROM` when `FROM` is a living independent main claimant, and otherwise call `ADISCORD_vorkerland_route_premature_wrk_release_to_living_claimant` in the current scope; when only `FROM` is premature WRK and subject cleanup is inactive, set the same flag and call the same routing effect in the current scope.

- [ ] **Step 5: Reduce each hook to shared interception plus its original normal branch**

Use this shape:

```hoi4
if = {
    limit = { ADISCORD_vorkerland_release_requires_interception = yes }
    ADISCORD_vorkerland_intercept_premature_wrk_release = yes
}
else = {
    ADISCORD_vorkerland_sync_republics_from_ruins = yes
    if = {
        limit = { OR = { tag = ROM tag = TRU tag = ZAO tag = SOL } }
        ADISCORD_vorkerland_sync_independence_cosmetic = yes
    }
}
```

The code block above is the `on_release_as_puppet` normal branch. Keep `on_puppet`'s two VLA auxiliary branches between `sync_republics_from_ruins` and the independence-cosmetic branch. Keep `on_release_as_free`'s normal branch limited to the independence-cosmetic branch and do not add `sync_republics_from_ruins` there.

- [ ] **Step 6: Run recovery, collapse, stalemate, and party-identity tests**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_recovery.py tools/tests/test_validate_adiscord_vorkerland_collapse.py tools/tests/test_validate_adiscord_vorkerland_stalemate.py tools/tests/test_adiscord_party_texticons.py -q
python -B tools/validate_adiscord_vorkerland_recovery.py
python -B tools/validate_adiscord_vorkerland_stalemate.py
```

Expected: PASS with all `ROOT`/`FROM` contracts preserved.

- [ ] **Step 7: Record a working-tree checkpoint**

Run `git diff --check` on the files listed in this task and inspect the three hook diffs side by side. Do not commit.

---

### Task 4: Replace the war clock with transition-driven campaign state

**Owner:** Primary agent

**Files:**
- Create: `common/scripted_effects/ADISCORD_vorkerland_campaign_state_effects.txt`
- Create: `common/scripted_effects/ADISCORD_vorkerland_war_economy_effects.txt`
- Create: `common/scripted_effects/ADISCORD_vorkerland_doctrine_effects.txt`
- Delete: `common/scripted_effects/ADISCORD_vorkerland_focus_dynamic_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt:1-525,1385-1400,1950-1990`
- Modify: `common/scripted_triggers/ADISCORD_vorkerland_phase_triggers.txt:150-205`
- Modify: `common/on_actions/01_ADISCORD_vorkerland_collapse_on_actions.txt:1-100,429-520`
- Modify: `events/ADISCORD_vorkerland_collapse_events.txt:159-211`
- Modify: `common/national_focus/ADISCORD_vorkerland_civil_war_focus.txt:2280-2480,3890-4090,6010-6210`
- Modify: `common/dynamic_modifiers/ADISCORD_vorkerland_collapse_dynamic_modifiers.txt:90-190`
- Create: `tools/tests/test_vorkerland_campaign_state.py`
- Modify: `tools/tests/test_adiscord_vorkerland_civil_war_focus.py:2198-2310`
- Modify: `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py:5781-5894`
- Modify: `tools/validators/validate_adiscord_vorkerland_recovery.py:991-1197`

**Interfaces:**
- Produces: `ADISCORD_vorkerland_refresh_war_economy_dynamic_state`, `ADISCORD_vorkerland_refresh_doctrine_dynamic_state`, `ADISCORD_vorkerland_refresh_legitimacy_leader`, `ADISCORD_vorkerland_refresh_claimant_coalition`, and `ADISCORD_vorkerland_reconcile_campaign_state`.
- Consumes: existing legitimacy variables, `ADISCORD_vorkerland_central_control_score`, phase flags, three coalition ideas, and the 17 explicit central states.

- [ ] **Step 1: Add failing architecture tests**

Create `test_vorkerland_campaign_state.py` with helpers that read named Clausewitz blocks. Assert:

```python
def test_calendar_controller_is_absent(self) -> None:
    combined = self.phase_effects + self.phase_triggers + self.on_actions + self.focus
    for token in (
        "ADISCORD_vorkerland_war_month",
        "ADISCORD_vorkerland_is_war_clock_owner",
        "ADISCORD_vorkerland_advance_war_clock",
        "ADISCORD_vorkerland_live_claimants",
    ):
        self.assertNotIn(token, combined)
    self.assertNotIn("on_monthly = {", self.on_actions)

def test_only_factory_scaling_remains_monthly(self) -> None:
    for tag in ("WKR", "VAD", "TVA"):
        hook = named_block(self.on_actions, f"on_monthly_{tag}")
        self.assertEqual(hook.count("ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes"), 1)
        self.assertNotIn("every_country", hook)
        self.assertNotIn("every_state", hook)
```

Also assert stable-incumbent branches appear before fallback selection, coalition requires `ADISCORD_vorkerland_central_control_score > 8`, `collapse.2` calls one-shot attrition and reconciliation, and central state changes trigger a three-claimant coalition refresh.

- [ ] **Step 2: Run the new test and verify the old clock fails it**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_campaign_state.py -q
```

Expected: FAIL on the clock tokens, general monthly hook, missing split effect files, and missing majority condition.

- [ ] **Step 3: Split dynamic effects by dependency**

Rename the current `ADISCORD_vorkerland_refresh_focus_dynamic_state` block to `ADISCORD_vorkerland_refresh_war_economy_dynamic_state` and end it immediately after `ADISCORD_vorkerland_war_economy_scale_display` is multiplied by 100. This moves the factory baseline, scale, stance, WKR/VAD/TVA output, and display statements from the first `set_variable = { var = ADISCORD_vorkerland_factory_count value = num_of_factories }` through `multiply_variable = { ADISCORD_vorkerland_war_economy_scale_display = 100 }` without changing arithmetic or flags.

Create `ADISCORD_vorkerland_refresh_doctrine_dynamic_state` from the doctrine statements that begin by zeroing `ADISCORD_vorkerland_doctrine_attack`, `ADISCORD_vorkerland_doctrine_defence`, `ADISCORD_vorkerland_doctrine_org`, `ADISCORD_vorkerland_doctrine_manpower`, `ADISCORD_vorkerland_doctrine_stability`, and `ADISCORD_vorkerland_doctrine_breakthrough`, then calculate `ADISCORD_vorkerland_doctrine_scale`, evaluate the six variant flags, and end with `ADISCORD_vorkerland_apply_focus_doctrine = yes`. Move `ADISCORD_vorkerland_apply_focus_doctrine` itself unchanged into the doctrine file.

Replace the six variant-root calls to `ADISCORD_vorkerland_refresh_focus_dynamic_state` with the doctrine effect. Add an immediate war-economy refresh to each war-economy fork completion so the player does not wait for the next monthly pulse.

- [ ] **Step 4: Move campaign-state effects out of the phase file**

Move legitimacy initialization/derivation, iconic-objective resolution, organized defence, leader selection, central-control recount, theatre priority, and coalition handling into `ADISCORD_vorkerland_campaign_state_effects.txt`. Retain phase setters, graph launch, recovery, and terminal settlement in the phase file.

- [ ] **Step 5: Implement stable incumbent leadership**

Check incumbents before fallback priority. For each incumbent tag, keep its flag when it is live and neither rival has strictly greater legitimacy; clear the other two flags in that branch. Only if no incumbent qualifies, select the highest live claimant with deterministic WKR/VAD/TVA fallback ordering.

- [ ] **Step 6: Implement majority-based coalition refresh**

`ADISCORD_vorkerland_refresh_claimant_coalition` runs in claimant scope. It first removes all three coalition ideas, then adds exactly one when the central showdown is active, the recipient is a living AI claimant at war, and the flagged leader's `ADISCORD_vorkerland_central_control_score` is greater than 8. Never add an idea targeting the recipient itself.

`ADISCORD_vorkerland_reconcile_campaign_state` explicitly recounts WKR, VAD, and TVA when they exist, refreshes the leader, then refreshes coalition and theatre state for all three.

- [ ] **Step 7: Route transitions and remove the clock**

Delete the general `on_monthly`, clock effect, clock trigger, and dead live-claimant writes. Add tag hooks:

```hoi4
on_monthly_WKR = { effect = { if = { limit = { ADISCORD_vorkerland_is_live_claimant = yes } ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes } } }
on_monthly_VAD = { effect = { if = { limit = { ADISCORD_vorkerland_is_live_claimant = yes } ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes } } }
on_monthly_TVA = { effect = { if = { limit = { ADISCORD_vorkerland_is_live_claimant = yes } ADISCORD_vorkerland_refresh_war_economy_dynamic_state = yes } } }
```

After `collapse.2` sets `ADISCORD_vorkerland_collapse_wars_started`, call `ADISCORD_vorkerland_apply_central_attrition = yes` once and `ADISCORD_vorkerland_reconcile_campaign_state = yes`. Make `ADISCORD_vorkerland_add_legitimacy` call `ADISCORD_vorkerland_refresh_doctrine_dynamic_state = yes`, `ADISCORD_vorkerland_refresh_legitimacy_leader = yes`, then refresh coalition state for WKR, VAD, and TVA when each tag exists. After control changes in one of the 17 central states, recount the losing and gaining claimant scopes and refresh coalition state for WKR, VAD, and TVA when each tag exists. Call the same full reconciliation from the central-showdown phase setter and the terminal-settlement effect.

- [ ] **Step 8: Update validators and existing dynamic tests**

Replace old generic-effect expectations with the two produced effect IDs. Assert doctrine has no monthly caller, monthly hooks contain no world scan, and every branch flag is still read exactly once by its owning effect.

- [ ] **Step 9: Run focused tests and validators**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_campaign_state.py tools/tests/test_adiscord_vorkerland_civil_war_focus.py tools/tests/test_adiscord_vorkerland_recovery.py tools/tests/test_vorkerland_war_exhaustion.py -q
python -B tools/validate_adiscord_vorkerland_civil_war_focus.py
python -B tools/validate_adiscord_vorkerland_recovery.py
```

Expected: PASS; `rg -n "war_month|war_clock|live_claimants" common events tools/tests tools/validators` returns no active WRK contract.

- [ ] **Step 10: Record a working-tree checkpoint**

Run `git diff --check` on all Task 4 paths and inspect the exact on-action scopes. Do not commit.

---

### Task 5: Make terminal regional failure advance through a bounded degraded path

**Owner:** Primary agent

**Files:**
- Modify: `common/scripted_effects/ADISCORD_vorkerland_phase_effects.txt:1000-1076`
- Read/verify: `events/ADISCORD_vorkerland_phase_events.txt:73-81`
- Modify: `tools/validators/validate_adiscord_vorkerland_recovery.py:1205-1575`
- Modify: `tools/tests/test_adiscord_vorkerland_recovery.py:467-472`
- Modify: `tools/tests/test_adiscord_vorkerland_showdown_recovery.py:26-75`

**Interfaces:**
- Consumes: existing `ADISCORD_vorkerland_phase.3` verifier event and `ADISCORD_vorkerland_begin_central_preparation`.
- Produces: `ADISCORD_vorkerland_degrade_regional_launch`, permanent flag `ADISCORD_vorkerland_regional_war_launch_degraded`, and no new event ID.

- [ ] **Step 1: Add a failing degraded-recovery test**

Assert both terminal failure branches call one common effect, that the common effect sets the degraded flag and schedules `ADISCORD_vorkerland_phase.3` after one day, and that the phase.3 verification path clears the transient failed latch before beginning central preparation.

- [ ] **Step 2: Verify the test fails on the current unscheduled latch**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_recovery.py tools/tests/test_adiscord_vorkerland_showdown_recovery.py -q
```

Expected: FAIL because final regional failure currently only sets a flag and logs.

- [ ] **Step 3: Add one common degraded effect**

Implement:

```hoi4
ADISCORD_vorkerland_degrade_regional_launch = {
    clr_global_flag = ADISCORD_vorkerland_regional_war_launch_final_retry
    clr_global_flag = ADISCORD_vorkerland_regional_war_launch_scheduled
    set_global_flag = ADISCORD_vorkerland_regional_war_launch_failed
    set_global_flag = ADISCORD_vorkerland_regional_war_launch_degraded
    log = "[ADISCORD][VORKERLAND][RECOVERY] Regional war graph failed bounded verification; central preparation queued."
    WKR = { country_event = { id = ADISCORD_vorkerland_phase.3 days = 1 } }
}
```

Use it from both final-failure sites. Do not create or register a new event ID.

- [ ] **Step 4: Teach the phase.3 verifier to release the transient latch**

Before ordinary consolidation verification, handle active degraded failure:

Make the first branch of `ADISCORD_vorkerland_verify_regional_consolidation` require `ADISCORD_vorkerland_regional_war_launch_failed`, the regional-consolidation phase, and an unfinished collapse. That branch clears the failed latch, sets `ADISCORD_vorkerland_northern_wars_began`, calls `ADISCORD_vorkerland_schedule_northern_escalation = yes`, and calls `ADISCORD_vorkerland_begin_central_preparation = yes`.

Convert the current success branch to the next `else_if` without changing its verified flag or central-preparation calls. Keep the following retry branch limited by `ADISCORD_vorkerland_regional_war_launch_scheduled`, absence of northern wars, and absence of the final-retry flag; it still sets the final-retry flag and schedules `ADISCORD_vorkerland_collapse.63` after one day. Replace the last branch, which requires the final-retry flag and absence of northern wars, with `ADISCORD_vorkerland_degrade_regional_launch = yes`. The permanent degraded flag remains for diagnostics.

- [ ] **Step 5: Run recovery verification**

Run:

```powershell
python -B -m pytest tools/tests/test_adiscord_vorkerland_recovery.py tools/tests/test_adiscord_vorkerland_showdown_recovery.py -q
python -B tools/validate_adiscord_vorkerland_recovery.py
```

Expected: PASS; no retry or recovery path is recurring.

- [ ] **Step 6: Record a working-tree checkpoint**

Run `git diff --check` on the four implementation/test files. Do not commit.

---

### Task 6: Guarantee every late-spawn division template

**Suggested owner:** Luna Medium after Task 1

**Files:**
- Create: `common/scripted_effects/ADISCORD_vorkerland_emergency_template_effects.txt`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt:70-205,430-505`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_focus_decision_effects.txt:230-375`
- Modify: `common/scripted_effects/ADISCORD_vorkerland_rom_tru_effects.txt:40-85`
- Modify: `common/decisions/ADISCORD_vorkerland_collapse_decisions.txt:330-470`
- Create: `tools/tests/test_vorkerland_emergency_templates.py`
- Modify: `tools/validators/validate_adiscord_vorkerland_collapse.py:2380-2435,2890-3050`
- Modify: `tools/tests/test_validate_adiscord_vorkerland_collapse.py:700-840,2170-2210`

**Interfaces:**
- Produces same-scope `ADISCORD_vorkerland_ensure_*_template` effects for the exact literal templates used by late Vorkerland `create_unit` calls.
- Template sources: existing inline blocks in `ADISCORD_vorkerland_collapse_effects.txt`; `history/units/WRK.txt`, `VAD.txt`, `TVA_vorkerland_collapse.txt`, `WPS_vorkerland_collapse.txt`, `TGD_vorkerland_collapse.txt`, and `ROM.txt`.

- [ ] **Step 1: Add a failing callsite-coverage test**

Create a mapping from each late-spawn file/effect or decision to its required ensure call. Cover these literal templates:

```python
REQUIRED_LATE_TEMPLATES = {
    "Emergency Militia",
    "Worker Home Guard",
    "Workerland Mobile Group",
    "Armi Mobile Group",
    "TVA Collapse Militia",
    "WPS Collapse Militia",
    "TGD Urban Guard",
    "TVA Infiltration Cell",
    "Workerland Militia",
    "Armi Security Detachment",
    "Line Infantry Brigade",
}
```

For each `create_unit`, accept either an exact template definition in the executing setup block or an explicit ensure call in the owner country scope before the state/capital scope. Reject a country-scope ensure placed inside the state scope.

- [ ] **Step 2: Run the new test and confirm missing guarantees**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_emergency_templates.py -q
```

Expected: FAIL for TVA collapse militia, VAD retreat levies, and the other unguarded late paths.

- [ ] **Step 3: Create idempotent ensure effects**

For every source template, copy the complete named `division_template` block into its corresponding ensure effect. Each effect contains one `if`; its limit negates `has_template` using the exact literal name in the first column below, and its body is the complete source `division_template` block. Use this exact source mapping and effect ID:

```text
Emergency Militia          ADISCORD_vorkerland_ensure_emergency_militia_template             common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt
Worker Home Guard          ADISCORD_vorkerland_ensure_worker_home_guard_template             common/scripted_effects/ADISCORD_vorkerland_collapse_effects.txt
Workerland Militia         ADISCORD_vorkerland_ensure_workerland_militia_template            history/units/WRK.txt
Workerland Mobile Group    ADISCORD_vorkerland_ensure_workerland_mobile_group_template       history/units/WRK.txt
Armi Security Detachment   ADISCORD_vorkerland_ensure_armi_security_detachment_template      history/units/VAD.txt
Armi Mobile Group          ADISCORD_vorkerland_ensure_armi_mobile_group_template             history/units/VAD.txt
TVA Collapse Militia       ADISCORD_vorkerland_ensure_tva_collapse_militia_template          history/units/TVA_vorkerland_collapse.txt
TVA Infiltration Cell      ADISCORD_vorkerland_ensure_tva_infiltration_cell_template         history/units/TVA_vorkerland_collapse.txt
WPS Collapse Militia       ADISCORD_vorkerland_ensure_wps_collapse_militia_template          history/units/WPS_vorkerland_collapse.txt
TGD Urban Guard            ADISCORD_vorkerland_ensure_tgd_urban_guard_template               history/units/TGD_vorkerland_collapse.txt
Line Infantry Brigade      ADISCORD_vorkerland_ensure_line_infantry_brigade_template         history/units/ROM.txt
```

Do not simplify battalion layouts or change lock/recruiting behavior. Group multiple templates in a tag package only when all consumers need that package.

- [ ] **Step 4: Call guarantees immediately before late spawns**

Call each ensure in the division owner's country scope before entering `capital_scope` or numeric state scope. For cross-tag aid decisions use explicit tag scope first:

```hoi4
TVA = { ADISCORD_vorkerland_ensure_tva_collapse_militia_template = yes }
WPS = { ADISCORD_vorkerland_ensure_wps_collapse_militia_template = yes }
TGD = { ADISCORD_vorkerland_ensure_tgd_urban_guard_template = yes }
```

Initial setup paths may use the same ensure effects instead of maintaining duplicate inline template definitions, but initial OOB units remain in their OOB owners.

- [ ] **Step 5: Extend the collapse validator**

Validate the required template/effect mapping, `has_template` guard, exact source layout tokens, and call-before-spawn ordering. Keep the repository-wide division-template audit unchanged unless it exposes a genuine generic gap.

- [ ] **Step 6: Run template and collapse tests**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_emergency_templates.py tools/tests/test_validate_adiscord_vorkerland_collapse.py tools/tests/test_validate_adiscord_division_templates.py -q
python -B tools/validate_adiscord_vorkerland_collapse.py
python -B tools/validate_adiscord_division_templates.py
```

Expected: PASS; the confirmed template names are never spawned without a same-scope guarantee.

- [ ] **Step 7: Record a working-tree checkpoint**

Run `git diff --check` on Task 6 paths and report the exact template-source mapping. Do not commit.

---

### Task 7: Restore vanilla focus-interface inheritance and custom assets

**Owner:** Primary agent because `interface/goals_shine.gfx` contains concurrent dirty work

**Files:**
- Create: `interface/ADISCORD_focus_shines.gfx` from the current working copy
- Delete: `interface/goals_shine.gfx`
- Delete: `interface/nationalfocusview.gui`
- Modify: `interface/ADISCORD_subuniticons.gfx:20-45`
- Modify: `tools/validators/validate_adiscord_vorkerland_civil_war_focus.py:34-36,739-781,2880-2950,3330-3360`
- Modify: `tools/tests/test_adiscord_vorkerland_civil_war_focus.py:1950-1975,1988-2048`
- Modify: `tools/tests/test_wrk_focus_icons.py:1-50`
- Create: `tools/tests/test_vorkerland_focus_interface_inheritance.py`

**Interfaces:**
- Consumes: current dirty custom sprite definitions, current vanilla `Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/interface/goals_shine.gfx`, and vanilla `gfx/texticons/unit_mechanized_icon_small.dds`.
- Produces: additive `interface/ADISCORD_focus_shines.gfx` and `GFX_unit_ADISCORD_mechanized_infantry_icon_small`.

- [ ] **Step 1: Add failing inheritance and icon tests**

Assert:

```python
def test_focus_interface_does_not_shadow_current_vanilla(self) -> None:
    self.assertFalse((ROOT / "interface/nationalfocusview.gui").exists())
    self.assertFalse((ROOT / "interface/goals_shine.gfx").exists())
    self.assertTrue((ROOT / "interface/ADISCORD_focus_shines.gfx").is_file())

def test_custom_mechanized_small_icon_exists(self) -> None:
    source = read(ROOT / "interface/ADISCORD_subuniticons.gfx")
    self.assertIn('name = "GFX_unit_ADISCORD_mechanized_infantry_icon_small"', source)
    self.assertIn('texturefile = "gfx/texticons/unit_mechanized_icon_small.dds"', source)
```

Also parse `SpriteType` names and assert the custom shine file has no duplicates and no sprite name also defined by current vanilla.

- [ ] **Step 2: Run tests and verify all three confirmed failures**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_focus_interface_inheritance.py tools/tests/test_wrk_focus_icons.py -q
```

Expected: FAIL because both shadowing paths exist, the additive file does not, and the small icon is missing.

- [ ] **Step 3: Snapshot and compare sprite names before editing**

Read the current working copy, not `HEAD`. Parse all `SpriteType` blocks from:

```text
interface/goals_shine.gfx
Z:/SteamLibrary/steamapps/common/Hearts of Iron IV/interface/goals_shine.gfx
```

Record counts for custom-only, vanilla-overlap, and duplicate names. Abort the edit if the source changes between snapshot and patch application.

- [ ] **Step 4: Rename the working custom source and drop vanilla overlaps**

Move the current mod file to `interface/ADISCORD_focus_shines.gfx`, preserving every custom-only block byte-for-byte. Delete only blocks whose sprite names exist in current vanilla. Then delete `interface/nationalfocusview.gui`.

- [ ] **Step 5: Add the small mechanized texticon**

Add:

```hoi4
SpriteType = {
    name = "GFX_unit_ADISCORD_mechanized_infantry_icon_small"
    texturefile = "gfx/texticons/unit_mechanized_icon_small.dds"
}
```

- [ ] **Step 6: Update GFX validators to aggregate additive sources**

Point custom focus-shine checks at `ADISCORD_focus_shines.gfx`. Continuous focus icons inherited from vanilla are accepted because the vanilla-named override is absent; do not add local duplicate aliases for `GFX_goal_continuous_repairments_shine` or `GFX_goal_continuous_reduce_training_time_shine`.

- [ ] **Step 7: Run focused interface verification**

Run:

```powershell
python -B -m pytest tools/tests/test_vorkerland_focus_interface_inheritance.py tools/tests/test_wrk_focus_icons.py tools/tests/test_adiscord_vorkerland_civil_war_focus.py -q
python -B tools/validate_adiscord_vorkerland_civil_war_focus.py
```

Expected: PASS; custom sprite count equals the recorded custom-only count, overlap count is zero, and both shadow paths are absent.

- [ ] **Step 8: Record a working-tree checkpoint**

Run `git diff --check -- interface tools/tests tools/validators` and retain the before/after sprite-count evidence for final reporting. Do not commit.

---

### Task 8: Integrate, validate, run a fresh campaign, and commit all task-owned work

**Owner:** Primary agent

**Files:**
- Modify only as required by failures attributable to Tasks 1-7.
- Final stage set: every verified Task 1-7 implementation, validator, test, plan, and task-owned WRK path; exclude unrelated technology, map, state-history, terrain, and temporary audit files.

**Interfaces:**
- Consumes: all produced scripted IDs, split files, validators, and interface assets.
- Produces: one final commit and fresh static/runtime evidence.

- [ ] **Step 1: Recheck ownership before integration fixes**

Run:

```powershell
git status --short
git diff --cached --name-only
git log -5 --oneline --decorate
```

Confirm no unrelated path is staged. Compare current task paths with the pre-implementation snapshot and preserve concurrent changes.

- [ ] **Step 2: Run focused validators**

Run:

```powershell
python -B tools/validate_adiscord_vorkerland_civil_war_focus.py
python -B tools/validate_adiscord_vorkerland_collapse.py
python -B tools/validate_adiscord_vorkerland_recovery.py
python -B tools/validate_adiscord_vorkerland_diplomacy.py
python -B tools/validate_adiscord_vorkerland_focus_decisions.py
python -B tools/validate_adiscord_vorkerland_story.py
python -B tools/validate_adiscord_vorkerland_stalemate.py
python -B tools/validate_adiscord_division_templates.py
```

Expected: every command exits 0.

- [ ] **Step 3: Run the complete Vorkerland and WRK test set**

Run:

```powershell
$vorkTests = @(Get-ChildItem -LiteralPath tools/tests -File | Where-Object { $_.Name -like '*vorkerland*.py' -or $_.Name -like 'test_wrk*.py' } | ForEach-Object FullName)
python -B -m pytest @vorkTests -q
```

Expected: PASS with no interrupted or partial run.

- [ ] **Step 4: Run repository gates**

Run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
git diff --cached --check
```

Expected: all exit 0. If a failure is unrelated and pre-existing, capture exact path and evidence; do not weaken a validator.

- [ ] **Step 5: Verify encoding, ownership, and absence contracts**

Check UTF-8 BOM for every touched Russian localisation file. Run `rg` to prove no active war-clock tokens, duplicate claimant trigger, legacy decision path, `interface/goals_shine.gfx`, or `interface/nationalfocusview.gui` remain.

- [ ] **Step 6: Obtain authorization and run fresh-campaign acceptance**

Before launching Hearts of Iron IV, ask the user for launch authorization. Fully restart the game, start a new campaign, and verify collapse materialization, regional wars, central preparation, central-showdown focus availability, late templates, legitimacy ties, 9-of-17 coalition activation/removal, capitulations, reunification, continuous focus UI, shines, and the mechanized small icon.

Inspect fresh `error.log` and `game.log`. The known focus-order, template, missing-shine, undefined GUI type, and mechanized texticon errors must not recur.

- [ ] **Step 7: Build an explicit final stage manifest**

List every Task 1-7 path. Stage only those verified paths, passing each literal manifest entry after `git add --`. Include deletions explicitly. Exclude `.github`, unrelated technologies, map/state files, terrain, `tools/_audit_*`, `tools/_tmp_*`, and any other path not owned by this plan.

- [ ] **Step 8: Inspect the exact staged patch**

Run:

```powershell
git diff --cached --name-status
git diff --cached --stat
git diff --cached --check
```

Compare the staged path list to the manifest and inspect every staged hunk. Unstage any unrelated path without discarding its working-tree contents.

- [ ] **Step 9: Create the single requested final commit**

Run:

```powershell
git commit -m "fix: harden WRK civil war campaign"
```

Verify `git show --stat --oneline HEAD` contains only the explicit task manifest. Do not push.

- [ ] **Step 10: Report residual runtime limitations honestly**

Report exact static counts, commit hash, fresh log timestamp, runtime scenarios exercised, and any acceptance step the user still needs to perform. Do not claim gameplay success from static validation alone.
