# Difficulty-dependent campaign AI implementation plan

> Use superpowers:executing-plans for implementation and a fresh review before completion.

**Goal:** Make difficulty change native AI recruitment and campaign preparation in addition to the existing numeric bonuses.

**Specification:** Adapt the requested TDH approach to A-Discord's countries, scripted wars, finite resources and current economy. Keep the middle difficulty's behavior unchanged. The user has prohibited interrupting the current game process; native acceptance remains pending until a permitted cold start.

**Architecture:** A shared native strategy file owns the four non-default difficulty profiles. Shared predicates gate eligibility and resource-backed expansion. Country and campaign specializations extend their existing AI files and reuse current threat predicates. No new event loop, permanent marker, free equipment, division spawn or diplomatic route is required.

**Tech stack:** Clausewitz native AI strategies and boolean scripted triggers, Python unittest, RU/EN localisation.

## Constraints and review focus

- Preserve concurrent work in the authoritative checkout; append country sections without rewriting existing policies.
- Difficulty 0/1 reduces desired recruitment by 20/10 points; difficulty 2 has no overlay. Difficulty 3/4 adds 15/30 points only with a healthy economy, replenished army, real manpower/equipment and room below NOD's existing recruitment brake.
- Additional recruitment stops while 12000 manpower is already training. Keep 12000 free recruits, 6000 rifles and transport reserves when the country uses supply trucks. These are expansion guards, not guaranteed force counts or native hard caps.
- Production adjustments use weights, never additional fixed factory minima. Current replacement, fiscal, template and front-control rules retain authority.
- War preparation must expire with its actual threat. Country handoff, capitulation, subjecthood, suppression and terminal world state close the overlay. SRP's separate war remains independent of the STP-STS settlement.
- Keep the disabled southern final war disabled. Do not enable diplomacy or change political routes and war dates.
- RU localisation stays UTF-8 with BOM; gameplay text stays UTF-8 without BOM; authored text uses ASCII dashes.

## Implementation

- [x] Add failing source-execution tests in `tools/tests/test_adiscord_difficulty_ai.py` for all five levels, resource boundaries, lifecycle cleanup, simultaneous wars and native additive priorities.
- [x] Add `common/scripted_triggers/ADISCORD_difficulty_triggers.txt` and `common/ai_strategy/ADISCORD_difficulty_ai.txt` with shared eligibility, bounded recruitment and stockpile/construction policies.
- [x] Extend existing STP, VAL, RUS, Vorkerland, NAM resource-war and western/southern final-war AI files with gated campaign production and logistics specializations. Reuse their existing threat and technology predicates.
- [x] Explain behavioral differences in the existing RU/EN difficulty tooltips and document the source contract in `docs/development/performance.md`.
- [x] Run focused tests, relevant existing AI/front/economy tests, the repository suite, `python -B tools/validate_tc.py --limit 300`, and `git diff --check`. Report unrelated failures separately.
- [x] Review the final change and record remaining native acceptance requirements without claiming observed battle behavior.

## Verification limits

The 19 difficulty tests pass. The selected AI regression set passed 67 tests; the general validator and whitespace check also passed. Five front-test failures reproduce against the pre-change snapshots. The optional full suite did not finish within ten minutes and reported failures; a subsequent fail-fast run stops in the concurrently edited technology generator (`production: lane spacing cannot centre integer grid slots`). Full-suite and native campaign acceptance remain incomplete.
