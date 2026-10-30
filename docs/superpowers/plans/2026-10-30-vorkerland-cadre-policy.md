# Vorkerland personnel and trial programmes

> **For agentic workers:** Use superpowers:executing-plans for implementation in the existing shared checkout.

**Goal:** Give TVA distinct personnel choices, paid field-trial protocols and doctrine programme upgrades with preserved contracts.

**Architecture:** Keep the existing country files, decision IDs and temporary combat ideas. Country variables own the available and protected cadre pools; reunification reads both before annexing TVA. Field trials keep their paid kind and probability through settlement or refund.

**Tech Stack:** Clausewitz scripts, UTF-8 BOM localisation, Python source-executing tests and focus builder.

**Spec:** `docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md`, TVA personnel reserve, trial protocol and military doctrine sections.

## Global constraints

- Preserve unrelated dirty work. Do not commit the shared checkout.
- New campaigns only; preserve current-campaign save/load and handoff.
- Modify focus sources and regenerate through check/apply/check.
- No Computer Use or game launch. Native rendering remains a manual check.
- Keep gameplay scripts without BOM and both existing localisation BOMs.

## Review focus

- An unrelated war cannot activate or preserve either combat regime.
- Fractional balances below any price cannot be charged.
- A second callback cannot repeat payment while the regime is active; native one-time decisions forbid later reuse.
- Protected cadres remain available to the successor after the timed idea expires.
- Handoff reads the reserve before annexation and caps the inherited total at 100.

## Task 1: Personnel programmes and inheritance

**Files:** Existing Vorkerland scripted triggers/effects, decisions, ideas, scripted localisation, Russian/English localisation and `tools/tests/test_vorkerland_preparation.py`.

**Interfaces:** `TVA_final_operation_context` is a boolean country trigger. `TVA_protected_cadre` is the protected reserve. The existing two `*_activate_plan` decisions debit their full prices and apply their existing 70-day ideas. `ADISCORD_vorkerland_pw_record_trial_iterations` consumes both reserves before annexation.

- [x] Add source-executing tests for prices, duplicate callbacks, both terminal paths, protected inheritance and current-campaign persistence; run and observe failure.
- [x] Implement the specified programmes, meaningful UI costs and protected-reserve consumer.
- [x] Run the personnel tests and existing TVA administration/economy tests; require zero failures.

## Task 2: Reachable focus choice and verification

**Files:** `focus_trees/Vorkerland/tva/focuses.txt`, existing AI plans, focus validator, focus tests, GFX aliases and focus-effects guide.

**Interfaces:** Both final courses follow `TVA_close_operational_loop`, exclude each other and are prepared during central preparation/showdown. Remove `TVA_declare_the_final_iteration` and its unused localisation. AI terminates each course on its completed focus instead of a duplicate flag.

- [x] Verify graph prerequisites, mutually exclusive courses, AI references and the preparation/war distinction.
- [x] Inspect and bind meaningful existing textures; update both normal and shine sprites.
- [x] Run the focus builder check/apply/check; prove second-apply SHA-256 identity.
- [x] Run focused tests, `python -B -X utf8 tools/validate_tc.py --limit 300` and `git diff --check`; inspect all reported sections.
- [x] Review the changed scope and remove only this task's temporary previews.

## Task 3: Distinct field-trial programmes

**Files:** Existing TVA focus source and Vorkerland effects, triggers, decisions,
scripted localisation, RU/EN localisation, ideas and tests.

**Interfaces:** A paid trial stores `TVA_trial_kind` alongside its existing receipt
and chance. Shared price calculation takes an explicit temporary kind input.
Refund and country handoff read that kind before clearing the receipt. Successful
trials award their paid protocol, even if a focus completes while they are pending.
The logistic trial consumes the existing temporary logistic idea; its free
activation decision is removed. Focus rewards explain the specialization and
unlock the existing trial decision without unrelated manpower or equipment gifts.

- [x] Add failing source-executing tests for distinct prices, fractional shortages,
  payment/result snapshots, every outcome, interruptions and successor refunds.
- [x] Implement the protocol snapshots and results using the existing trial slot.
- [x] Update focus/UI rewards, inspect icons, regenerate with check/apply/check
  and verify second-apply identity.
- [x] Run focused suites, full validation and diff checks; review the changed scope.

**Review focus:** Pending baseline trials must not become cheaper specialized
trials; a new focus must not alter refunds; cancelled manpower must follow the
living recipient; repeated callbacks must not duplicate results; unrelated wars
must not preserve trials or their combat idea. Native timing and UI remain manual.

## Task 4: Doctrine programmes

**Files:** Existing TVA focus source, Vorkerland programmes, aggregate, ideas,
AI plans, localisation, focus contracts and source-executing tests.

**Interfaces:** Remove the two linear doctrine followups. Continuous assault
upgrades delivered weapon series with a 21-day combat regime during the civil
war; delivery resets rather than extends that regime. Measured front upgrades
completed training with `TVA_crew_standards`, bounded 0-3. Derived organization
and experience-loss values combine standards with existing policy inputs.
The shared programme receipt, prices and durations stay authoritative.

- [x] Test successful delivery, peace, interruption, duplicate callbacks, pending
  upgrades, training at a full reserve, caps and exact modifier previews.
- [x] Implement the two programme upgrades and terminal cleanup; initialize
  standards once and preserve ordinary current-campaign state.
- [x] Remove the obsolete focuses and rewards, update AI/source contracts and
  meaningful icons; regenerate and verify idempotence.
- [x] Run focused suites, full validation and diff checks, then review the scope.

**Review focus:** Training must remain useful at either cap; cancellations must
not award a standards level; doctrines must not alter a paid production tier;
the frontline regime must not survive peace or accumulate unlimited duration;
closing TVA must remove its effects without resetting a living country's state.
