# A-Discord repository rules

## Generated output

Treat the generator that names an output in its header or source as the owner
of that output. Update the generator and regenerate; do not hand-edit generated
state history, strategic regions, technology data, map buildings, or generated
localisation to make a one-off correction. Use the builder's dry-run or
`--check` mode before its explicit `--apply` mode, then prove a second run is
idempotent when the builder changes data.

## Localisation encoding

Russian localisation files use UTF-8 with a BOM. Preserve that BOM and verify
it after editing; do not use shell rewrites that can remove it or corrupt
Cyrillic text.

## Verification

Run the focused test or validator for the paths changed, then run:

```powershell
python -B tools/validate_tc.py --limit 300
git diff --check
```

Static validation cannot prove Clausewitz runtime behavior. Fully restart
Hearts of Iron IV and inspect fresh logs after changes to loaded gameplay,
ideas, GFX, AI, defines, localisation names, or map data. Capture a fresh
campaign/UI result when the change is player-visible.

## Dirty worktrees

This repository is commonly an authoritative, dirty checkout. Preserve
unrelated work: inspect status first, avoid reset/checkout/bulk formatting,
and stage explicit verified paths only. Do not include someone else's changes
in a commit, and do not delete files unless their exact targets and purpose
have been verified.
