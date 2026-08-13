# Review Task 2: State Splits

Spec:
`docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`,
Shared Manifest and Task 2.

Review commit:
`52b4079a1f0517aff890abd18880416fe9b00afd`

The commit's direct parent is the review base. An unrelated documentation
commit may exist immediately before it; do not review or change that commit.

Inspect all 13 changed files directly. Do not edit or commit.

Pass 1, spec compliance:

- exact manifest province partitions and no duplicates/loss;
- exact populations, owners, cores, state categories, supplies and VPs;
- exact factory transfer rules;
- exact Russian localisation and UTF-8 BOM;
- no map bitmap/definition/rail/supply edits.

Pass 2, quality:

- valid HOI4 state syntax and history scopes;
- no duplicate state/province/VP ownership;
- focused test meaningfully detects missing/duplicate content;
- compatibility with the general validator.

Run the focused state test, section validator, and any cheap independent
checks. Report findings as Critical, Important, or Minor with file/line
evidence, ending in APPROVED or CHANGES REQUIRED.

Write the report to `.superpowers/sdd/task-2-review-report.md`.
