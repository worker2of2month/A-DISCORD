# Industry and Electronics Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Preserve the authoritative dirty checkout and unrelated work.

**Goal:** Implement the approved industry/electronics research design and construction capacity progression.

**Architecture:** Keep technology rows, graphs, AI, prices and rendering in the existing technology generator. Regenerate the two gameplay files and their shared GUI, localisation and manifests through a bounded builder mode that does not require unrelated artwork sources.

**Tech Stack:** Python, unittest, Clausewitz, generated GUI/GFX, UTF-8 localisation.

**Spec:** `docs/superpowers/specs/2026-10-27-industry-electronics-redesign-design.md`

## Global Constraints

- New campaigns; no old-save migration or recurring recovery.
- Common capacity: eight increments of 0.10 in 2160/2162/2164/2166/2169/2172/2176/2180.
- Density specialisation: two additional increments of 0.10 in 2166/2174; restoration excludes those increments but retains the common route.
- No research slots, new resources, new building types or changes to MAX_SHARED_SLOTS.
- Existing external technology IDs and all building/unit/equipment unlocks remain reachable.
- Keep all edits in existing source/data-type files; preserve unrelated country work.

## Review Focus

1. An XOR route must never require both alternatives at a merge: enumerate feasible graph paths.
2. A low-capacity state must receive the same common multiplier on either route: assert 0.80/1.00 attainable totals and verify native rounding.
3. New science/energy branches must not grant modern technologies at startup: compare starting profile closures.
4. Missing country artwork must not block unrelated research generation: exercise the bounded output mode without image-export calls.
5. Regeneration must preserve all other tabs and shared localisation: compare unaffected files and generated sections, then repeat for idempotence.

## Task 1: Research catalogue and graphs

Files: `tools/builders/build_adiscord_technology_system.py`, `tools/tests/test_build_adiscord_technology_system.py`.

Interfaces: retain `Branch`, `Tech`, `BranchGraph`, `effects_for`, `graph_for_branch` and `xor_siblings`; use explicit named routes in `PROGRAMME_ROUTES`.

- [x] Add failing tests for capacity dates/totals, no impossible XOR merge, industry/electronics scope, preserved IDs and profile closure.
- [x] Run the new test class and verify meaningful failures.
- [x] Expand authoritative civil rows, explicit route edges and symmetric XOR groups; keep scientific, applied and construction specialisations distinct.
- [x] Add semiconductor main branch and retain military and energy unlocks.
- [x] Run graph and catalogue tests, expecting all new assertions to pass.

## Task 2: Costs, AI and presentation

Files: same generator and tests; generated GUI/GFX and Russian/English technology localisation.

Interfaces: `research_cost_for`, `ai_will_do_for`, `technology_description_notes`, `icon_for_technology`, `render_folder`.

- [x] Test the attainable 2160-2170 construction/industrial budget against half of two slots at native base cost; test distinct roles of exclusive alternatives.
- [x] Set bounded civil research prices, appropriate AI priorities, descriptions and usable icons.
- [x] Verify unique card coordinates, chronological edges, reachable native building levels and complete localisation.

## Task 3: Bounded regeneration and verification

Files: generator, existing technology tests, existing design documentation, generated output files under their registered owner.

Interfaces: add `--civil-only` paired with `--check` or `--apply`; it writes civil technology data and shared definitions/manifests, without unrelated image conversion or country-history edits.

- [x] Add a test that civil output regeneration does not invoke unrelated image exporters and preserves non-civil technology files.
- [x] Run dry/check before apply; regenerate; compare all changed paths against ownership and scope.
- [x] Hash outputs, apply again and verify identical hashes; check BOM and localisation quoting.
- [x] Run focused suites, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`; compare pre-existing failures.
- [ ] Cold-load gameplay/UI verification remains required; static checks do not establish native rendering or state-slot rounding.
- [x] Request a fresh final code review, resolve actionable findings and remove only temporary artifacts created by this task.

## Execution

The user approved implementation of both branches. Execute in the current authoritative checkout without another approval checkpoint; do not commit unrelated work. Native execution and one final independent review keep shared generator edits sequential.
