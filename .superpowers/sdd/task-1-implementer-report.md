# Task 1 implementer report

## Changed files

- `tools/vorkerland_collapse_manifest.py`
- `tools/validate_adiscord_vorkerland_collapse.py`
- `tools/test_validate_adiscord_vorkerland_collapse.py`

The commit intentionally contains only these three files.  The shared manifest
contains the prescribed tags, contaminated states, dirty groups, capitals, and
full state partitions.  The validator is read-only and supports `manifest`,
`states`, `countries`, `dirty`, `events`, `ai`, `outcomes`, and `superevents`.

## TDD evidence

### RED

Command:

```powershell
python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v
```

Result: exit `1`; `ModuleNotFoundError: No module named
'tools.vorkerland_collapse_manifest'`.  The single unittest failed while
importing the missing manifest, as required.

### GREEN

Command:

```powershell
python -m unittest tools.test_validate_adiscord_vorkerland_collapse -v
```

Output:

```text
test_manifest_is_unique_and_complete (...) ... ok
Ran 1 test in 0.000s
OK
```

Exit `0`.

## Preflight and static checks

Command:

```powershell
python tools/validate_adiscord_vorkerland_collapse.py --section countries
```

Result: exit `1` as expected.  It reported the missing fixed-tag registry,
character database, country/history/OOB files, and all three flag sizes for
the future tags (beginning with `TVA`).  This confirms that absent later-task
content is returned as findings rather than causing a Python exception.

Also run successfully:

```powershell
python -m py_compile tools/vorkerland_collapse_manifest.py tools/validate_adiscord_vorkerland_collapse.py tools/test_validate_adiscord_vorkerland_collapse.py
git diff --check -- tools/vorkerland_collapse_manifest.py tools/validate_adiscord_vorkerland_collapse.py tools/test_validate_adiscord_vorkerland_collapse.py
```

Both returned exit `0`.

## Commit

`7cc0205b24cba0fdd1886c627c16702848612f23`

Message: `test: add vorkerland collapse validation manifest`

## Follow-up concerns

The country preflight is expected to fail until Task 3 creates the fixed-tag
content.  Sections for later tasks similarly report missing files as findings
until those tasks supply them.
