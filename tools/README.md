# Tooling

The scripts in this directory validate and generate A-Discord content. Run
them from the repository root with `python -B` so validation does not create
bytecode artifacts.

Implementations are grouped by role: generators live in `tools/builders`,
validators in `tools/validators`, shared manifests and helpers in `tools/lib`,
and tests in `tools/tests`. Root validator and builder scripts are compatibility
facades for existing commands.

## Check and apply

- A check, dry run, or validator must not write repository files. Use it first
  to inspect intended changes.
- A mutating generator must require an explicit `--apply`; run its check again
  afterwards and, when it generates files, rerun it to confirm idempotence.
- Generated output belongs to the generator that emits its marker or documents
  the path. Change that generator rather than patching its output by hand.

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
