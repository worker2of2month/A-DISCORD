# Review Task 1: Validator and Manifest

Spec:
`docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`,
Task 1 and Shared Manifest.

Review range:
`3191c8b76ef772db3c0d542e1efeed3e94227949..7cc0205b24cba0fdd1886c627c16702848612f23`

Inspect the commit and all three changed files directly with Git. Do not edit
production files and do not commit.

Review in two passes:

1. Spec compliance:
   - exact tag/state/group/capital/partition data;
   - requested public interfaces and section names;
   - expected missing-content behavior for future tasks;
   - read-only operation.
2. Code quality:
   - parser robustness for normal Clausewitz formatting;
   - false-positive/false-negative risks;
   - useful failure messages and exit semantics;
   - unit-test quality and hidden errors.

Run any relevant read-only tests. Classify findings as Critical, Important, or
Minor with exact file/line evidence. End with one verdict:

- APPROVED
- CHANGES REQUIRED

Write the full review to:
`.superpowers/sdd/task-1-review-report.md`
