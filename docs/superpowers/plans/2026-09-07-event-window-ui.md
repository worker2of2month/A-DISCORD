# A-Discord Event Window UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ordinary `country_event` popup with the approved compact dark dossier and add a dedicated 507x184 test picture used by the existing event UI QA events.

**Architecture:** Keep the engine-bound `EventWindow`, `top_Window`, `midsection`, `bottom_Window`, `Title`, `Description`, `event_picture`, `options_grid`, and `event_option_entry` names. A deterministic builder generates the four popup surfaces, option background, preview, and cropped test picture from checked-in source art; hand-authored GUI/GFX files bind those outputs without changing operative, leader, or news event windows.

**Tech Stack:** Clausewitz `.gui`/`.gfx`, Python 3, Pillow, repository UI surface helpers, `unittest`.

**Spec:** `docs/mockups/event-window-concept-v1.html`

## Global Constraints

- Preserve unrelated dirty work and do not stage or commit it.
- Change only the ordinary `EventWindow`; leave `EventWindow_Operative`, `EventWindow_leader`, and `EventWindow_News` intact.
- Keep the ordinary event picture contract at 507x184, retain the shared 300-pixel option-entry contract used by all four event-window types, and leave all engine-bound widget names unchanged.
- Use the existing technology palette and restrained framing so the popup matches the other reskinned screens without repeated nested borders.
- Run the builder in check mode before apply mode, then prove a second check is clean.
- Static checks do not count as in-game visual proof; do not launch HOI4 without separate authorization.

---

### Task 1: Lock the approved composition with failing contracts

**Files:**
- Create: `tools/tests/test_adiscord_event_ui.py`

**Interfaces:**
- Consumes: current `interface/eventwindow.gui`, `interface/eventwindow.gfx`, `interface/ADISCORD_eventpictures.gfx`, existing debug events.
- Produces: executable contracts for 615x650 popup geometry, 507x184 picture, 507x39 option row, generated ownership, and test-event picture binding.

- [ ] **Step 1: Write the failing test**

  Add `unittest` assertions that the root uses `GFX_event_popup_bg`; the top contains the picture at `(54, 104)`; the middle contains readable `hoi_16mbs` description text with a bounded scrollbar; the bottom contains the shared 300-pixel option grid; the five existing `ADISCORD_event_ui_test` events use `GFX_event_adiscord_ui_test`; generated outputs have exact image sizes; and `event_ui_assets` is registered in `generated_output_owners.json`.

- [ ] **Step 2: Verify RED**

  Run: `python -B -m unittest tools.tests.test_adiscord_event_ui -v`

  Expected: assertion failures for the absent compact layout, missing generated owner, and missing dedicated test picture.

### Task 2: Generate restrained popup surfaces and the test image

**Files:**
- Create: `tools/builders/build_adiscord_event_ui_assets.py`
- Create: `gfx/event_pictures/source/event_adiscord_ui_test_source.png`
- Modify: `tools/data/generated_output_owners.json`
- Generate: `gfx/interface/event_popup_bg.png`
- Generate: `gfx/interface/event_popup_top.png`
- Generate: `gfx/interface/event_popup_middle.png`
- Generate: `gfx/interface/event_popup_bottom.png`
- Generate: `gfx/interface/event_option_entry_adiscord.png`
- Generate: `gfx/interface/events/preview/ADISCORD_event_window_preview.png`
- Generate: `gfx/event_pictures/event_adiscord_ui_test.png`

**Interfaces:**
- Consumes: `PALETTES["technology"]`, `metal_surface`, `outer_frame`, `apply_or_check`, `production_surface_source.png`, and the generated source illustration.
- Produces: `expected_outputs() -> dict[Path, bytes]` plus a check-by-default / `--apply` CLI.

- [ ] **Step 1: Implement the minimal builder**

  Generate a 615x650 dark outer shell with one teal divider, transparent segment overlays sized 615x308, 615x64, and 615x168, a shared 300x35 restrained option background inside a 300x39 row, a 1600x900 visual preview, and an `ImageOps.fit` 507x184 test picture. Avoid decorative screws, thick inner boxes, repeated rails, and text baked into game UI assets.

- [ ] **Step 2: Register exact ownership**

  Add an exclusive `event_ui_assets` entry with every generated output, the builder, the shared surface helper, the metal source, and test-art source listed as inputs.

- [ ] **Step 3: Follow the generator contract**

  Run the builder without `--apply` and confirm it reports stale outputs; run with `--apply`; run again without `--apply` and confirm all outputs are current.

### Task 3: Bind the approved layout without disturbing other event types

**Files:**
- Modify: `interface/eventwindow.gui`
- Modify: `interface/eventwindow.gfx`
- Modify: `interface/ADISCORD_eventpictures.gfx`
- Modify: `events/ADISCORD_scenario_debug_events.txt`

**Interfaces:**
- Consumes: generated popup surfaces and `GFX_event_adiscord_ui_test`.
- Produces: compact ordinary event popup and console-testable events `ADISCORD_event_ui_test.1` through `.5`.

- [ ] **Step 1: Replace only the ordinary popup block**

  Set `EventWindow` to 615x650 centered at `(-307, -325)`. Keep the title and picture in `top_Window` (picture at `(54, 104)`), description in `midsection`, and choices in `bottom_Window`; retain the exact engine names and allow the middle section to remain the only dynamically growing segment.

- [ ] **Step 2: Bind generated sprites**

  Define `GFX_event_popup_bg`, keep the existing top/middle/bottom sprite IDs on the generated assets, and size the shared `event_option_entry` to 300x39 with a 300x35 background and `hoi_18mbs` text so operative, leader, and news grids remain compatible while four ordinary choices retain a 4-pixel gap.

- [ ] **Step 3: Bind the test picture**

  Add `GFX_event_adiscord_ui_test` to the A-Discord-prefixed event picture extension and point all five existing UI QA events at it.

- [ ] **Step 4: Verify GREEN**

  Run: `python -B -m unittest tools.tests.test_adiscord_event_ui -v`

  Expected: all event UI contracts pass.

### Task 4: Validate the scoped change

**Files:**
- Verify all files listed above.

**Interfaces:**
- Consumes: completed event UI implementation.
- Produces: static evidence and a reviewable preview; no commit or push.

- [ ] **Step 1: Run focused compatibility checks**

  Run: `python -B -m unittest tools.tests.test_adiscord_event_ui tools.tests.test_adiscord_ui_contracts tools.tests.test_validate_adiscord_runtime_compat tools.tests.test_generated_output_ownership -v`

- [ ] **Step 2: Run repository gates**

  Run: `python -B tools/validate_tc.py --limit 300`

  Run: `git diff --check`

- [ ] **Step 3: Inspect only owned changes**

  Run a scoped `git diff --` over the event GUI/GFX, builder, tests, ownership registry, debug events, and mockup files. Confirm no operative, leader, or news window block changed and no unrelated dirty path was staged.

- [ ] **Step 4: Report the runtime boundary**

  Link the generated preview and test picture. State that a full HOI4 restart and fresh invocation of `event ADISCORD_event_ui_test.1` through `.5` remain necessary for visual/runtime acceptance.
