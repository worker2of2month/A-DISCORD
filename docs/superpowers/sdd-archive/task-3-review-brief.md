# Review Task 3: Fixed Country Roster

Spec:
`docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`,
Shared Manifest and Task 3.

Review commit:
`e64a90a`

Inspect the commit directly. Do not edit or commit.

Pass 1, spec and narrative compliance:

- exactly 16 fixed tags and exact country/Russian roster names;
- dormant history gives no startup territory, OOB, faction or subject status;
- every future capital and division province matches `CAPITALS`;
- Dorian Worx is recognisably the technocratic claimant, not a generic
  pragmatist;
- all other new leaders and collective administrations are bound/localised;
- regional tags have two militia divisions, dirty tags one, exact equipment;
- exact source flag trio used for every tag;
- no unrelated internal coordination files are tracked in the feature commit.

Pass 2, quality:

- valid character/country/OOB/GFX/loc syntax;
- unique keys, correct leader recruitment and portrait resolution;
- sufficient ideology/party localisation;
- no new tags own states or load OOBs at campaign start;
- validator/test coverage does not mask absent content.

Run focused CountryRosterTests, countries section, general validator and cheap
independent flag hash checks. Classify Critical/Important/Minor with file/line
evidence. End APPROVED or CHANGES REQUIRED.

Write report to `.superpowers/sdd/task-3-review-report.md`.
