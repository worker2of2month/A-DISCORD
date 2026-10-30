# VAD crown district policy implementation plan

Use superpowers:executing-plans inline. Preserve the shared dirty checkout; no commits, worktree replacement, Computer Use or game launch.

**Goal:** Replace the generic wartime coronation branch with an imperial district choice, keeping monarchy out of the joint cabinet and collegial staff routes.

**Spec:** docs/superpowers/specs/2026-10-26-vorkerland-civil-war-rework-design.md, VAD political identity and removal of cloned legitimacy branches.

**Architecture:** Existing VAD district targets, chancery receipt and lifecycle. Existing country files per engine type. No new currency, periodic handler or duplicated completion marker. New campaigns only; preserve paid operations and current-version save/load.

## Contract

Remove VAD_convene_the_court_of_honours after tracing its consumers. Keep the two surviving IDs but rename their visible narrative: VAD_stage_the_coronation_rites becomes district privileges, VAD_mortgage_the_regalia becomes crown collateral. Each costs 21 days and directly requires VAD_bind_officers_to_chancery. Cells (50,11) and (52,11) keep them near the imperial route. Both require the actual imperial government, an industrial district with a charter, and remain optional to military readiness. No wartime coronation occurs.

- VAD_crown_privileges_programme: state target, 30 PP and 80 support equipment, 21 days, receipt kind 10. Delivery grants the district +15% local factories and +10% local supply for 90 days, country +0.03 legitimacy and BOP +0.10 toward chancery.
- VAD_crown_collateral_programme: state target, 35 PP and 60 support equipment, 21 days, receipt kind 11. Delivery grants 1800 infantry equipment, country -0.04 legitimacy and BOP -0.10 toward headquarters; the pledged district loses 20% local factories for 90 days.
- Both use the existing VAD_oath_pp/manpower/support/kind/state receipt, VAD_oath_in_progress target reservation, standard full cancellation refund and living-successor handoff. No extra escrow. Both require current ownership/control, the charter and at least one civilian or military factory at payment and delivery. Neither active result permits another crown policy on the same district. The country slot excludes all other chancery work.
- Completed local investments are disabled while the administration is inactive. Actual district loss, charter removal or war retirement removes their modifiers through the existing state cleanup. Current campaign subjugation/liberation retains institutional state and BOP; do not replace ordinary refund hooks with full country retirement. Paid work cancels on lost independence/capitulation, and wrong target/kind/repeated callbacks must be inert.
- An imperial leader is Petrichev with the completed imperial-entry focus, no joint or collegial government, and an active independent VAD administration. Use this predicate in both focus availability and programme settlement. Hide the branch after joint/staff choice. Joint AI must not name imperial focuses; imperial AI selects privileges only.
- All prices, outcomes, local penalties and cancellation are visible. Descriptions remain narrative. Use existing inspected action art and matching shine masks. RU/EN BOM; gameplay no BOM; ASCII punctuation.

## Tasks

- [x] Add failing source-executing accounting, target, lifecycle, political-access and art tests. Native building count syntax is documented in installed triggers_documentation.md under building_count_trigger.
- [x] Implement programmes, state modifiers and lifecycle integration; rewrite focus source, localisations, icons and AI. Remove only verified retired consumers.
- [x] Update manifests and geometry contracts; generator check/apply/check, repeated-apply hash, inspect source layout and remove this work's previews.
- [x] Run Vorkerland suites, shared callback ownership/order, full TC and diff checks. One fresh read-only review with important fixes covered RED/GREEN. Native runtime remains manual/unverified.

## Review focus

An apparent monarchy programme must never run under the joint cabinet or collegial staff. No industrial collateral may pay after its factories, charter or current control are lost. Shared receipt and target marker must prevent old callbacks from settling a different district's payment. Annexation refunds the successor before clearing the receipt; an unrelated country's cleanup cannot remove VAD's assets. Both alternatives must remain useful and reachable without becoming mandatory military preparation.
