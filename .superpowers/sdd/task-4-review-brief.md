# Review Task 4: Dirty-State Bootstrap

Spec:
`docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`,
Shared Manifest and Task 4.

Review commit:
`0f0a589`

Inspect the direct commit only. Do not edit or commit.

Pass 1, spec compliance:

- exact 37 contaminated states, each applied once;
- state 23 modified only by the persistent modifier, never transferred;
- exact 32 spawn states remain ownerless/coreless;
- exact six capitals, VPs, buildings, manpower/category/supply;
- state 125 remains impassable;
- no modifier duration, remove trigger, or removal call;
- state populations/categories/supplies match the brief;
- localisation is sober and UTF-8 BOM.

Pass 2, quality/runtime risk:

- state-scoped dynamic modifier syntax and valid icon/modifier keys;
- idempotent helper scope in every enumerated state;
- valid ownerless state history/building/VP syntax;
- no accidental loss of province lists/history content;
- tests and validator cannot pass incomplete enumeration;
- no unrelated files.

Run DirtyStateTests, dirty section, general validator, diff check and targeted
independent counts. Report Critical/Important/Minor with line evidence and end
APPROVED or CHANGES REQUIRED.

Write `.superpowers/sdd/task-4-review-report.md`.
