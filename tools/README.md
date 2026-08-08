# Tooling

The scripts in this directory validate and generate A-Discord content. Run
them from the repository root with `python -B` so validation does not create
bytecode artifacts.

Implementations are grouped by role: generators live in `tools/builders`,
validators in `tools/validators`, shared manifests and helpers in `tools/lib`,
and tests in `tools/tests`. Root validator and builder scripts are compatibility
facades for existing commands.

## Check and apply

- Every packaged builder defaults to a real, non-mutating validation. `--check`
  names the same behavior explicitly; `--help` is also safe. A write requires
  an explicit, mutually exclusive `--apply`.
- Run a builder through its package module, for example
  `python -B -m tools.builders.build_adiscord_map_buildings`. Root
  `tools/build_adiscord_*.py` paths remain compatibility facades with the same
  arguments and exit codes.
- After an intentional apply in a disposable full repository, run the complete
  apply pipeline twice and compare the full union of owned output hashes. Unit
  discovery never opts into that write test in the live checkout.
- Generated output belongs to the generator that emits its marker or documents
  the path. Change that generator rather than patching its output by hand.

## Generated-output registry

`tools/data/generated_output_owners.json` is the reviewable ownership manifest.
Each family records its packaged owner, bounded output globs, source inputs,
check/apply commands, deletion policy, and whether ownership is exclusive or a
documented layer. The loader rejects missing paths, output overlaps involving
an exclusive owner, and layered ownership without an explanation.

The top-level `apply_sequence` is authoritative; JSON entry order is not. The
state pipeline deliberately runs outer shells, northern population, Exclusion
Zone boundary realignment, then northern population again. The repeated
northern pass refreshes metadata whose province and owner blocks depend on the
realigned state boundaries. Technology runs before doctrine so doctrine can
remove migrated keys from their shared localisation as the final cleanup.

Run the ownership and safe-CLI contract with:

```powershell
python -B -m unittest tools.tests.test_generated_output_ownership -v
```

The full apply/idempotence case is enabled only by setting
`ADISCORD_GENERATOR_SANDBOX` to a disposable, fully materialized repository
copy. The helper rejects the authoritative checkout, any directory inside it,
and any ancestor containing it. Never point this variable at the live mod.

## Full static gate

Run the complete tooling test suite through the canonical package directory:

```powershell
python -B -m unittest discover -s tools/tests -p "test_*.py"
```

Run this command for the whole total-conversion static validation:

```powershell
python -B tools/validate_tc.py --limit 300
```

Pair it with the focused test or validator for the changed subsystem and
`git diff --check`. A green static gate does not replace a full game restart
and fresh-log review for runtime-visible changes.
