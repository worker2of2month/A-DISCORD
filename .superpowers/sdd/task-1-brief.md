# Task 1: Specialized Validator and Manifest

Plan: `docs/superpowers/plans/2026-07-24-vorkerland-collapse-dirty-zone.md`
Base commit: `3191c8b76ef772db3c0d542e1efeed3e94227949`

## Scope

Create only:

- `tools/vorkerland_collapse_manifest.py`
- `tools/validate_adiscord_vorkerland_collapse.py`
- `tools/test_validate_adiscord_vorkerland_collapse.py`

Do not modify any existing dirty file. Work directly on the current `main`
checkout by explicit user permission. Commit only the three files above with:

`test: add vorkerland collapse validation manifest`

## Required workflow

1. Write a failing unit test importing the manifest.
2. Run:
   `python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v`
   and record the expected import failure.
3. Implement the shared manifest exactly as written in the plan.
4. Implement a read-only validator exposing:
   `validate(root: Path) -> list[str]`
   and CLI `--section`.
5. Supported sections must be:
   `manifest`, `states`, `countries`, `dirty`, `events`, `ai`, `outcomes`,
   and `superevents`.
6. Run the unit test again and obtain PASS.
7. Run:
   `python tools/validate_adiscord_vorkerland_collapse.py --section countries`
   and obtain an expected non-zero result for missing fixed-tag content.
8. Commit only the three new files.

## Required manifest invariants

- 16 unique tags:
  `TVA EYR EGC WPA WPS PSD EBA DVA SRA ZTA SLA RZA MLR ERT IRT SCA`
- 37 contaminated states:
  `23 24 49 51 57 59 60 125 152 153 154 155 160 165 166 167 168 169
  171 172 173 176 177 178 180 181 182 183 184 185 187 188 189 190
  191 192 193`
- Dirty groups, capitals, and state partitions must be copied verbatim from
  the Shared Manifest section of the plan, without abbreviating province
  lists.
- `DIRTY_GROUPS` must cover all contaminated states except
  `{23, 24, 57, 59, 60}` exactly once.
- `CAPITALS` keys must equal `TAGS`.
- `STATE_PARTITIONS` keys must equal `{71, 72, 74, 76, 80}`.

## Validator behavior for later tasks

The validator is the feature gate used by Tasks 2–8. It must be useful before
the content exists: absent later feature files are reported as findings, not
as Python exceptions. Section selection must limit checks to the requested
section. Avoid overly rigid formatting assumptions that would make normal
Clausewitz whitespace/comments fail. The validator must not modify files.

Write the completion report to:
`.superpowers/sdd/task-1-implementer-report.md`

Include changed files, RED/GREEN commands and outputs, preflight result,
commit hash, and any follow-up concerns.
