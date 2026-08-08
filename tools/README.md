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

## Vendor and reference assets

`third_party/hoi4_flag_maker/` is a manual, opaque vendor GUI, separate from
the supported Python tooling. Its A-Discord provenance and update policy are
in `third_party/hoi4_flag_maker/README.adiscord.md`; do not add a wrapper or
make it part of the validation command surface.

`tools/assets/reference/` holds non-runtime visual guidance imported with the
2026-01-07 icon-reference bundle. These binaries have no repository path
consumers and are neither generated output nor HOI4-loaded assets. Their move
preserves the following SHA256 values:

| Asset | Purpose and provenance | SHA256 |
| --- | --- | --- |
| `tools/assets/reference/REV'S COMPREHENSIVE BASIC ICON GUIDE v1.0.docx` | Third-party icon reference guide from the 2026-01-07 bundle. | `12d318f1681509c0d7919a7a9bcd4cb6c76af08324bc2f0d05512f5c09dc0b83` |
| `tools/assets/reference/Sudin‘s TFR Icon Guide.docx` | Third-party TFR icon reference guide from the 2026-01-07 bundle. | `b6c05cc68eafceef01af4b1185bdfe2696b0794c90cdde648f73948746458f6a` |
| `tools/assets/reference/TFR 图标教程 Icon Guide CN.docx` | Third-party Chinese icon reference guide from the 2026-01-07 bundle. | `6f252790c399d4448ed641542ed09d0303e50492022be38cc4648b34078b44a7` |
| `tools/assets/reference/focus.psd` | Generic focus-art reference PSD from the 2026-01-07 bundle. | `ade29c1bdece678057a165a566abaaf52cbe81b9908b488dfa9dc014efa4f1f0` |
| `tools/assets/reference/人像比例Framing.png` | Portrait-framing reference image from the 2026-01-07 bundle. | `864b6522d7c7576147a9fa7ee1e452bcb16d4f822503fa67a8a2a8ad6953d7bb` |
| `tools/assets/reference/色彩Color.png` | Colour reference image from the 2026-01-07 bundle. | `f8da09d5fed8b22ae87445139db1d133d3a40a59fd0fe52f26a0235af7300f21` |

Update reference files only as a reviewed, attributable asset change: record
source, purpose, and replacement SHA256 in this table. Do not treat the
guidance as a licence for its visual content.

The following `tools/` binaries were examined and intentionally left in place
because their names or embedded project content identify them as active or
ambiguous A-Discord editable sources rather than reference material:
`decisions.psd`, `portrait.psd`, `STP_Operation_Last_Banquette.psd`,
`val_ideology.psd`, `wrk_ideology.psd`, and `wrk_ideology_2.psd`.
