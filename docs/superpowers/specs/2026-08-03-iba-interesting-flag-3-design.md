# IBA Interesting Flag 3 Design

## Goal

Assign `gfx/flags/interesting flag 3.png` to IBA without allowing the existing flag generator to restore IBA's procedural placeholder later.

## Design

- Preserve the supplied artwork as the canonical generator input at `gfx/flags/source/IBA.png`.
- Remove IBA from the procedural `BUILDERS` map and register `source/IBA.png` as IBA's supplied source.
- Generate the standard HOI4 flag triplet: `gfx/flags/IBA.tga`, `gfx/flags/medium/IBA.tga`, and `gfx/flags/small/IBA.tga`.
- Delete the temporary `gfx/flags/interesting flag 3.png` after the canonical source and triplet have been produced.
- Leave every other country flag and unrelated dirty file unchanged.

## Verification

- A focused contract must fail before the generator mapping changes and pass afterward.
- The generated IBA source and all three TGA files must exist at their expected dimensions.
- The generator must remain rerunnable without the deleted temporary PNG.
- Run the focused test, the Vorkerland validator, `validate_tc.py --limit 300`, and `git diff --check`.
